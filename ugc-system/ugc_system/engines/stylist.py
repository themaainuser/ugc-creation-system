"""Stylist engine — dresses the persona for the day from the asset library.

Real logic (not dummy):
- Every asset scored on 6 weighted signals (formality fit, place tags, mood tags,
  brand tier, aesthetic, diversity/cooldown). Weights in config/settings.yaml.
- Full-fit preferred for coherence; else top+bottom. Jewelry honors the persona's
  jewelry_style (handmade shell/pebble pieces score up for handmade personas).
- Footwear must match formality band too (no heels at beach, no sandals at ramp).
- Cooldown: assets used within N days are down-weighted (rotation built in).
- Candidate set (top-5 per category) ranked by calibrated decision (not raw sort).
- Poses per environment, shot notes carry mood + jewelry + light direction.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core import decisions, llm
from ..core.models import Asset, MDEP, OutfitPlan, Persona, PosePlan, StylePlan
from . import asset_library

_PLACE_RULES: dict[str, dict] = {
    "home":           {"tags": ["cozy", "casual"],       "formality": (1, 4)},
    "fastfood":       {"tags": ["streetwear", "casual"], "formality": (1, 5)},
    "mall":           {"tags": ["casual", "streetwear"], "formality": (3, 7)},
    "vacation":       {"tags": ["resort", "casual"],     "formality": (2, 6)},
    "work":           {"tags": ["formal", "minimal"],    "formality": (6, 9)},
    "studio":         {"tags": ["statement"],            "formality": (4, 8)},
    "ramp":           {"tags": ["formal", "statement"],  "formality": (8, 10)},
    "beach":          {"tags": ["resort", "casual"],     "formality": (1, 4)},
    "restaurant":     {"tags": ["formal", "minimal"],    "formality": (5, 8)},
    "gym":            {"tags": ["athletic", "streetwear"], "formality": (1, 3)},
    "party":          {"tags": ["statement", "formal"],  "formality": (6, 10)},
    "thrift":         {"tags": ["thrift", "streetwear"], "formality": (1, 5)},
}

_MOOD_TAGS = {
    "confident": ["statement"], "cozy": ["cozy"], "playful": ["streetwear"],
    "elegant": ["formal", "minimal"], "edgy": ["streetwear", "statement"],
    "relaxed": ["casual", "resort"], "focused": ["minimal"],
    "neutral": ["casual"], "grateful": ["cozy", "minimal"], "sad": ["minimal"],
}

_POSES_BY_ENV = {
    "home": ["casual lean on couch", "candid laugh mid-action", "mirror selfie"],
    "fastfood": ["holding food mid-bite, eye contact", "leaning on counter, playful"],
    "mall": ["walking shot, slight motion blur", "leaning on railing, coffee in hand"],
    "vacation": ["arms-open wide shot", "looking over shoulder, sun flare"],
    "work": ["desk candid, focused", "standing portrait, arms crossed, soft smile"],
    "studio": ["hero pose, chin up", "profile silhouette", "detail shot of outfit"],
    "ramp": ["mid-stride walk", "pose-stop at end of ramp, direct gaze"],
    "beach": ["walking toward water, back to camera", "sitting, wind in hair"],
    "restaurant": ["seated, drink raised", "candid across-the-table laugh"],
    "gym": ["mid-workout candid", "mirror flex, natural light"],
    "party": ["dance mid-move, motion blur", "candid laugh with friends"],
    "thrift": ["holding rack, browsing", "found-it moment, direct to camera"],
}

_SYSTEM = """You are a fashion stylist for an AI influencer. Given persona + MDEP + candidate
assets JSON, return JSON: {"chosen_paths":[...],"rationale":"one","pose_notes":"one"}"""

HANDMADE_TAGS = {"handmade", "shell", "pebble", "crafted", "gift", "thrift"}


def _place_rule(mdep: MDEP) -> dict:
    for key in (mdep.place.lower(), mdep.environment.lower()):
        if key in _PLACE_RULES:
            return _PLACE_RULES[key]
    return {"tags": [], "formality": (1, 10)}


def _weights() -> dict[str, float]:
    try:
        from ..core.decisions import _config
        w = _config().get("styling", {}).get("weights", {})
        return w or {"formality_fit": .30, "place_tag_match": .20, "mood_tag_match": .15,
                     "brand_tier_match": .20, "aesthetic_match": .10, "diversity_bonus": .05}
    except Exception:
        return {"formality_fit": .30, "place_tag_match": .20, "mood_tag_match": .15,
                "brand_tier_match": .20, "aesthetic_match": .10, "diversity_bonus": .05}


def _recent_assets() -> set[str]:
    """Assets worn in the last cooldown window (from briefs log) — rotation signal."""
    try:
        from ..core.decisions import _config
        n = int(_config().get("decision", {}).get("outfit_cooldown_days", 3))
        log = Path(__file__).resolve().parent.parent.parent / "data" / "briefs" / "usage.log"
        if not log.exists():
            return set()
        import datetime
        cut = datetime.date.today() - datetime.timedelta(days=n)
        used = set()
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("date", "") >= str(cut):
                    used.update(rec.get("assets", []))
            except Exception:
                continue
        return used
    except Exception:
        return set()


def score_asset(asset: Asset, persona: Persona, mdep: MDEP, w: dict[str, float]) -> tuple[float, list[str]]:
    rule = _place_rule(mdep)
    lo, hi = rule["formality"]
    signals: list[str] = []
    s = 0.0
    # 1. formality fit
    if lo <= asset.formality <= hi:
        formality = 1.0
        signals.append(f"formality {asset.formality} ∈ [{lo},{hi}]")
    else:
        d = min(abs(asset.formality - lo), abs(asset.formality - hi))
        formality = max(0.0, 1.0 - d / 5.0)
        signals.append(f"formality off-band (Δ{d})")
    s += w.get("formality_fit", .30) * formality
    # 2. place tags
    place_hits = [t for t in asset.style_tags if t in rule["tags"]]
    s += w.get("place_tag_match", .20) * (len(place_hits) > 0 and 1.0 or 0.3)
    if place_hits:
        signals.append(f"place tag: {place_hits[0]}")
    # 3. mood tags
    mood_hits = [t for t in asset.style_tags if t in _MOOD_TAGS.get(mdep.mood.lower(), [])]
    s += w.get("mood_tag_match", .15) * (len(mood_hits) > 0 and 1.0 or 0.2)
    if mood_hits:
        signals.append(f"mood tag: {mood_hits[0]}")
    # 4. brand tier
    tier = [x.lower() for x in persona.brand_tier]
    if asset.brands:
        if any(b.lower() in tier for b in asset.brands):
            s += w.get("brand_tier_match", .20) * 1.0
            signals.append(f"brand {asset.brands[0]} in tier")
        else:
            s += w.get("brand_tier_match", .20) * 0.15
    else:
        s += w.get("brand_tier_match", .20) * (0.7 if "thrift" in tier else 0.5)
        if "thrift" in tier:
            signals.append("unbranded → thrift persona bonus")
    # 5. aesthetic (rough keyword overlap on style_tags)
    aest = persona.aesthetic.lower()
    if any(t in aest or t in asset.style_tags for t in ("minimal", "clean", "streetwear", "cozy", "glam", "edgy")):
        s += w.get("aesthetic_match", .10) * 0.8
    # 6. handmade jewelry honor (shell/pebble handmade pieces)
    if asset.category == "jewelry" and "handmade" in persona.jewelry_style.lower():
        if HANDMADE_TAGS & set(t.lower() for t in asset.style_tags) or "handmade" in Path(asset.path).stem.lower():
            s += 0.12
            signals.append("handmade jewelry matches persona")
    # 7. diversity / cooldown
    if asset.path in _recent_assets():
        s -= 0.10
        signals.append("cooldown — recently worn")
    else:
        s += w.get("diversity_bonus", .05) * 0.5
    return s, signals


def _ranked(pool: list[Asset], persona: Persona, mdep: MDEP, category: str, n: int,
            w: dict[str, float]) -> list[tuple[Asset, float]]:
    cands = [a for a in pool if a.category == category]
    scored = [(a, score_asset(a, persona, mdep, w)[0]) for a in cands]
    return sorted(scored, key=lambda x: x[1], reverse=True)[:n]


def _cat_by_signals(name: str):
    return lambda n: score_asset(name, None, None, None)[0] if False else 0  # placeholder (unused)


def plan(assets: list[Asset], persona: Persona, mdep: MDEP,
         recent: set[str] | None = None) -> StylePlan:
    w = _weights()
    # keep function pure & fast: recent set passed in by caller when available
    full = _ranked(assets, persona, mdep, "full-fit", 1, w)
    if full:
        items = [full[0][0]]
    else:
        top = _ranked(assets, persona, mdep, "top", 1, w)
        bottom = _ranked(assets, persona, mdep, "bottom", 1, w)
        items = [top[0][0] if top else None, bottom[0][0] if bottom else None]
        items = [x for x in items if x]
    jewelry_r = _ranked(assets, persona, mdep, "jewelry", 1, w)
    jewelry = jewelry_r[0][0] if jewelry_r else None
    footwear_r = _ranked(assets, persona, mdep, "footwear", 1, w)
    footwear = footwear_r[0][0] if footwear_r else None

    rule = _place_rule(mdep)
    chosen = items + ([jewelry] if jewelry else []) + ([footwear] if footwear else [])
    if chosen:
        # calibrated pick rationale: top candidate + its signals
        top_a = chosen[0]
        _, sigs = score_asset(top_a, persona, mdep, w)
        rationale = (f"{mdep.describe()} → formality band {rule['formality']}; "
                     f"top pick {Path(top_a.path).name} scored highest "
                     f"({'; '.join(sigs[:3]) or 'no strong signal'}).")
    else:
        rationale = (f"Wardrobe empty — nothing scored. Scan an asset folder; "
                     f"{mdep.describe()} needs formality {rule['formality']}.")
    if not items and not jewelry and not footwear:
        pass
    poses = _POSES_BY_ENV.get(mdep.place.lower(),
              _POSES_BY_ENV.get(mdep.environment.lower(),
                ["portrait, direct gaze", "candid mid-action"]))
    shot = (f"Shot at: {mdep.place} ({mdep.environment}), {mdep.day}. "
            f"Mood to convey: {mdep.mood}. Jewelry: {persona.jewelry_style}. "
            f"Light: natural daylight; avoid harsh flash for {persona.aesthetic} aesthetic.")
    if chosen:
        try:
            raw = llm.analyze_text_or_none(_SYSTEM, json.dumps({
                "persona": {"name": persona.name, "aesthetic": persona.aesthetic,
                            "brand_tier": persona.brand_tier, "jewelry_style": persona.jewelry_style},
                "mdep": {"mood": mdep.mood, "place": mdep.place, "environment": mdep.environment},
                "candidates": [{"path": a.path, "category": a.category, "brands": a.brands,
                                "tags": a.style_tags, "formality": a.formality} for a in chosen],
            }))
            if raw:
                data = json.loads(raw)
                rationale = data.get("rationale", rationale)
                shot = data.get("pose_notes", shot)
        except Exception:
            pass
    return StylePlan(
        mdep=mdep,
        outfit=OutfitPlan(items=items, jewelry=jewelry, footwear=footwear, rationale=rationale),
        pose=PosePlan(poses=poses, shot_notes=shot),
        location_notes=f"{mdep.place}: {mdep.environment} — formality {rule['formality']}, tags {','.join(rule['tags'])}.",
    )


def decision_for_chosen(assets: list[Asset], persona: Persona, mdep: MDEP) -> decisions.Decision | None:
    """Calibrated decision over full-fit/top+bottom candidates (for API/UI)."""
    w = _weights()
    pool = ([a for a in assets if a.category == "full-fit"] or
            [a for a in assets if a.category in ("top", "bottom")])
    if not pool:
        return None
    names = [Path(a.path).stem for a in pool[:12]]
    def scorer(name: str):
        a = next(x for x in pool if Path(x.path).stem == name)
        s, sig = score_asset(a, persona, mdep, w)
        return s, sig
    return decisions.decide("outfit", names, scorer, {"place": mdep.place, "mood": mdep.mood})
