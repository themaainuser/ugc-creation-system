"""Assemble whole outfits from the wardrobe and score them as outfits.

1. Hard rules drop items that can't work: gender expression, formality far
   outside the place's band, weather, terrain-safe footwear, jewelry level,
   items worn too recently (statement pieces rest 7 days, basics 2).
2. Each slot keeps its best few items; outfits are built as
   (dress | top + bottom) + footwear + optional outerwear / jewelry / bag.
3. Every outfit gets a feature vector — formality fit, weather fit, persona
   fit, colour harmony, style coherence, hero-piece balance, novelty, story,
   sponsor fit, footwear fit — that the learner turns into P(best).
"""
from __future__ import annotations

import itertools
import math
import re

from .wardrobe import hex_to_hls

FEATURES = ["formality_fit", "weather_fit", "persona_fit", "color_harmony", "style_coherence",
            "hero_balance", "novelty", "story", "brand_fit", "footwear_fit"]
PRIOR = [0.9, 0.8, 0.8, 0.9, 0.7, 0.5, 0.6, 0.35, 0.5, 0.6]

JEWELRY_COUNT = {"none": (0, 0), "minimal": (0, 1), "everyday": (1, 2), "statement": (1, 3), "fine": (2, 3)}
WEATHER_WARMTH = {"hot": (1, 2), "warm": (1, 3), "mild": (2, 3), "rain": (2, 3), "cold": (3, 5)}
STORY_CONTEXTS = {"family", "intimate", "travel", "kindness", "festive"}


# ------------------------------------------------------------- item level
def _persona_fit(item: dict, persona: dict) -> float:
    wanted = {str(b).lower() for b in persona.get("brand_tier") or []}
    brand, tier = (item.get("brand") or "").lower(), item.get("tier", "")
    score = 0.35
    if brand and brand in wanted or tier in wanted or tier.replace("_", " ") in wanted:
        score = 1.0
    elif tier == "handmade" and "handmade" in (persona.get("jewelry_style") or "").lower():
        score = 1.0
    aesthetic = set(re.findall(r"[a-z]+", (persona.get("aesthetic") or "").lower()))
    tags = {t.lower() for t in item.get("style_tags", [])}
    if aesthetic & tags:
        score = min(1.0, score + 0.25)
    return score


def _formality_fit(f: int, band: list[int]) -> float:
    lo, hi = band
    return 1.0 if lo <= f <= hi else max(0.0, 1 - 0.35 * (lo - f if f < lo else f - hi))


def _weather_fit(item: dict, weather: str) -> float:
    cls = re.search(r"(hot|warm|mild|rain|cold)", weather)
    lo, hi = WEATHER_WARMTH.get(cls.group(1) if cls else "mild", (2, 3))
    w = item.get("warmth", 2)
    if item["category"] in ("jewelry", "bag", "accessory"):
        return 1.0
    return 1.0 if lo <= w <= hi else max(0.0, 1 - 0.4 * (lo - w if w < lo else w - hi))


def _novelty(item_id: str, worn: dict) -> float:
    days = worn.get(item_id)
    return 1.0 if days is None else round(1 - math.exp(-days / 6), 3)


def _gender_ok(item: dict, persona: dict) -> bool:
    ge = item.get("gender_expression", "neutral")
    if ge == "neutral" or persona.get("wardrobe_expression") == "fluid":
        return True
    g = (persona.get("gender") or "").lower()
    return (g in ("female", "woman") and ge == "feminine") or (g in ("male", "man") and ge == "masculine") or g in ("neutral", "nonbinary", "non-binary")


def filter_items(items: list[dict], scene, persona: dict, worn: dict) -> tuple[dict, list[str]]:
    """Hard rules. Returns {slot: [items]} and human-readable notes on what was excluded."""
    notes: list[str] = []
    pools: dict[str, list] = {c: [] for c in ("top", "bottom", "dress", "outerwear", "footwear", "jewelry", "bag", "accessory")}
    dropped: dict[str, int] = {}
    lo, hi = scene.formality
    for it in items:
        why = None
        if not _gender_ok(it, persona):
            why = "gender expression"
        elif it["category"] not in ("jewelry", "bag", "accessory") and not (lo - 2 <= it["formality"] <= hi + 2):
            why = "formality"
        elif it["category"] == "outerwear" and "hot" in scene.weather:
            why = "too hot for a layer"
        elif it["category"] == "footwear" and it.get("subcategory") not in scene.footwear:
            why = f"{it.get('subcategory')} don't suit {scene.terrain}/{', '.join(scene.settings[:2])}"
        elif it["category"] == "jewelry" and scene.jewelry == "none":
            why = "no jewelry here"
        else:
            days = worn.get(it["id"])
            rest = 7 if it.get("statement", 0) >= 0.7 else 2
            if days is not None and days < rest:
                why = f"worn {days}d ago"
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        pools[it["category"]].append(it)
    for why, n in sorted(dropped.items(), key=lambda kv: -kv[1]):
        notes.append(f"{n} item{'s' if n > 1 else ''} excluded: {why}")
    if not pools["footwear"]:
        fallback = [it for it in items if it["category"] == "footwear" and _gender_ok(it, persona)]
        if fallback:
            pools["footwear"] = fallback
            notes.append(f"No {'/'.join(scene.footwear[:3])} in the wardrobe — add some; using the closest pair for now")
    return pools, notes


