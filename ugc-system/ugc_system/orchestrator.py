"""Orchestrator — Reel + Persona + MDEP + Assets → one Content Brief.

One idea in, one shoot-ready brief out. Every major sub-choice is a calibrated
JEV decision (verdict, outfit, expression) so the operator sees P + gate, not
a black box. The brief also carries the escalation flags so a low-confidence
choice is visible before generation starts.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .core.models import ContentBrief, MDEP, Persona, Verdict
from .engines import expressions, reel_analyzer, stylist

ROOT = Path(__file__).resolve().parent.parent
USAGE_LOG = ROOT / "data" / "briefs" / "usage.log"


def escalation_list(verdict_decision=None, outfit_decision=None,
                    expression_decision=None, wardrobe_empty: bool = False) -> list[str]:
    """Operator review queue: anything gated "escalate" plus empty wardrobe.

    Single source of truth for escalation wording — build_brief and the
    bridge's plan-day both go through here (the UI re-derives the same lines
    from the *effective* decisions after operator locks).
    """
    out: list[str] = []
    for label, d in (("verdict", verdict_decision), ("outfit", outfit_decision),
                     ("expression", expression_decision)):
        if d and d.gate == "escalate":
            out.append(f"{label}: P({d.chosen})={d.confidence:.2f} → escalate")
    if wardrobe_empty:
        out.append("wardrobe: empty — scan assets before shooting")
    return out


def build_brief(persona: Persona, mdep: MDEP, transcript: str = "",
                context: str = "", idea: str = "",
                assets: list | None = None,
                mode: Verdict | None = None,
                analysis=None,
                verdict_decision=None) -> ContentBrief:
    from .core import decisions

    # 1. Reel analysis + calibrated verdict.
    # When the caller already ran the analyzer (bridge `line`/`brief` do),
    # keep the caller's verdict decision instead of dropping it — the UI's
    # Verdict JEV card, its escalation gate, and outcome scoring all read it.
    if analysis is None and transcript:
        analysis, verdict_decision = reel_analyzer.decision_for(transcript, context, persona.niche)

    effective_mode = mode or (analysis.verdict if analysis else Verdict.REMIX)

    # 2. Hook + script outline — preserves original beat text
    if effective_mode is Verdict.RECREATE and analysis:
        hook = analysis.hook.text_or_action
        outline = [f"{b.timestamp} [{b.purpose}] {b.what_happens}" for b in analysis.beats]
        ending_txt = f"ending: keep original ({analysis.ending.style}) — {analysis.ending.detail}"
    elif analysis:
        hook = (analysis.remix_ideas[0] if analysis.remix_ideas
                else f"Remix of: {analysis.hook.text_or_action}")
        body = "; ".join(f"{b.purpose} ({b.technique})" for b in analysis.beats[1:-1] or analysis.beats)
        outline = [
            f"0:00-0:03 [hook] {hook}",
            f"body: adapt beats — {body}",
            f"ending: keep original ending style ({analysis.ending.style}) — it converts.",
        ]
    else:
        hook = idea or "No hook provided — generate 3 options."
        outline = ["hook: TBD", f"body: {idea or 'TBD'}", "ending: CTA to comments"]

    if idea:
        outline.insert(1, f"operator twist: {idea}")

    # 3. Styling
    style = stylist.plan(assets or [], persona, mdep)
    outfit_decision = stylist.decision_for_chosen(assets or [], persona, mdep)

    # 4. Expressions (hook on-card so brand-trust / children rules fire)
    expr = expressions.plan(persona, mdep,
                            hook_text=hook, verdict=effective_mode.value,
                            hook_type=(analysis.hook.hook_type if analysis else ""))
    expr_decision = expressions.decision(persona, mdep, hook, effective_mode.value,
                                         analysis.hook.hook_type if analysis else "")

    # 5. Caption + hashtags — persona-truthful, niche-tagged
    caption = _caption(persona, mdep, effective_mode)
    tags = _hashtags(persona, analysis)

    # 6. Escalation flags — operator must review anything gated "escalate"
    escalations = escalation_list(verdict_decision, outfit_decision, expr_decision,
                                  wardrobe_empty=not (assets or []))

    brief = ContentBrief(
        persona_id=persona.id, mdep=mdep, mode=effective_mode,
        hook=hook, script_outline=outline, style=style,
        expressions=expr, caption_idea=caption, hashtags=tags,
    )
    # stash decisions + escalations onto the dict surface for API/UI
    brief.__dict__["decisions"] = {
        "verdict": verdict_decision.to_dict() if verdict_decision else None,
        "outfit": outfit_decision.to_dict() if outfit_decision else None,
        "expression": expr_decision.to_dict() if expr_decision else None,
    }
    brief.__dict__["escalations"] = escalations
    return brief


def _caption(persona: Persona, mdep: MDEP, mode: Verdict) -> str:
    verb = "recreating" if mode is Verdict.RECREATE else "remixing"
    return (f"{persona.name} at {mdep.place} — {mdep.mood} energy, {mdep.day}. "
            f"{verb} the reel that stopped my scroll. #UGC")


def _hashtags(persona: Persona, analysis) -> list[str]:
    tags = ["#aiugc", f"#{persona.niche.lower().replace(' ', '')}",
            f"#{persona.aesthetic.replace(' ', '').lower()}"]
    if analysis:
        tags += [f"#{t}" for t in analysis.niche_tags[:4]]
    # dedupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def log_usage(brief: ContentBrief) -> None:
    """Record worn assets for cooldown rotation (stylist diversity signal)."""
    try:
        items = list(brief.style.outfit.items)
        if brief.style.outfit.jewelry:
            items.append(brief.style.outfit.jewelry)
        if brief.style.outfit.footwear:
            items.append(brief.style.outfit.footwear)
        rec = {"date": str(date.today()), "persona": brief.persona_id,
               "assets": [Path(a.path).name for a in items]}
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
