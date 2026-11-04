"""Reel Analyzer — step 1: Hook → Flow → Ending → Verdict.

Real logic (not dummy):
1. Sentence-split transcript, estimate reading time at 150 wpm, map beats to timestamps.
2. Hook typing via pattern rules (question / bold-claim / POV / controversy / visual).
3. Ending typing (CTA / loop / cliffhanger / punchline / call-to-comments).
4. Structural quality scoring: beat count, escalation arc, open-loop density, payoff clarity.
5. Verdict via calibrated JEV-style decision (remix vs recreate).
6. Remix ideas derived from the weakest beat (fix hook, swap setting, invert climax...).

LLM path (when UGC_LLM_API_KEY set) improves typing; heuristic is fully deterministic offline.
"""
from __future__ import annotations

import json
import re

from ..core import decisions, llm
from ..core.models import Beat, Ending, Hook, ReelAnalysis, Verdict

SYSTEM = """You are a short-form video strategist for AI UGC influencer accounts.
Analyze the transcript below. Return JSON exactly:
{
  "hook": {"text_or_action": "...", "hook_type": "question|bold-claim|pattern-interrupt|POV|controversy|visual",
           "first_3_seconds": "...", "why_it_works": "..."},
  "beats": [{"order":1,"timestamp":"0:00-0:03","purpose":"hook|setup|escalation|payoff|CTA",
             "what_happens":"...","technique":"..."}],
  "ending": {"style":"CTA|loop|cliffhanger|punchline|call-to-comments","detail":"...","loop_close":true},
  "niche_tags": ["..."],
  "verdict": "remix|recreate",
  "verdict_reason": "one sentence",
  "remix_ideas": ["3 concrete alternatives"]
}
'recreate' only if script/structure is essentially perfect."""

# ---- pattern rules -----------------------------------------------------

_HOOK_RULES: list[tuple[str, re.Pattern]] = [
    ("question", re.compile(r"\?\s*$|^(what|why|how|when|where|is|do|did|have|can|would|could)\b", re.I)),
    ("bold-claim", re.compile(r"\b(best|worst|never|always|secret|truth|stop|insane|crazy|unbelievable|expensive|viral|hacked)\b", re.I)),
    ("POV", re.compile(r"^(pov|me when|nobody:|day in the life)", re.I)),
    ("controversy", re.compile(r"\b(unpopular opinion|hot take|people hate|nobody talks|wrong about)\b", re.I)),
    ("visual", re.compile(r"^\[|\(.*(camera|close.?up|shot|shows?|reveals?|opens? with)", re.I)),
]

_ENDING_RULES: list[tuple[str, re.Pattern]] = [
    ("cliffhanger", re.compile(r"(part two|part 2|continued|next video|see what happens|wait for)", re.I)),
    ("call-to-comments", re.compile(r"(comment|reply|tell me|what do you think|drop in|tag)", re.I)),
    ("CTA", re.compile(r"(follow|subscribe|link in bio|check out|book|buy|shop|try it|join|click)", re.I)),
    ("punchline", re.compile(r"(!|\?)\s*$", re.I)),
    ("loop", re.compile(r"(again|same thing|rewind|loop)", re.I)),
]

_NICHE_KEYWORDS = {
    "fashion": ["dress", "outfit", "style", "brand", "prada", "gucci", "hermes", "looks", "thrift", "skims"],
    "travel": ["vacation", "flight", "hotel", "beach", "trip", "goa", "dubai", "bali", "travel"],
    "food": ["food", "recipe", "cook", "restaurant", "taste", "dish", "cafe", "coffee", "cooking"],
    "comedy": ["funny", "joke", "prank", "lol", "comedy", "roast"],
    "tech": ["phone", "gadget", "app", "ai", "laptop", "review", "tech", "iphone", "android"],
    "adult_wellness": ["condom", "wellness", "intimacy", "sex"],
    "betting": ["stake", "1xbet", "4rabet", "polymarket", "kalshi", "bet", "odds", "prediction"],
    "dance": ["dance", "choreo", "bpm", "beat"],
    "lifestyle": ["day in the life", "morning", "routine", "grwm", "vlog"],
}


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _type_hook(first: str) -> tuple[str, str]:
    for name, rx in _HOOK_RULES:
        if rx.search(first):
            reasons = {
                "question": "Direct question creates an open information gap the viewer must close.",
                "bold-claim": "Strong claim signals payoff and triggers curiosity + mild disagreement.",
                "POV": "POV format puts the viewer inside the scene instantly.",
                "controversy": "Controversial frame invites comment-bait and watch-time.",
                "visual": "Visual-first opening interrupts the scroll pattern before a word is read.",
            }
            return name, reasons[name]
    return "pattern-interrupt", "Abrupt opener breaks the feed's prediction; forces a stop-and-watch."


def _type_ending(last: str) -> tuple[str, str, bool]:
    for name, rx in _ENDING_RULES:
        if rx.search(last):
            return name, f"Detected {name} signal: “{last[:80]}”", name in ("loop", "call-to-comments")
    return "punchline", "Final line lands as a closer — no explicit CTA detected.", False


