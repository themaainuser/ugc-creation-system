"""CLI for the UGC system.

Commands:
  init                         scaffold folders + example persona
  scan-assets <folder>         index clothing/jewelry images → assets/index.json
  analyze <transcript>         hook/flow/ending breakdown of a reel
  plan-day                     outfit + pose + expressions for today's post
  brief <transcript>           full content brief (reel + style + expressions)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows consoles default to cp1252; force UTF-8 so box-drawing output works.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import yaml

from .core.models import Gender, MDEP, Persona, Verdict
from .engines import asset_library, expressions, reel_analyzer, stylist
from .orchestrator import build_brief

ROOT = Path(__file__).resolve().parent.parent
PERSONAS_DIR = ROOT / "personas"
INDEX_PATH = ROOT / "assets" / "index.json"

EXAMPLE_PERSONA = {
    "id": "aria", "name": "Aria", "gender": "female", "age_range": "22-26",
    "niche": "fashion", "aesthetic": "clean minimal",
    "brand_tier": ["Skims", "Zara", "thrift"],
    "jewelry_style": "delicate gold, occasional handmade piece",
    "voice_tone": "warm, dry humor", "follower_style": "best-friend energy",
    "banned_topics": [], "notes": "Example persona — edit me.",
}


def _load_persona(pid: str) -> Persona:
    path = PERSONAS_DIR / f"{pid}.yaml"
    if not path.exists():
        available = sorted(p.stem for p in PERSONAS_DIR.glob("*.yaml"))
        sys.exit(f"Persona '{pid}' not found. Available: {available}")
    return Persona.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))


def _load_assets() -> list:
    if INDEX_PATH.exists():
        return asset_library.load_index(INDEX_PATH)
    print("No asset index found (run `scan-assets`) — styling with empty wardrobe.")
    return []


def cmd_init(_args) -> None:
    for d in ("personas", "assets/clothing", "assets/jewelry",
              "assets/footwear", "data/transcripts", "data/briefs"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    p = PERSONAS_DIR / "aria.yaml"
    if not p.exists():
        p.write_text(yaml.safe_dump(EXAMPLE_PERSONA, sort_keys=False),
                     encoding="utf-8")
    print("Scaffolded. Edit personas/aria.yaml, dump images into assets/, "
          "then run `scan-assets`.")


def cmd_scan_assets(args) -> None:
    assets = asset_library.scan(args.folder)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    asset_library.save_index(assets, INDEX_PATH)
    by_cat: dict[str, int] = {}
    for a in assets:
        by_cat[a.category] = by_cat.get(a.category, 0) + 1
    print(f"Indexed {len(assets)} assets → {INDEX_PATH}")
    print("By category:", json.dumps(by_cat))


def _mdep_from_args(args) -> MDEP:
    return MDEP(
        mood=getattr(args, "mood", "neutral"),
        day=getattr(args, "day", "casual weekday"),
        environment=getattr(args, "environment", "home"),
        place=getattr(args, "place", "home"),
    )


def _print(obj) -> None:
    print(json.dumps(obj.__dict__ if hasattr(obj, "__dict__") else obj,
                     indent=2, default=str))


def cmd_analyze(args) -> None:
    transcript = Path(args.transcript).read_text(encoding="utf-8") \
        if Path(args.transcript).exists() else args.transcript
    analysis = reel_analyzer.analyze(transcript, context=args.context or "")
    print("── HOOK " + "─" * 60)
    print(f"{analysis.hook.hook_type}: {analysis.hook.text_or_action}")
    print(f"Why it works: {analysis.hook.why_it_works}")
    print("── FLOW " + "─" * 60)
    for b in analysis.beats:
        print(f"  {b.timestamp} [{b.purpose}] {b.what_happens}  ({b.technique})")
    print("── ENDING " + "─" * 58)
    print(f"  {analysis.ending.style}: {analysis.ending.detail}  loop={analysis.ending.loop_close}")
    print("── VERDICT " + "─" * 56)
    print(f"  {analysis.verdict.value}: {analysis.verdict_reason}")
    for i, idea in enumerate(analysis.remix_ideas, 1):
        print(f"  remix {i}: {idea}")


def cmd_plan_day(args) -> None:
    persona = _load_persona(args.persona)
    mdep = _mdep_from_args(args)
    style = stylist.plan(_load_assets(), persona, mdep)
    expr = expressions.plan(persona, mdep)
    print("── STYLE " + "─" * 58)
    for item in style.outfit.items:
        print(f"  outfit: {Path(item.path).name} "
              f"[{item.category} {','.join(item.brands) or '-'}]")
    if style.outfit.jewelry:
        print(f"  jewelry: {Path(style.outfit.jewelry.path).name}")
    if style.outfit.footwear:
        print(f"  footwear: {Path(style.outfit.footwear.path).name}")
    print(f"  rationale: {style.outfit.rationale}")
    print(f"  poses: {', '.join(style.pose.poses)}")
    print(f"  shot: {style.pose.shot_notes}")
    print("── EXPRESSIONS " + "─" * 52)
    print(f"  primary: {expr.primary.name} ({'genuine' if expr.primary.genuine else 'performed'})")
    print(f"  secondary: {', '.join(e.name for e in expr.secondary)}")
    print(f"  avoid: {', '.join(expr.avoid) or '-'}")
    print(f"  audio: {expr.audio_note}")


def cmd_brief(args) -> None:
    persona = _load_persona(args.persona)
    mdep = _mdep_from_args(args)
    transcript = ""
    if args.transcript and Path(args.transcript).exists():
        transcript = Path(args.transcript).read_text(encoding="utf-8")
    elif args.transcript:
        transcript = args.transcript
    brief = build_brief(persona, mdep, transcript,
                        context=args.context or "", idea=args.idea or "",
                        assets=_load_assets(),
                        mode=Verdict(args.mode) if args.mode else None)
    out = ROOT / "data" / "briefs" / f"{persona.id}_brief.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(brief.to_dict(), indent=2, default=str),
                   encoding="utf-8")
    print(f"── CONTENT BRIEF ({brief.mode.value}) " + "─" * 40)
    print(f"HOOK: {brief.hook}")
    print("SCRIPT:")
    for line in brief.script_outline:
        print(f"  • {line}")
    print(f"STYLE: {brief.style.outfit.rationale}")
    print(f"  poses: {', '.join(brief.style.pose.poses)}")
    print(f"EXPRESSION: {brief.expressions.primary.name} — {brief.expressions.rationale}")
    print(f"CAPTION: {brief.caption_idea} {' '.join(brief.hashtags)}")
    print(f"\nSaved → {out}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="ugc_system",
                                 description="AI UGC influencer content engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)

    p = sub.add_parser("scan-assets")
    p.add_argument("folder")
    p.set_defaults(func=cmd_scan_assets)

    p = sub.add_parser("analyze")
    p.add_argument("transcript", help="file path or raw transcript text")
    p.add_argument("--context", help="why this reel fits your influencer")
    p.set_defaults(func=cmd_analyze)

    def add_mdep(p):
        p.add_argument("--persona", required=True)
        p.add_argument("--mood", default="neutral")
        p.add_argument("--day", default="casual weekday")
        p.add_argument("--environment", default="home")
        p.add_argument("--place", default="home")

    p = sub.add_parser("plan-day")
    add_mdep(p)
    p.set_defaults(func=cmd_plan_day)

    p = sub.add_parser("brief")
    p.add_argument("transcript", nargs="?", help="reel transcript file or text")
    add_mdep(p)
    p.add_argument("--context", help="why the reel is good for this influencer")
    p.add_argument("--idea", help="your twist on the reel")
    p.add_argument("--mode", choices=["remix", "recreate"],
                   help="override the auto verdict")
    p.set_defaults(func=cmd_brief)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
