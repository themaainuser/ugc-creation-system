"""Mood / Day / Environment / Place (+ music) -> a Scene the stylist can obey.

Rules from config/styling/scenes.yaml do the work offline. When no place
rule matches (a place the rules have never heard of), Opus fills the gaps
if a key is configured; otherwise the safe default is used and flagged.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date as Date
from functools import lru_cache

import yaml

from ..core import opus
from ..core.env import ROOT

CFG = ROOT / "config" / "styling"
CACHE = ROOT / "data" / "styling" / "scene_cache.json"
LIST_KEYS = ("settings", "footwear", "props", "contexts", "faces")


@lru_cache(maxsize=1)
def rules() -> dict:
    return yaml.safe_load((CFG / "scenes.yaml").read_text(encoding="utf-8"))


@dataclass
class Scene:
    mood: str
    place: str
    environment: str = ""
    music: str = ""
    notes: str = ""
    date: str = ""
    time_of_day: str = ""
    weather: str = ""
    brand: str = ""
    # derived
    weekday: str = ""
    season: str = ""
    settings: list = field(default_factory=list)
    indoor: bool = False
    privacy: str = "public"
    formality: list = field(default_factory=lambda: [2, 6])
    terrain: str = "pavement"
    footwear: list = field(default_factory=list)
    jewelry: str = "everyday"
    props: list = field(default_factory=list)
    lighting: str = ""
    contexts: list = field(default_factory=list)
    target_va: list = field(default_factory=lambda: [0.3, 0.0])
    va_parts: dict = field(default_factory=dict)
    preferred_faces: list = field(default_factory=list)
    situation_notes: list = field(default_factory=list)
    matched: list = field(default_factory=list)
    source: str = "rules"

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------- climate
def _season(d: Date, region: str) -> tuple[str, str]:
    """(season, default weather) for the persona's region."""
    m = d.month
    if region.startswith("india"):
        north = "north" in region
        if m in (3, 4, 5):
            return "summer", "hot"
        if m in (6, 7, 8, 9):
            return "monsoon", "rain"
        if m in (10, 11):
            return "post-monsoon", "warm"
        return "winter", "cold" if north else "mild"
    if region in ("southern", "australia", "south"):
        m = (m + 5) % 12 + 1
    return (("winter", "cold") if m in (12, 1, 2) else ("spring", "mild") if m in (3, 4, 5)
            else ("summer", "hot") if m in (6, 7, 8) else ("autumn", "mild"))


def _weather_class(text: str, default: str) -> str:
    t = text.lower()
    for word, cls in (("snow", "cold"), ("cold", "cold"), ("chilly", "cold"), ("winter", "cold"),
                      ("rain", "rain"), ("monsoon", "rain"), ("storm", "rain"), ("humid", "hot"),
                      ("hot", "hot"), ("sunny", "warm"), ("warm", "warm"), ("mild", "mild"),
                      ("cool", "mild"), ("breezy", "mild")):
        if word in t:
            return cls
    return default


def _lighting(base: str, time_of_day: str, indoor: bool) -> str:
    t = time_of_day.lower()
    if not t:
        return base
    if any(w in t for w in ("night", "late", "evening")) and not indoor:
        return "night: city lights, street lamps and on-camera flash"
    if "golden" in t or "sunset" in t:
        return "golden-hour sun, long warm shadows"
    if "morning" in t or "sunrise" in t:
        return f"soft morning light — {base}" if indoor else "soft low morning sun"
    if "noon" in t or "afternoon" in t:
        return base if indoor else "bright afternoon sun, crisp shadows"
    return base


# ------------------------------------------------------------- emotion target
def mood_va(mood: str) -> tuple[list[float] | None, list[str]]:
    words = re.findall(r"[a-z]+", mood.lower())
    hits = [w for w in words if w in rules()["moods"]]
    if not hits:
        return None, []
    vs = [rules()["moods"][w] for w in hits]
    return [round(sum(v[0] for v in vs) / len(vs), 3), round(sum(v[1] for v in vs) / len(vs), 3)], hits


def music_va(music: str) -> list[float] | None:
    for rule in rules()["music"]:
        if re.search(rule["match"], music, re.I):
            return rule["va"]
    return None


def _blend(parts: dict) -> list[float]:
    """Weighted blend of mood, music and place feelings (weights renormalised)."""
    w = {"mood": 1.0 - rules()["music_weight"] - rules()["place_weight"],
         "music": rules()["music_weight"], "place": rules()["place_weight"], "situation": 0.5}
    total = sum(w[k] for k in parts)
    v = sum(parts[k][0] * w[k] for k in parts) / total
    a = sum(parts[k][1] * w[k] for k in parts) / total
    return [round(max(-1, min(1, v)), 3), round(max(-1, min(1, a)), 3)]