def unary(item: dict, scene, persona: dict, worn: dict) -> float:
    return (0.35 * _formality_fit(item["formality"], scene.formality) + 0.2 * _weather_fit(item, scene.weather)
            + 0.3 * _persona_fit(item, persona) + 0.15 * _novelty(item["id"], worn))


# ------------------------------------------------------------- outfit level
def _chromatic(colors: list[dict]) -> list[tuple[float, float]]:
    out = []
    for c in colors[:2]:
        h, l, s = hex_to_hls(c.get("hex", "#888888"))
        if s > 0.28 and 0.15 < l < 0.88 and c.get("name") not in ("denim", "beige", "camel", "tan", "cream", "navy", "gold", "silver"):
            out.append((h, s))
    return out


def color_harmony(items: list[dict]) -> tuple[float, str]:
    hues = [hs for it in items if it["category"] not in ("jewelry",) for hs in _chromatic(it.get("colors", []))]
    score, why = 1.0, "neutral palette"
    distinct: list[float] = []
    for h, _ in hues:
        if all(min(abs(h - d), 360 - abs(h - d)) > 25 for d in distinct):
            distinct.append(h)
    if len(distinct) == 1:
        why = "one colour against neutrals"
    for a, b in itertools.combinations(distinct, 2):
        d = min(abs(a - b), 360 - abs(a - b))
        if d <= 40:
            why = "analogous colours"
        elif 150 <= d <= 210:
            why = "complementary pop"
        elif 45 <= d <= 135:
            score -= 0.3
            why = "colours clash"
    if len(distinct) > 2:
        score -= 0.2 * (len(distinct) - 2)
        why = "too many colours"
    metals = {c.get("name") for it in items if it["category"] == "jewelry" for c in it.get("colors", [])} & {"gold", "silver", "rose gold"}
    if {"gold", "silver"} <= metals:
        score -= 0.15
        why += ", mixed metals"
    return max(0.0, min(1.0, score)), why


def style_coherence(items: list[dict]) -> float:
    clothes = [it for it in items if it["category"] in ("top", "bottom", "dress", "outerwear", "footwear")]
    if len(clothes) < 2:
        return 0.8
    sims = []
    for a, b in itertools.combinations(clothes, 2):
        ta, tb = set(a.get("style_tags", [])), set(b.get("style_tags", []))
        sims.append(len(ta & tb) / len(ta | tb) if ta | tb else 0.5)
    f = [it["formality"] for it in clothes]
    spread = max(f) - min(f)
    return max(0.0, min(1.0, 0.45 + 0.55 * min(1.0, 2 * sum(sims) / len(sims)) - 0.08 * max(0, spread - 2)))


def hero_balance(items: list[dict]) -> tuple[float, dict | None]:
    st = [it.get("statement", 0.3) for it in items]
    hero = max(items, key=lambda it: it.get("statement", 0.3))
    total = sum(st)
    if max(st) >= 0.65 and total <= 1.7:
        return 1.0, hero
    if max(st) < 0.65:
        return 0.7, hero  # quiet look, nothing to lead with
    return max(0.2, 1 - 0.4 * (total - 1.7)), hero  # too many loud pieces


def story_score(items: list[dict], scene) -> float:
    storied = [it for it in items if it.get("tier") in ("handmade", "thrift") or it.get("story")]
    if not storied:
        return 0.3
    return 1.0 if STORY_CONTEXTS & set(scene.contexts) else 0.6


def brand_fit(items: list[dict], brand: str) -> float:
    if not brand:
        return 0.5
    return 1.0 if any(brand.lower() in (it.get("brand") or "").lower() for it in items) else 0.0


def footwear_fit(items: list[dict], scene) -> float:
    shoes = [it for it in items if it["category"] == "footwear"]
    return 1.0 if shoes and shoes[0].get("subcategory") in scene.footwear else 0.3