def _estimate_seconds(sentences: list[str]) -> int:
    words = sum(len(s.split()) for s in sentences)
    return max(6, min(90, round(words / 2.5)))  # ~150 wpm


def _fmt(t: int) -> str:
    return f"0:{t:02d}" if t < 60 else f"{t // 60}:{t % 60:02d}"


def _build_beats(sentences: list[str], total_sec: int) -> list[Beat]:
    n = len(sentences)
    if n == 0:
        sentences = ["(empty transcript)"]
        n = 1
    # distribute sentences across 5-beat arc proportionally
    beats: list[Beat] = []
    if n == 1:
        beats = [Beat(1, "0:00-0:03", "hook", sentences[0], "single-line reel treated as hook"),
                 Beat(2, f"0:03-0:{total_sec:02d}", "payoff", sentences[0], "no escalation possible")]
        return beats
    # chunk boundaries: hook=first, setup=next 20%, escalation=next 40%, payoff=next, CTA=last
    hook_end = 1
    setup_end = max(hook_end + 1, round(n * 0.30))
    esc_end = max(setup_end + 1, round(n * 0.75))
    span = total_sec / max(1, n)
    def ts(i0: int, i1: int) -> str:
        return f"{_fmt(int(i0 * span))}-{_fmt(int(i1 * span))}"
    def chunk(i0: int, i1: int) -> str:
        return " ".join(sentences[i0:i1])
    beats = [
        Beat(1, ts(0, hook_end), "hook", chunk(0, hook_end), "first-line pattern interrupt"),
        Beat(2, ts(hook_end, setup_end), "setup", chunk(hook_end, setup_end), "context + open loop"),
        Beat(3, ts(setup_end, esc_end), "escalation", chunk(setup_end, esc_end) or sentences[-2], "stakes rise / new info"),
        Beat(4, ts(esc_end, max(n - 1, esc_end + 1)), "payoff", chunk(esc_end, max(n - 1, esc_end + 1)) or sentences[-1], "payoff line"),
        Beat(5, ts(max(n - 1, esc_end + 1), n), "CTA", sentences[-1], "close / loop / CTA"),
    ]
    return beats


def _structural_score(sentences: list[str], beats: list[Beat]) -> tuple[float, str]:
    """0..1 quality score from deterministic signals."""
    score = 0.0
    # 1. beat count in sweet spot (4-6 beats)
    if 4 <= len(beats) <= 6:
        score += 0.20
    elif len(beats) >= 2:
        score += 0.10
    # 2. length sweet spot (15-45s)
    words = sum(len(s.split()) for s in sentences)
    if 35 <= words <= 115:
        score += 0.20
    elif words < 20 or words > 180:
        score += 0.05
    else:
        score += 0.12
    # 3. escalation language (but/then/wait/suddenly/actually)
    text = " ".join(sentences).lower()
    esc_words = sum(1 for w in ("but", "then", "wait", "suddenly", "actually", "however", "next") if w in text)
    score += min(0.20, esc_words * 0.05)
    # 4. question hooks score higher (open loop)
    htype, _ = _type_hook(sentences[0]) if sentences else ("", "")
    if htype in ("question", "bold-claim", "controversy"):
        score += 0.20
    elif htype == "pattern-interrupt":
        score += 0.10
    # 5. ending strength (CTA/cliffhanger > plain)
    etype, _, _ = _type_ending(sentences[-1]) if sentences else ("", "", False)
    if etype in ("cliffhanger", "loop", "call-to-comments", "CTA"):
        score += 0.20
    else:
        score += 0.08
    return min(1.0, score), f"structure={score:.2f} (beats={len(beats)}, words={words})"


def _hook_score(first: str) -> float:
    htype, _ = _type_hook(first)
    base = {"question": 0.85, "bold-claim": 0.88, "controversy": 0.82, "POV": 0.75,
            "visual": 0.70, "pattern-interrupt": 0.55}.get(htype, 0.5)
    # short hooks (≤12 words) are punchier
    if len(first.split()) <= 12:
        base += 0.08
    return min(1.0, base)


def _niche_tags(text: str) -> list[str]:
    low = text.lower()
    return [tag for tag, kws in _NICHE_KEYWORDS.items() if any(k in low for k in kws)] or ["general"]