# ------------------------------------------------------------- Opus fallback
def _opus_place(place: str, environment: str) -> dict | None:
    key = hashlib.sha1(f"{place}|{environment}".lower().encode()).hexdigest()[:16]
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if key in cache:
        return cache[key]
    if not opus.available():
        return None
    d = rules()["default"]
    system = ("You classify a photo-shoot location for an AI fashion influencer. Reply with ONE JSON object "
              "using exactly these keys and vocabularies:\n"
              f"{json.dumps(d)}\n"
              "settings: any of home bedroom kitchen street cafe restaurant fastfood mall beach pool nature landmark "
              "studio runway office car hotel gym event nightlife festive airport campus. "
              "footwear: any of sneakers heels flats sandals slides boots loafers formal_shoes sports barefoot. "
              "jewelry: none|minimal|everyday|statement|fine. terrain: floor|pavement|sand|trail|grass|water. "
              "props: mirror stairs chair table window car railing bed counter escalator pool wall. "
              "contexts: family kindness comedy editorial romance nightlife festive travel food fitness work intimate. "
              "va: [valence, arousal] in -1..1 for how the place makes people feel.")
    try:
        res = opus.complete({"system": system, "parts": [{"type": "text", "text": f"Place: {place}\nEnvironment: {environment}"}]},
                            max_tokens=2000, effort="low")
        data = opus.extract_json(res["text"])
    except Exception:
        return None
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache[key] = data
    CACHE.write_text(json.dumps(cache, indent=2))
    return data


# ------------------------------------------------------------- main
def interpret(inp: dict, persona: dict | None = None) -> Scene:
    persona = persona or {}
    sc = Scene(mood=inp.get("mood", "").strip() or "neutral", place=inp.get("place", "").strip(),
               environment=inp.get("environment", "").strip(), music=inp.get("music", "").strip(),
               notes=inp.get("notes", "").strip(), date=inp.get("date") or Date.today().isoformat(),
               time_of_day=inp.get("time_of_day", "").strip(), weather=inp.get("weather", "").strip(),
               brand=inp.get("brand", "").strip())
    d = Date.fromisoformat(sc.date)
    sc.weekday = d.strftime("%A")
    region = str(persona.get("region") or "india").lower()
    sc.season, default_weather = _season(d, region)

    where = f"{sc.place} {sc.environment}"
    merged: dict = {}
    for rule in rules()["places"]:
        if hit := re.search(rule["match"], where, re.I):
            sc.matched.append(hit.group(0).strip().lower())
            for k, v in rule.items():
                if k == "match":
                    continue
                if k in LIST_KEYS:
                    merged[k] = list(dict.fromkeys((merged.get(k) or []) + v))
                else:  # most specific rule is listed first and wins
                    merged.setdefault(k, v)
    if not sc.matched:
        extra = _opus_place(sc.place, sc.environment) if sc.place else None
        if extra:
            merged, sc.source = extra, "opus"
            sc.matched.append("opus")
    base = {**rules()["default"], **merged}

    sc.settings = base.get("settings") or ["street"]
    sc.indoor = bool(base.get("indoor"))
    sc.privacy = base.get("privacy", "public")
    sc.formality = list(base.get("formality", [2, 6]))
    sc.terrain = base.get("terrain", "pavement")
    sc.footwear = base.get("footwear") or rules()["default"]["footwear"]
    terrain_shoes = {"sand": ["sandals", "slides", "barefoot"], "trail": ["sneakers", "boots", "sports"],
                     "water": ["slides", "sandals", "barefoot"]}
    if sc.terrain in terrain_shoes:  # the ground beats every other rule: no heels on sand
        sc.footwear = [f for f in sc.footwear if f in terrain_shoes[sc.terrain]] or terrain_shoes[sc.terrain]
    sc.jewelry = base.get("jewelry", "everyday")
    sc.contexts = list(base.get("contexts") or [])
    sc.preferred_faces = list(base.get("faces") or [])
    # props named in the environment text ("a big mirror", "stairs") count too
    props = set(base.get("props") or [])
    for p in ("mirror", "stairs", "chair", "table", "window", "car", "railing", "bed", "counter", "escalator", "pool", "wall", "mat"):
        if re.search(rf"\b{p}", sc.environment, re.I):
            props.add(p)
    sc.props = sorted(props)

    weather = _weather_class(f"{sc.weather} {sc.environment}", base.get("weather") or default_weather)
    sc.weather = weather if not sc.weather else f"{sc.weather} ({weather})"
    sc.lighting = _lighting(base.get("lighting", "natural daylight"), sc.time_of_day, sc.indoor)

    parts: dict = {}
    mva, _ = mood_va(sc.mood)
    if mva:
        parts["mood"] = mva
    situation_text = f"{sc.mood} {sc.environment} {sc.notes} {sc.place}"
    for s in rules()["situations"]:
        if re.search(s["match"], situation_text, re.I):
            sc.contexts = list(dict.fromkeys(sc.contexts + s.get("contexts", [])))
            if s.get("note"):
                sc.situation_notes.append(s["note"])
            if s.get("va"):
                parts["situation"] = s["va"]
    if sc.brand and "brand_trust" not in sc.contexts:
        sc.contexts.append("brand_trust")
        sc.situation_notes.append(f"{sc.brand} is in this post: only genuine expressions near the product")
    if mus := music_va(sc.music) if sc.music else None:
        parts["music"] = mus
    parts["place"] = base.get("va") or rules()["default"]["va"]
    if "mood" not in parts and "situation" not in parts:
        parts["mood"] = rules()["moods"]["neutral"]
    sc.va_parts = parts
    sc.target_va = _blend(parts)
    return sc
