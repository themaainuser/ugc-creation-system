"""Expression Engine — what the model's face/body does on camera.

Real logic (not dummy):
- 12-expression catalog with genuine/performed flags and micro-direction.
- MDEP mood → ranked candidates; hook type boosts the primary (controversy→deadpan,
  question→genuine_smile, POV→focused_flow, etc.).
- Brand-trust reels (sponsor/betting/sex-wellness etc.) auto-ban performed emotion.
- Children-present contexts: warm only (no deadpan/smirk/edgy).
- Audio direction: tempo-matched bed; beat-drop sync note when escalation is strong.
- Primary pick via calibrated decision (not first-in-list).
"""
from __future__ import annotations

import json

from ..core import decisions, llm
from ..core.models import Expression, ExpressionPlan, MDEP, Persona

_CATALOG: dict[str, Expression] = {
    "genuine_smile": Expression("genuine_smile", True,
        "Real delight: good news, unexpected treat, payoff moments.",
        "Duchenne: cheeks lift, crow's feet, eyes soften and brighten."),
    "kind_forced_smile": Expression("kind_forced_smile", False,
        "Praising a child's first cooking attempt, polite reaction to a mediocre gift. Warmth > honesty.",
        "Mouth smiles, eyes stay gentle-not-bright; slight head tilt; soft voice. Never reads as mockery."),
    "awe": Expression("awe", True,
        "Vacation reveals, big views, product unveil, first taste.",
        "Mouth slightly open, brows up, head tilts back a touch, held breath."),
    "smirk": Expression("smirk", False,
        "Playful confidence: teaser hooks, 'wait for it' setups, bold claims.",
        "One corner of mouth up, direct camera gaze, slow blink."),
    "mischievous_grin": Expression("mischievous_grin", True,
        "Prank setups, comedy beats, playful MDEP.",
        "Teeth showing, brows wiggling, lean toward camera."),
    "focused_flow": Expression("focused_flow", True,
        "Work/study/reel middle-sections; POV hooks; makes the loop feel real.",
        "Soft gaze slightly off-camera, relaxed jaw, minimal blinking, subtle nod on beat."),
    "polite_interest": Expression("polite_interest", False,
        "Mimicked engagement through a pitch you don't believe. Honest-parody reels only.",
        "Nods are timed but eyes don't follow; smile arrives a beat late."),
    "excited_burst": Expression("excited_burst", True,
        "Unboxing, food first-bite, surprise reveals. Short duration only.",
        "Eyes wide, gasp, hands to face, fast motion."),
    "calm_content": Expression("calm_content", True,
        "Slow-lifestyle outros, gratitude captions, elegant/relaxed moods.",
        "Closed-lip smile, slow blink, shoulders down, deep exhale."),
    "deadpan": Expression("deadpan", False,
        "Comedy punchlines; contrast with upbeat audio; controversy hooks.",
        "Totally still face, unblinking stare into camera, flat mouth."),
    "surprise_wide": Expression("surprise_wide", True,
        "Plot-twist reveals, unexpected price, 'wait what' moments.",
        "Eyes wide, brows high, mouth O, head pull-back."),
    "soft_nod": Expression("soft_nod", True,
        "Agreement moments, 'exactly' payoffs, gentle outros.",
        "Slow nod, soft eye contact, closed-lip smile."),
}

_MOOD_MAP = {
    "confident": ["smirk", "genuine_smile"],
    "cozy": ["calm_content", "genuine_smile"],
    "playful": ["mischievous_grin", "excited_burst"],
    "elegant": ["calm_content", "polite_interest"],
    "edgy": ["smirk", "deadpan"],
    "relaxed": ["calm_content", "focused_flow"],
    "neutral": ["genuine_smile", "focused_flow"],
    "grateful": ["calm_content", "genuine_smile"],
    "sad": ["calm_content", "soft_nod"],
    "focused": ["focused_flow"],
}

_HOOK_BOOST = {
    "question": "genuine_smile", "bold-claim": "smirk", "controversy": "deadpan",
    "POV": "focused_flow", "visual": "awe", "pattern-interrupt": "surprise_wide",
}

_SYSTEM = """You are a performance director for AI UGC reels. Persona, MDEP, hook/verdict →
JSON {"primary": "<catalog name>", "secondary": [...], "avoid": [...],
"audio_note": "...", "rationale": "..."} Catalog keys: %s"""

_BRAND_TRUST = {"brand-deal", "sponsor", "betting", "policyprediction", "prediction-market",
                "adult-wellness", "condom", "sex-wellness", "1xbet", "stake", "4rabet",
                "polymarket", "kalshi", "adult"}