def _remix_ideas(weakness: str, persona_niche: str, text: str) -> list[str]:
    ideas = {
        "hook": [
            "Invert the hook: show the payoff first, then rewind to the setup.",
            "Add a text-on-screen overlay: the hook line + 'wait for 0:07' open loop.",
            "Open mid-scene (in medias res) instead of starting with the intro line.",
        ],
        "escalation": [
            "Insert a beat-drop moment at the escalation — new camera angle or cut.",
            "Change location mid-reel for the escalation beat only.",
            "Swap in a trending audio and sync the payoff to the drop.",
        ],
        "ending": [
            "Turn the ending into a loop: final frame echoes the opening pose.",
            "End on a question to comments instead of a statement.",
            "Cliffhanger variant: tease part two with a visual hint.",
        ],
        "structure": [
            "Keep the same beats — change the location while holding the structure.",
            "Swap persona voice tone (deadpan vs excited) on the same script.",
            "Add a B-roll insert between setup and escalation.",
        ],
    }
    chosen = ideas.get(weakness, ideas["structure"])
    # tailor first idea to persona niche if fashion/travel/food detected
    if "fashion" in persona_niche.lower():
        chosen[0] = "Re-shoot the hook in a thrift store — same line, new setting contrast."
    if "travel" in persona_niche.lower():
        chosen[0] = "Start the hook at the destination, rewind to explain how we got there."
    return chosen


def _heuristic(transcript: str, context: str, persona_niche: str = "") -> ReelAnalysis:
    sentences = _split_sentences(transcript)
    first = sentences[0] if sentences else transcript[:80]
    htype, why = _type_hook(first)
    total = _estimate_seconds(sentences)
    beats = _build_beats(sentences, total)
    etype, edetail, loop = _type_ending(sentences[-1]) if sentences else ("CTA", "", False)

    hs = _hook_score(first)
    ss, sdetail = _structural_score(sentences, beats)
    # weakest link drives remix ideas
    weakness = "hook" if hs < 0.65 else ("ending" if etype == "punchline" else ("escalation" if ss < 0.55 else "structure"))

    def scorer(name: str):
        if name == "recreate":
            s = hs * 0.5 + ss * 0.5 - 0.25  # needs BOTH high
            return s, [f"hook={hs:.2f}", f"structure={ss:.2f}", sdetail if name == "recreate" else ""]
        s = 1.0 - (hs * 0.5 + ss * 0.5)
        return s, [f"gap_hook={1 - hs:.2f}", f"gap_structure={1 - ss:.2f}"]

    d = decisions.decide("verdict", ["remix", "recreate"], scorer,
                         {"hook_score": round(hs, 2), "structure_score": round(ss, 2), "context": context})
    final_verdict = Verdict(d.chosen)
    reason = d.rationale
    if final_verdict == Verdict.RECREATE and (hs < 0.80 or ss < 0.75):
        # hard guardrails: never recreate a weak reel even if model is confident
        final_verdict = Verdict.REMIX
        reason = f"Guardrail: hook={hs:.2f}/structure={ss:.2f} below recreate bar (0.80/0.75). " + reason

    return ReelAnalysis(
        source=transcript[:80],
        hook=Hook(first, htype, why, f"0:00-0:03 — {first}"),
        beats=beats,
        ending=Ending(etype, edetail, loop),
        verdict=final_verdict,
        verdict_reason=reason,
        user_context=context,
        remix_ideas=_remix_ideas(weakness, persona_niche, transcript),
        niche_tags=_niche_tags(transcript),
    )


def analyze(transcript: str, context: str = "", persona_niche: str = "") -> ReelAnalysis:
    user = (f"User context (why this fits a persona): {context or '(none)'}\n\n"
            f"Persona niche: {persona_niche or 'lifestyle'}\n\nTranscript:\n{transcript}")
    raw = llm.analyze_text_or_none(SYSTEM, user)
    if raw:
        try:
            data = json.loads(raw)
            h, e = data["hook"], data["ending"]
            return ReelAnalysis(
                source=transcript[:60], hook=Hook(**h),
                beats=[Beat(**b) for b in data["beats"]],
                ending=Ending(**e), verdict=Verdict(data["verdict"]),
                verdict_reason=data.get("verdict_reason", ""), user_context=context,
                remix_ideas=data.get("remix_ideas", []), niche_tags=data.get("niche_tags", []),
            )
        except Exception as e:
            import sys
            print(f"[reel_analyzer] LLM output unusable ({type(e).__name__}: {e})"
                  f" — heuristic fallback", file=sys.stderr)
    return _heuristic(transcript, context, persona_niche)


def decision_for(transcript: str, context: str = "", persona_niche: str = "") -> tuple[ReelAnalysis, decisions.Decision]:
    """Full analysis + calibrated verdict decision (for UI/API exposure)."""
    analysis = analyze(transcript, context, persona_niche)
    sentences = _split_sentences(transcript)
    first = sentences[0] if sentences else ""
    hs = _hook_score(first)
    ss, _ = _structural_score(sentences, _build_beats(sentences, _estimate_seconds(sentences)))
    def scorer(name: str):
        if name == "recreate":
            return hs * 0.5 + ss * 0.5 - 0.25, [f"hook={hs:.2f}", f"structure={ss:.2f}"]
        return 1.0 - (hs * 0.5 + ss * 0.5), [f"hook_gap={1 - hs:.2f}"]
    d = decisions.decide("verdict", ["remix", "recreate"], scorer, {"hook": round(hs, 2), "structure": round(ss, 2)})
    return analysis, d
