"""JSON-in/JSON-out bridge for the Next.js UI.

Commands:
  personas            → {"personas":[...]}
  assets              → {"assets":[...]}
  scan {"folder":..}  → {"count":n,"by_category":{...}}
  analyze {...}       → {analysis, decision}
  brief {...}         → ContentBrief (with decisions + escalations)
  plan-day {...}      → {style, expressions, decisions}
  line {...}          → {analysis, decision, brief}
  health              → {"ok":true,"jev":bool,"llm":bool,"assets":n,"personas":n}
  outcome {...}       → log Brier-scored outcome, returns {"brier":x}
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ugc_system.core.models import MDEP, Persona, Verdict
from ugc_system.core import decisions
from ugc_system.engines import asset_library, expressions, stylist, reel_analyzer
from ugc_system.orchestrator import build_brief, escalation_list, log_usage, escalation_list

PERSONAS_DIR = ROOT / "personas"
INDEX_PATH = ROOT / "assets" / "index.json"
OUTCOME_LOG = ROOT / "data" / "decisions" / "outcomes.jsonl"

def _persona(pid: str) -> Persona:
    p = PERSONAS_DIR / f"{pid}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"persona '{pid}' not found")
    return Persona.from_dict(yaml.safe_load(p.read_text(encoding="utf-8")))

def _mdep(d: dict | None) -> MDEP:
    d = d or {}
    return MDEP(mood=d.get("mood","neutral"), day=d.get("day","casual weekday"),
                environment=d.get("environment","home"), place=d.get("place","home"))

def _assets():
    return asset_library.load_index(INDEX_PATH) if INDEX_PATH.exists() else []

def _clean(obj):
    from dataclasses import asdict, is_dataclass
    if is_dataclass(obj): obj = asdict(obj)
    if isinstance(obj, dict): return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_clean(v) for v in obj]
    if isinstance(obj, str) and obj.startswith(str(ROOT)):
        return obj[len(str(ROOT))+1:].replace("\\","/")
    return obj

def handle(cmd: str, payload: dict):
    if cmd == "personas":
        out = []
        for p in sorted(PERSONAS_DIR.glob("*.yaml")):
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            d["id"] = p.stem
            out.append(d)
        return {"personas": out}

    if cmd == "assets":
        return {"assets": _clean(_assets())}

    if cmd == "health":
        import os
        return {"ok": True,
                "jev": bool(os.environ.get("JEV_BASE_URL")),
                "llm": bool(os.environ.get("UGC_LLM_API_KEY")),
                "assets": len(_assets()),
                "personas": len(list(PERSONAS_DIR.glob("*.yaml")))}

    if cmd == "scan":
        assets = asset_library.scan(payload["folder"])
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        asset_library.save_index(assets, INDEX_PATH)
        by = {}
        for a in assets: by[a.category] = by.get(a.category, 0) + 1
        return {"count": len(assets), "by_category": by}

    if cmd == "analyze":
        analysis, dec = reel_analyzer.decision_for(payload["transcript"], payload.get("context",""),
                                                   payload.get("persona_niche",""))
        return {"analysis": _clean(analysis), "decision": dec.to_dict()}

    if cmd == "plan-day":
        persona = _persona(payload["persona"]); mdep = _mdep(payload.get("mdep"))
        # Pass the current hook/verdict context so expressions keep honoring
        # brand-trust / children / recreate bans during MDEP re-dress.
        hook_text = payload.get("hook_text", "")
        verdict = payload.get("verdict", "remix")
        hook_type = payload.get("hook_type", "")
        style = stylist.plan(_assets(), persona, mdep)
        expr = expressions.plan(persona, mdep, hook_text=hook_text,
                                verdict=verdict, hook_type=hook_type)
        outfit_d = stylist.decision_for_chosen(_assets(), persona, mdep)
        expr_d = expressions.decision(persona, mdep, hook_text, verdict, hook_type)
        return {"style": _clean(style), "expressions": _clean(expr),
                "decisions": {"outfit": _clean(outfit_d), "expression": _clean(expr_d)},
                "escalations": escalation_list(
                    None, outfit_d, expr_d, wardrobe_empty=not _assets())}

    if cmd in ("brief", "line"):
        persona = _persona(payload["persona"]); mdep = _mdep(payload.get("mdep"))
        transcript = payload.get("transcript",""); context = payload.get("context","")
        mode = Verdict(payload["mode"]) if payload.get("mode") else None
        analysis = dec = None
        if transcript:
            analysis, dec = reel_analyzer.decision_for(transcript, context, persona.niche)
        brief = build_brief(persona, mdep, transcript=transcript, context=context,
                            idea=payload.get("idea",""), assets=_assets(), mode=mode,
                            analysis=analysis, verdict_decision=dec)
        if payload.get("log", True):
            log_usage(brief)
        out = {"brief": _clean(brief), "analysis": _clean(analysis) if analysis else None}
        return out

    if cmd == "outcome":
        # payload: {verb, chosen, confidence, gate, outcome}
        pseudo = decisions.Decision(verb=payload.get("verb",""), options=[],
                                    chosen=payload.get("chosen",""),
                                    confidence=float(payload.get("confidence",0.5)),
                                    gate=payload.get("gate","automate"),
                                    rationale="", brier_estimate=0.0)
        # rebuild options from payload if present
        if payload.get("options"):
            from ugc_system.core.decisions import OptionScore
            pseudo.options = [OptionScore(o["name"], o.get("raw",0.0), o.get("p",0.0), o.get("signals",[])) for o in payload["options"]]
        rec = decisions.save_outcome(OUTCOME_LOG, pseudo, payload.get("outcome",""))
        return {"brier": rec["brier"], "record": rec}

    raise ValueError(f"unknown command '{cmd}'")

def main():
    for s in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"): s.reconfigure(encoding="utf-8", errors="replace")
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else ""
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        json.dump(handle(cmd, payload), sys.stdout, ensure_ascii=False)
    except Exception as e:
        json.dump({"error": f"{type(e).__name__}: {e}"}, sys.stdout, ensure_ascii=False)
    sys.stdout.flush()

if __name__ == "__main__":
    main()
