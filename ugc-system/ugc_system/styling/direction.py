"""Poses and expressions for a look.

Expressions
  The scene gives a target point in valence/arousal space (mood blended
  with music and place). Allowed expressions are scored by closeness to it.
  Genuine expressions are allowed unless a context bans them. Performed ones
  are allowed only in their contexts: comedy (deadpan, side-eye), kindness
  (encouraging smile when a child's first dish is too salty), editorial
  (runway stare). In a brand-trust moment (sponsor, review) only genuine
  expressions are allowed, apart from editorial craft on a fashion shoot.

Poses
  Poses must fit the place (settings + props it has) and the outfit's
  formality. They're scored on showing off the hero piece, matching the
  target energy, and freshness; a set is picked greedily for variety
  (different shot sizes, at least one detail shot when jewelry or shoes
  are the story).
"""
from __future__ import annotations

import math
from functools import lru_cache

import yaml

from ..core.env import ROOT

CFG = ROOT / "config" / "styling"
POSE_FEATURES = ["setting_fit", "hero_showcase", "energy_match", "formality_fit", "novelty"]
POSE_PRIOR = [0.95, 0.9, 0.45, 0.5, 0.6]
EXPR_FEATURES = ["emotion_match", "context_fit", "novelty", "pose_energy"]
EXPR_PRIOR = [1.0, 0.6, 0.35, 0.4]

HERO_SHOWCASE = {"footwear": ["footwear"], "jewelry": ["jewelry"], "bag": ["bag"], "outerwear": ["outerwear"],
                 "dress": ["silhouette", "full_look"], "top": ["top"], "bottom": ["bottom", "footwear"],
                 "accessory": ["accessories", "face"]}


@lru_cache(maxsize=1)
def expressions() -> list[dict]:
    return yaml.safe_load((CFG / "expressions.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def poses() -> list[dict]:
    return yaml.safe_load((CFG / "poses.yaml").read_text(encoding="utf-8"))


def _novelty(key: str, worn: dict) -> float:
    days = worn.get(key)
    return 1.0 if days is None else round(1 - math.exp(-days / 5), 3)


# ------------------------------------------------------------- expressions
def expression_allowed(e: dict, contexts: set[str]) -> tuple[bool, str]:
    banned = set(e.get("banned_in") or []) & contexts
    if banned:
        return False, f"not in a {'/'.join(sorted(banned)).replace('_', '-')} moment"
    if e["mode"] == "performed":
        allow = set(e.get("allow") or [])
        if not allow & contexts:
            return False, f"performed — only for {', '.join(sorted(allow))}"
    return True, ""


def expression_features(e: dict, target: list[float], contexts: set[str], worn: dict, pose_energy: float | None = None,
                        preferred: list[str] | None = None) -> list[float]:
    dist = math.dist((e["v"], e["a"]), target)
    match = max(0.0, 1 - dist / 1.6)
    if preferred and e["id"] in preferred:
        ctx = 1.0  # the convention of the place (runway = editorial stare)
    elif e["mode"] == "performed":
        ctx = 1.0  # it is only allowed when it's the right tool for this context
    elif "brand_trust" in contexts:
        ctx = 1.0 if e["v"] > 0.2 else 0.4
    elif e.get("suits"):  # awe belongs at a landmark, not over a burger
        ctx = 1.0 if set(e["suits"]) & contexts else 0.15
    else:
        ctx = 0.7
    energy = 0.6 if pose_energy is None else max(0.0, 1 - abs(pose_energy - (e["a"] + 1) / 2) * 1.5)
    return [round(match, 3), ctx, _novelty(f"expr:{e['id']}", worn), round(energy, 3)]


def rank_expressions(target: list[float], contexts: set[str], worn: dict) -> tuple[list[dict], list[dict]]:
    """(allowed sorted by closeness, notable disallowed with reasons)."""
    allowed, blocked = [], []
    for e in expressions():
        ok, why = expression_allowed(e, contexts)
        d = round(math.dist((e["v"], e["a"]), target), 3)
        (allowed if ok else blocked).append({**e, "distance": d, "reason": why})
    allowed.sort(key=lambda e: e["distance"])
    blocked.sort(key=lambda e: e["distance"])
    return allowed, blocked[:4]


# ------------------------------------------------------------- poses
def pose_ok(p: dict, scene, formality: float) -> tuple[bool, str]:
    if "any" not in p["settings"] and not set(p["settings"]) & set(scene.settings):
        return False, "wrong place"
    missing = set(p.get("needs") or []) - set(scene.props)
    if missing:
        return False, f"needs {', '.join(missing)}"
    lo, hi = p["formality"]
    if not (lo - 1.5 <= formality <= hi + 1.5):
        return False, "formality"
    return True, ""


def pose_features(p: dict, scene, hero_cat: str | None, formality: float, worn: dict) -> list[float]:
    # the place's most specific setting comes first (kitchen before home)
    ranks = [i for i, st in enumerate(scene.settings) if st in p["settings"]]
    setting = (1.0 if ranks[0] == 0 else 0.75) if ranks else 0.55  # "any" poses fit, but less specifically
    want = HERO_SHOWCASE.get(hero_cat or "", ["full_look"])
    shows = set(p.get("showcases") or [])
    showcase = 1.0 if shows & set(want) else 0.55 if "full_look" in shows else 0.2
    target_energy = (scene.target_va[1] + 1) / 2
    energy = max(0.0, 1 - abs(p["energy"] - target_energy) * 1.6)
    lo, hi = p["formality"]
    ff = 1.0 if lo <= formality <= hi else 0.5
    return [setting, showcase, round(energy, 3), ff, _novelty(f"pose:{p['id']}", worn)]


def pick_pose_set(scored: list[dict], n: int, hero_cat: str | None) -> list[dict]:
    """Greedy variety: best first, then penalise repeated shot sizes and showcases."""
    chosen: list[dict] = []
    pool = sorted(scored, key=lambda s: -s["score"])
    want_detail = hero_cat in ("jewelry", "footwear", "bag") and n >= 3
    while pool and len(chosen) < n:
        def adjusted(s):
            pen = 0.0
            for c in chosen:
                if c["pose"]["shot"] == s["pose"]["shot"]:
                    pen += 0.25
                pen += 0.1 * len(set(c["pose"]["showcases"]) & set(s["pose"]["showcases"]))
            if want_detail and len(chosen) == n - 1 and not any(c["pose"]["shot"] in ("closeup", "detail") for c in chosen):
                pen -= 0.3 if s["pose"]["shot"] in ("closeup", "detail") else 0
            return s["score"] - pen
        best = max(pool, key=adjusted)
        chosen.append(best)
        pool.remove(best)
    return chosen