def _banned(persona: Persona, hook_text: str, verdict: str) -> tuple[list[str], list[str]]:
    avoid: list[str] = []
    reasons: list[str] = []
    banned = {t.lower() for t in persona.banned_topics}
    hook = hook_text.lower()
    if (banned & _BRAND_TRUST) or any(k in hook for k in
        ("sponsor", "betting club", "stake", "1xbet", "4rabet", "polymarket", "kalshi",
         "condom", "wellness brand", "discount code")):
        avoid += [e.name for e in _CATALOG.values() if not e.genuine]
        reasons.append("brand-trust → performed emotions banned")
    # children-present contexts must stay warm — no deadpan/smirk (spec rule)
    if "children" in hook or "kids" in hook or "child" in hook or "niece" in hook:
        avoid += ["deadpan", "smirk", "polite_interest"]
        reasons.append("children-present → warm only")
    # recreate = script is perfect; performed mimicry would break the take
    if verdict == "recreate":
        avoid += [e.name for e in _CATALOG.values() if not e.genuine]
        reasons.append("recreate → genuine only")
    return list(dict.fromkeys(avoid)), reasons


def plan(persona: Persona, mdep: MDEP, hook_text: str = "", verdict: str = "remix",
         hook_type: str = "") -> ExpressionPlan:
    candidates = _MOOD_MAP.get(mdep.mood.lower(), _MOOD_MAP["neutral"])
    boost = _HOOK_BOOST.get(hook_type, "")
    avoid, ban_reasons = _banned(persona, hook_text, verdict)

    # calibrated pick among allowed candidates
    allowed = [c for c in candidates if c not in avoid]
    if boost and boost not in avoid and boost in _CATALOG:
        allowed = [boost] + [c for c in allowed if c != boost]

    def scorer(name: str):
        s = 2.5 if name == allowed[0] else 0.6
        sigs = [f"mood:{mdep.mood}→{name}"]
        if boost == name:
            sigs.append(f"hook boost ({hook_type})")
        if name in avoid:
            s -= 4.0
            sigs.append("banned")
        return s, sigs

    d = decisions.decide("expression", [c for c in candidates if c in _CATALOG], scorer,
                         {"mood": mdep.mood, "hook_type": hook_type, "verdict": verdict})
    primary_name = d.chosen if d.chosen in _CATALOG and d.chosen not in avoid else (
        allowed[0] if allowed else candidates[0])
    primary = _CATALOG[primary_name]
    secondary = [_CATALOG[c] for c in candidates[1:] if c in _CATALOG and c != primary_name][:2] or [_CATALOG["calm_content"]]

    audio = (f"Music at '{mdep.mood}' tempo; trend audio with beat drop → sync "
             f"expression shift ({primary_name}) to the drop at payoff beat.")
    if "first-bite" in hook_text.lower() or "taste" in hook_text.lower():
        audio = "ASMR-light bed under tasting; swell to excited_burst on first bite, settle to genuine_smile."
    rationale = (f"Mood '{mdep.mood}' at {mdep.place} ({mdep.environment}) → {primary_name} "
                 f"(P={d.confidence:.2f} → {d.gate}). "
                 + (f"{'; '.join(ban_reasons)}." if ban_reasons else "Per-Verdict: remix allows deliberate mimicry; recreate demands genuine."))

    raw = llm.analyze_text_or_none(_SYSTEM % ", ".join(_CATALOG), json.dumps({
        "persona": {"name": persona.name, "voice_tone": persona.voice_tone,
                    "banned_topics": persona.banned_topics},
        "mdep": {"mood": mdep.mood, "place": mdep.place, "environment": mdep.environment},
        "hook": hook_text, "hook_type": hook_type, "verdict": verdict,
    }))
    if raw:
        try:
            data = json.loads(raw)
            if data.get("primary") in _CATALOG and data["primary"] not in avoid:
                primary = _CATALOG[data["primary"]]
            secondary = [_CATALOG[n] for n in data.get("secondary", []) if n in _CATALOG] or secondary
            avoid = list(dict.fromkeys(avoid + [a for a in data.get("avoid", []) if a in _CATALOG]))
            audio = data.get("audio_note", audio)
            rationale = data.get("rationale", rationale)
        except Exception:
            pass
    return ExpressionPlan(primary=primary, secondary=secondary, avoid=avoid,
                          audio_note=audio, rationale=rationale)


def decision(persona: Persona, mdep: MDEP, hook_text: str = "", verdict: str = "remix",
             hook_type: str = "") -> decisions.Decision:
    candidates = _MOOD_MAP.get(mdep.mood.lower(), _MOOD_MAP["neutral"])
    avoid, _ = _banned(persona, hook_text, verdict)
    boost = _HOOK_BOOST.get(hook_type, "")
    def scorer(name: str):
        s = 1.0 if name == candidates[0] else 0.6
        sig = [f"mood:{mdep.mood}"]
        if boost == name:
            sig.append(f"hook:{hook_type}")
        if name in avoid:
            s -= 2.0
            sig.append("banned")
        return s, sig
    return decisions.decide("expression", list(_CATALOG), scorer, {"mood": mdep.mood, "hook_type": hook_type})
