"""CLI (every command prints JSON on stdout for the UI):
  python -m ugc_system.styling scan
  python -m ugc_system.styling tag [--force]
  python -m ugc_system.styling plan --persona aria --mood cozy --place "home" --environment "bedroom, big mirror" \
        --music "lofi" --notes "wearing the shell necklace my niece made" [--shots 3] [--opus] [--date 2026-11-05]
  python -m ugc_system.styling feedback <look-id> approve|reject|swap|posted [--alt 2] [--rating 4]
  python -m ugc_system.styling looks [--persona aria]
  python -m ugc_system.styling show <look-id>
  python -m ugc_system.styling learning --persona aria
"""
from __future__ import annotations

import argparse
import json
import sys

from ..core.env import load_env


def main(argv=None) -> int:
    load_env()
    ap = argparse.ArgumentParser(prog="styling")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    t = sub.add_parser("tag")
    t.add_argument("--force", action="store_true")
    p = sub.add_parser("plan")
    p.add_argument("--persona", required=True)
    for k in ("mood", "place", "environment", "music", "notes", "date", "time", "weather", "brand"):
        p.add_argument(f"--{k}", default="")
    p.add_argument("--shots", type=int, default=3)
    p.add_argument("--opus", action="store_true", help="Opus art director picks from the shortlist")
    p.add_argument("--seed", type=int)
    p.add_argument("--json", action="store_true", help="read the inputs as JSON from stdin")
    f = sub.add_parser("feedback")
    f.add_argument("look")
    f.add_argument("verdict", choices=["approve", "reject", "swap", "posted"])
    f.add_argument("--alt", type=int)
    f.add_argument("--rating", type=int)
    f.add_argument("--engagement", type=float)
    f.add_argument("--baseline", type=float)
    f.add_argument("--note", default="")
    l = sub.add_parser("looks")
    l.add_argument("--persona")
    s = sub.add_parser("show")
    s.add_argument("look")
    g = sub.add_parser("learning")
    g.add_argument("--persona", required=True)
    a = ap.parse_args(argv)

    from . import planner, wardrobe
    try:
        if a.cmd == "scan":
            items = wardrobe.load()
            root, demo = wardrobe.source_dir()
            out = {"items": items, "demo": demo, "folder": str(root)}
        elif a.cmd == "tag":
            out = wardrobe.tag(force=a.force, progress=lambda m: print(m, file=sys.stderr))
        elif a.cmd == "plan":
            if a.json:
                data = json.load(sys.stdin)
                out = planner.plan(data.pop("persona"), data, shots=int(data.pop("shots", 3)),
                                   art_director=bool(data.pop("opus", False)))
            else:
                inputs = {"mood": a.mood, "place": a.place, "environment": a.environment, "music": a.music,
                          "notes": a.notes, "date": a.date or None, "time_of_day": a.time, "weather": a.weather, "brand": a.brand}
                out = planner.plan(a.persona, inputs, shots=a.shots, art_director=a.opus, seed=a.seed)
        elif a.cmd == "feedback":
            out = planner.feedback(a.look, a.verdict, alt=a.alt, rating=a.rating, engagement=a.engagement,
                                   baseline=a.baseline, note=a.note)
        elif a.cmd == "looks":
            out = {"looks": planner.list_looks(a.persona)}
        elif a.cmd == "show":
            out = json.loads(planner.path_for(a.look).read_text(encoding="utf-8"))
        else:
            L = planner.learners(a.persona)
            out = {k: {"calibration": v.calibration(), "weights": dict(zip(v.features, [round(float(w), 3) for w in v.mean]))}
                   for k, v in L.items()}
    except (planner.PlanError, Exception) as e:  # the UI shows this message
        print(json.dumps({"error": f"{e}" if isinstance(e, planner.PlanError) else f"{type(e).__name__}: {e}"}))
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
