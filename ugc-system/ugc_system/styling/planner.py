"""Daily look: scene -> outfit -> expression -> poses -> shot prompts.

    look = plan(persona_id, {"mood": .., "place": .., "environment": .., "music": ..,
                             "notes": .., "date": .., "time_of_day": .., "weather": .., "brand": ..},
                shots=3, art_director=False)
    feedback(look_id, "approve" | "reject" | "swap", alt=2)

Looks are saved to data/looks/<persona>/<id>.json. Feedback trains the
persona's learners and, on approve, logs the items/poses/expressions as worn.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from ..core import fsutil, opus
from ..core.env import ROOT, load_env
from . import direction, outfit, scene as scene_mod, wardrobe
from .learning import Learner, reward_from

LOOKS = ROOT / "data" / "looks"
PERSONAS = ROOT / "personas"
NEGATIVE = ("extra or fused fingers, warped hands, melted or misspelled logos, wrong garment colours, "
            "duplicated jewelry, plastic skin, over-smoothed face, text, watermark, extra limbs")
ITEM_KEYS = ("id", "file", "root", "name", "category", "subcategory", "brand", "tier", "colors",
             "formality", "statement", "story", "description", "demo")


class PlanError(RuntimeError):
    pass


def persona(pid: str) -> dict:
    p = PERSONAS / f"{pid}.yaml"
    if not p.exists():
        raise PlanError(f"persona '{pid}' not found in personas/")
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    d.setdefault("id", pid)
    return d


def learners(pid: str) -> dict[str, Learner]:
    return {"outfit": Learner(pid, "outfit", outfit.FEATURES, outfit.PRIOR),
            "pose": Learner(pid, "pose", direction.POSE_FEATURES, direction.POSE_PRIOR),
            "expression": Learner(pid, "expression", direction.EXPR_FEATURES, direction.EXPR_PRIOR)}


def _slim(it: dict) -> dict:
    return {k: it.get(k) for k in ITEM_KEYS}


def _signature(items: list[dict]) -> tuple:
    return tuple(sorted(i["id"] for i in items if i["category"] in ("top", "bottom", "dress")))


# ------------------------------------------------------------- outfit decision
def decide_outfit(items, sc, per, worn, L: Learner, seed) -> tuple[dict, list[str]]:
    pools, notes = outfit.filter_items(items, sc, per, worn)
    asked = outfit.requested_items(items, f"{sc.notes} {sc.environment} {sc.mood}")
    for it in asked:  # "wearing the shell necklace my niece made" -> it's in the look, rules or not
        if it not in pools[it["category"]]:
            pools[it["category"]].insert(0, it)
    cands = outfit.candidates(pools, sc, per, worn)
    if asked:
        ids = {a["id"] for a in asked}
        locked = [c for c in cands if ids <= {i["id"] for i in c["items"]}]
        if not locked:  # e.g. jewelry level allowed none: force it into the best outfits
            locked = [{"items": c["items"] + [a for a in asked if a not in c["items"]]} for c in cands[:300]]
        cands = locked
        notes.append("Locked in because you mentioned it: " + ", ".join(a["name"] for a in asked))
    if not cands:
        missing = [c for c in ("top", "bottom", "dress", "footwear") if not pools[c]]
        raise PlanError(f"No outfit possible for this scene — nothing usable in: {', '.join(missing)}. "
                        "Add more items to wardrobe/ or loosen the place.")
    for c in cands:
        c["x"], c["meta"] = outfit.features(c["items"], sc, per, worn)
    mean = L.mean
    cands.sort(key=lambda c: -float(np.dot(c["x"], mean)))
    shortlist, seen = [], set()
    for c in cands:  # five genuinely different outfits, not five jewelry swaps
        sig = _signature(c["items"])
        if sig in seen:
            continue
        seen.add(sig)
        shortlist.append(c)
        if len(shortlist) == 5:
            break
    X = np.array([c["x"] for c in shortlist])
    d = L.decide(X, seed=seed)
    order = np.argsort(d["p_best"])[::-1]
    alts = []
    for rank, i in enumerate(order):
        c = shortlist[i]
        alts.append({"items": [_slim(it) for it in c["items"]], "x": c["x"], "meta": c["meta"],
                     "p_best": d["p_best"][i], "predicted_approval": d["predicted_approval"][i],
                     "describe": outfit.describe(c["items"])})
    chosen = next(n for n, i in enumerate(order) if i == d["chosen"])
    pick = alts[chosen]
    gate = "automate" if pick["p_best"] >= 0.5 and pick["predicted_approval"] >= 0.6 else "review"
    return {"chosen": chosen, "alternatives": alts, "gate": gate, "margin": d["margin"],
            "explain": L.explain(np.array(pick["x"])), "calibration": L.calibration()}, notes


# ------------------------------------------------------------- shots
def plan_shots(sc, per, look_items: list[dict], hero_id: str | None, n: int, worn, Lp: Learner, Le: Learner, seed) -> tuple[list, dict]:
    rng = np.random.default_rng(seed)
    hero = next((i for i in look_items if i["id"] == hero_id), None)
    hero_cat = hero["category"] if hero else None
    wear = [i for i in look_items if i["category"] in ("top", "bottom", "dress", "outerwear")]
    formality = sum(i["formality"] for i in wear) / max(1, len(wear))

    # poses
    usable, blocked = [], 0
    for p in direction.poses():
        ok, _ = direction.pose_ok(p, sc, formality)
        if ok:
            usable.append(p)
        else:
            blocked += 1
    if not usable:
        raise PlanError("No pose fits this place — add props to the environment (mirror, stairs, chair...)")
    Xp = np.array([direction.pose_features(p, sc, hero_cat, formality, worn) for p in usable])
    wp = Lp.draws(1, rng)[0]
    dp = Lp.decide(Xp, seed=seed)
    scored = [{"pose": p, "x": Xp[i].tolist(), "score": float(Xp[i] @ wp), "p_best": dp["p_best"][i],
               "predicted": dp["predicted_approval"][i]} for i, p in enumerate(usable)]
    picked = direction.pick_pose_set(scored, n, hero_cat)

    # expressions
    ctx = set(sc.contexts)
    allowed, avoid = direction.rank_expressions(sc.target_va, ctx, worn)
    we = Le.draws(1, rng)[0]
    pref = sc.preferred_faces
    xe = {e["id"]: direction.expression_features(e, sc.target_va, ctx, worn, preferred=pref) for e in allowed}
    primary = max(allowed[:10], key=lambda e: float(np.dot(xe[e["id"]], we)))
    secondary = next((e for e in allowed if e["id"] != primary["id"] and abs(e["a"] - primary["a"]) + abs(e["v"] - primary["v"]) > 0.35), None)

    shots, used = [], set()
    for n_, s in enumerate(picked, 1):
        p = s["pose"]
        cands = []
        for e in allowed[:12]:
            x = direction.expression_features(e, sc.target_va, ctx, worn, p["energy"], pref)
            bonus = -0.15 if e["id"] in used else 0.0
            cands.append((float(np.dot(x, we)) + bonus, e, x))
        _, e, x = max(cands, key=lambda c: c[0])
        if "kindness" in ctx and p["shot"] in ("half", "closeup") and not any(sh["expression"]["id"] == "encouraging_smile" for sh in shots):
            k = next((a for a in allowed if a["id"] == "encouraging_smile"), None)
            if k:
                e, x = k, direction.expression_features(k, sc.target_va, ctx, worn, p["energy"])
        used.add(e["id"])
        shots.append({"n": n_, "pose": {k: p.get(k) for k in ("id", "name", "shot", "energy", "showcases", "prompt", "camera")},
                      "pose_x": s["x"], "pose_predicted": s["predicted"],
                      "expression": {k: e.get(k) for k in ("id", "name", "mode", "v", "a", "face", "motion")},
                      "expression_x": x})
    expr = {"target_va": sc.target_va, "va_parts": sc.va_parts,
            "primary": {k: primary.get(k) for k in ("id", "name", "mode", "v", "a", "face")},
            "secondary": {k: secondary.get(k) for k in ("id", "name", "mode", "v", "a", "face")} if secondary else None,
            "nearby_allowed": [{"id": e["id"], "name": e["name"], "mode": e["mode"], "v": e["v"], "a": e["a"]} for e in allowed[:8]],
            "avoid": [{"id": e["id"], "name": e["name"], "mode": e["mode"], "v": e["v"], "a": e["a"], "reason": e["reason"]} for e in avoid],
            "poses_blocked": blocked}
    return shots, expr


def write_prompts(shots: list[dict], per: dict, sc, look_items: list[dict]) -> None:
    character = per.get("appearance") or (
        f"{per.get('name', 'the creator')}, a {per.get('age_range', '')} {per.get('gender', '')} content creator "
        "(match the character reference image exactly)").replace("  ", " ")
    wearing = outfit.describe(look_items)
    where = sc.place + (f", {sc.environment}" if sc.environment else "")
    when = ", ".join(x for x in (sc.time_of_day, sc.weather, sc.season) if x)
    refs = ([per["reference_image"]] if per.get("reference_image") else []) + [
        f"{'demo' if i.get('demo') else 'wardrobe'}/{i['file']}" for i in look_items]
    for sh in shots:
        p, e = sh["pose"], sh["expression"]
        sh["image_prompt"] = (
            f"Photorealistic Instagram photo of {character}. Wearing: {wearing}. "
            f"Pose: {p['prompt']}. Expression: {e['face']}. Setting: {where}; {sc.lighting}"
            f"{'; ' + when if when else ''}. Camera: {p['camera']}. "
            f"{per.get('aesthetic', '')} aesthetic, natural skin texture, garments exactly as in the reference images, 4:5 vertical.")
        sh["video_prompt"] = (
            f"{character}, same outfit and setting. {p['prompt']}; {e['motion']}. {sc.lighting}. "
            "Handheld phone feel with a slow push-in, 4 seconds, 9:16, natural motion, no morphing of garments or jewelry.")
        sh["negative_prompt"] = NEGATIVE
        sh["reference_images"] = refs


# ------------------------------------------------------------- Opus art director
ART_SYSTEM = """You are the creative director of an AI fashion influencer. You get the persona, the scene, and up to three shortlisted outfits (with garment photos). Pick the outfit a sharp stylist would choose for this exact moment, and explain it like a stylist would (silhouette, colour story, what the hero piece is, why it suits the place and mood). Reply with one JSON object only:
{"pick": <index>, "why": "<2-3 sentences>", "styling_notes": "<tucks, rolls, layering, hair and makeup notes>", "caption": "<an Instagram caption in the persona's voice, no hashtags>", "hashtags": ["..."]}"""


def art_direct(per: dict, sc, alts: list[dict]) -> dict | None:
    if not opus.available():
        return None
    top = alts[:3]
    parts = [{"type": "text", "text": f"Persona:\n{yaml.safe_dump(per, sort_keys=False)}\nScene: mood {sc.mood}; place {sc.place}; "
              f"environment {sc.environment or '-'}; {sc.weekday} {sc.date} {sc.time_of_day}; weather {sc.weather}; music {sc.music or '-'}; "
              f"notes {sc.notes or '-'}; sponsor {sc.brand or 'none'}; contexts {', '.join(sc.contexts) or '-'}"}]
    for n, a in enumerate(top):
        parts.append({"type": "text", "text": f"Outfit {n}: {a['describe']}"})
        for it in a["items"][:6]:
            parts.append({"type": "image", "path": str(wardrobe.image_path(it))})
    res = opus.complete({"system": ART_SYSTEM, "parts": parts}, max_tokens=6000, effort="medium")
    data = opus.extract_json(res["text"])
    data["cost_usd"] = res["est_cost_usd"]
    data["pick"] = max(0, min(len(top) - 1, int(data.get("pick", 0))))
    return data


# ------------------------------------------------------------- plan / feedback
def plan(pid: str, inputs: dict, shots: int = 3, art_director: bool = False, seed: int | None = None) -> dict:
    load_env()
    per = persona(pid)
    sc = scene_mod.interpret(inputs, per)
    items = wardrobe.load()
    worn = wardrobe.worn_days_ago(pid, sc.date)
    L = learners(pid)
    seed = seed if seed is not None else secrets.randbelow(2**31)

    dec, notes = decide_outfit(items, sc, per, worn, L["outfit"], seed)
    ad = None
    if art_director:
        try:
            ad = art_direct(per, sc, dec["alternatives"])
        except Exception as e:  # never lose the look over the optional pass
            notes.append(f"Art director skipped: {type(e).__name__}: {e}")
        if ad is not None and ad["pick"] != dec["chosen"]:
            notes.append(f"Opus picked alternative {ad['pick'] + 1} over the learner's choice {dec['chosen'] + 1}.")
            dec["chosen"], dec["chosen_by"] = ad["pick"], "opus"
    dec.setdefault("chosen_by", "learner")
    pick = dec["alternatives"][dec["chosen"]]
    look_items = pick["items"]

    shot_list, expr = plan_shots(sc, per, look_items, pick["meta"]["hero"], shots, worn, L["pose"], L["expression"], seed)
    write_prompts(shot_list, per, sc, look_items)
    if any(i.get("demo") for i in look_items):
        notes.insert(0, "Using the DEMO wardrobe (placeholder images). Drop real images into ugc-system/wardrobe/ and run a scan.")

    look = {
        "id": f"{sc.date}-{secrets.token_hex(2)}", "persona": pid, "persona_name": per.get("name", pid),
        "created_at": datetime.now(timezone.utc).isoformat(), "seed": seed,
        "scene": sc.to_dict(), "outfit": dec, "expression": expr, "shots": shot_list,
        "art_director": ad, "notes": notes + sc.situation_notes, "feedback": None,
    }
    save(look)
    return look


def path_for(look_id: str, pid: str | None = None) -> Path:
    if pid:
        return LOOKS / pid / f"{look_id}.json"
    hits = list(LOOKS.glob(f"*/{look_id}.json"))
    if not hits:
        raise PlanError(f"look {look_id} not found")
    return hits[0]


def save(look: dict) -> Path:
    p = path_for(look["id"], look["persona"])
    p.parent.mkdir(parents=True, exist_ok=True)
    fsutil.write_text(p, json.dumps(look, indent=2, ensure_ascii=False))
    return p


def feedback(look_id: str, verdict: str, *, alt: int | None = None, rating: int | None = None,
             engagement: float | None = None, baseline: float | None = None, note: str = "") -> dict:
    p = path_for(look_id)
    look = json.loads(p.read_text(encoding="utf-8"))
    L = learners(look["persona"])
    dec = look["outfit"]
    pick = dec["alternatives"][dec["chosen"]]
    r = reward_from(verdict, rating, engagement, baseline)
    if verdict == "swap" and alt is not None and alt != dec["chosen"]:
        other = dec["alternatives"][alt]
        L["outfit"].update(pick["x"], 0.0, pick["predicted_approval"], f"{look_id}:swap-from")
        L["outfit"].update(other["x"], 1.0, other["predicted_approval"], f"{look_id}:swap-to")
        dec["chosen"], dec["chosen_by"] = alt, "operator"
        pick = other
    else:
        L["outfit"].update(pick["x"], r, pick["predicted_approval"], look_id)
        for sh in look["shots"]:
            L["pose"].update(sh["pose_x"], r, sh.get("pose_predicted"), look_id)
            L["expression"].update(sh["expression_x"], r, None, look_id)
    if verdict in ("approve", "posted") or (verdict == "swap" and alt is not None):
        wardrobe.log_worn(look["persona"], look["scene"]["date"], [i["id"] for i in pick["items"]],
                          [f"pose:{s['pose']['id']}" for s in look["shots"]],
                          [f"expr:{s['expression']['id']}" for s in look["shots"]], look_id)
    look["feedback"] = {"verdict": verdict, "alt": alt, "rating": rating, "engagement": engagement,
                        "reward": r, "note": note, "at": datetime.now(timezone.utc).isoformat()}
    if verdict == "swap" and alt is not None:  # rewrite prompts for the swapped-in outfit
        per = persona(look["persona"])
        sc = scene_mod.interpret({k: look["scene"][k] for k in ("mood", "place", "environment", "music", "notes", "date", "time_of_day", "brand")}, per)
        write_prompts(look["shots"], per, sc, pick["items"])
    fsutil.write_text(p, json.dumps(look, indent=2, ensure_ascii=False))
    return {"look": look, "calibration": {k: v.calibration() for k, v in L.items()}}


def list_looks(pid: str | None = None, limit: int = 40) -> list[dict]:
    files = sorted((LOOKS.glob(f"{pid}/*.json") if pid else LOOKS.glob("*/*.json")),
                   key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    out = []
    for f in files:
        try:
            l = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        pick = l["outfit"]["alternatives"][l["outfit"]["chosen"]]
        out.append({"id": l["id"], "persona": l["persona"], "persona_name": l.get("persona_name"),
                    "place": l["scene"]["place"], "mood": l["scene"]["mood"], "date": l["scene"]["date"],
                    "verdict": (l.get("feedback") or {}).get("verdict"),
                    "thumb": next((i for i in pick["items"] if i["category"] in ("dress", "top")), pick["items"][0])})
    return out