def features(items: list[dict], scene, persona: dict, worn: dict) -> tuple[list[float], dict]:
    wearable = [it for it in items if it["category"] not in ("jewelry", "bag", "accessory")]
    dressed = [it for it in items if it["category"] not in ("bag", "accessory")]  # jewelry must fit the occasion too
    harmony, harmony_why = color_harmony(items)
    hb, hero = hero_balance(items)
    x = [
        sum(_formality_fit(it["formality"], scene.formality) for it in dressed) / max(1, len(dressed)),
        sum(_weather_fit(it, scene.weather) for it in wearable) / max(1, len(wearable)),
        sum(_persona_fit(it, persona) for it in items) / len(items),
        harmony,
        style_coherence(items),
        hb,
        sum(_novelty(it["id"], worn) for it in items) / len(items),
        story_score(items, scene),
        brand_fit(items, scene.brand),
        footwear_fit(items, scene),
    ]
    return [round(v, 3) for v in x], {"harmony": harmony_why, "hero": hero["id"] if hero else None}


def _jewelry_sets(pool: list[dict], level: str, scene) -> list[list[dict]]:
    lo, hi = JEWELRY_COUNT.get(level, (0, 2))
    if hi == 0 or not pool:
        return [[]]
    sets = [[]] if lo == 0 else []
    for k in range(max(1, lo), hi + 1):
        for combo in itertools.combinations(pool[:6], k):
            subs = [c.get("subcategory") or c["name"] for c in combo]
            if len(set(subs)) < len(subs):  # two necklaces etc.
                continue
            if level == "minimal" and any(c.get("statement", 0) > 0.6 for c in combo):
                continue
            sets.append(list(combo))
    return sets or [[]]


def candidates(pools: dict, scene, persona: dict, worn: dict, k: int = 5, limit: int = 4000) -> list[dict]:
    rank = lambda cat, n: sorted(pools[cat], key=lambda it: -unary(it, scene, persona, worn))[:n]  # noqa: E731
    bases = [[d] for d in rank("dress", 4)] + [[t, b] for t in rank("top", k) for b in rank("bottom", k)]
    if not bases:
        bases = [[t] for t in rank("top", k)]
    shoes = rank("footwear", 3) or [None]
    cold = "cold" in scene.weather or "rain" in scene.weather
    outers = [None] + rank("outerwear", 2) if pools["outerwear"] else [None]
    jewel = _jewelry_sets(rank("jewelry", 6), scene.jewelry, scene)
    bags = [None] + (rank("bag", 2) if scene.privacy != "private" else [])
    out = []
    for base, shoe, outer, js, bag in itertools.product(bases, shoes, outers, jewel, bags):
        if outer is None and cold and pools["outerwear"]:
            continue
        items = [*base, *(x for x in (outer, shoe) if x), *js, *([bag] if bag else [])]
        out.append(items)
        if len(out) >= limit:
            break
    return [{"items": it} for it in out]


def describe(items: list[dict]) -> str:
    """Prompt-ready outfit description, garments first, jewelry last."""
    order = {"dress": 0, "top": 1, "bottom": 2, "outerwear": 3, "footwear": 4, "bag": 5, "accessory": 6, "jewelry": 7}
    parts = []
    for it in sorted(items, key=lambda i: order.get(i["category"], 9)):
        d = it.get("description") or f"{(it.get('colors') or [{}])[0].get('name', '')} {it['name']}".strip()
        if it.get("brand") and it["brand"].lower() not in d.lower() and it.get("tier") not in ("handmade", "thrift"):
            d = f"{it['brand']} {d}"
        parts.append(d)
    return "; ".join(parts)


GENERIC = {"handmade", "thrift", "vintage", "the", "and", "with", "my", "a", "of", "set", "new", "old"}


def requested_items(items: list[dict], text: str) -> list[dict]:
    """Items the operator names in the notes ("the shell necklace", "my Gucci heels")."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    if not words:
        return []
    hits = []
    for it in items:
        name = set(re.findall(r"[a-z]+", f"{it.get('name', '')} {it['id']}".lower())) - GENERIC
        brand = set(re.findall(r"[a-z]+", (it.get("brand") or "").lower()))
        overlap = name & words
        if len(overlap) >= 2 or (overlap and brand and brand <= words):
            hits.append(it)
    by_cat: dict[str, dict] = {}
    for it in hits:  # one per category (for jewelry: one per kind)
        key = it["category"] + (it.get("subcategory") or "" if it["category"] == "jewelry" else "")
        by_cat.setdefault(key, it)
    return list(by_cat.values())
