"""CLI:
  python -m ugc_system.reel_lab new --url URL --persona aria --idea "..." --context "..." [--run]
  python -m ugc_system.reel_lab new --video clip.mp4 --asset face.png:character:"Aria face ref" --run
  python -m ugc_system.reel_lab run <job-id> [--redo mastermind,flipbook,transcribe]
  python -m ugc_system.reel_lab list
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .job import JOBS_DIR, Job
from . import pipeline


def _job_path(ref: str) -> Path:
    p = Path(ref)
    return p if p.exists() else JOBS_DIR / ref


def health() -> dict:
    import importlib.util as iu
    import os
    from ..core.env import load_env
    from ..core import opus
    from . import mastermind, transcribe
    load_env()
    try:
        mm = opus.pick_provider()
    except opus.OpusError:
        mm = None
    return {
        "ffmpeg": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        "ytdlp": iu.find_spec("yt_dlp") is not None,
        "transcriber": transcribe.pick_provider(),
        "mastermind": mm,
        "mastermind_model": os.environ.get("UGC_MASTERMIND_MODEL") or (
            "claude-opus-5-5" if mm == "anthropic" else "anthropic/claude-opus-5.5"),
        "sdk": {"anthropic": iu.find_spec("anthropic") is not None,
                "openai": iu.find_spec("openai") is not None},
        "dry_run": os.environ.get("UGC_MASTERMIND_DRY_RUN") == "1",
        "personas": _personas(),
    }


def _personas() -> list[dict]:
    import yaml
    from ..core.env import ROOT
    out = []
    for f in sorted((ROOT / "personas").glob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        out.append({k: d.get(k) for k in ("id", "name", "gender", "niche", "aesthetic", "voice_tone")}
                   | {"id": d.get("id") or f.stem})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="reel_lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="create a job")
    n.add_argument("--url")
    n.add_argument("--video", help="local video file instead of a URL")
    n.add_argument("--persona")
    n.add_argument("--mode", choices=["remix", "recreate"], default="remix")
    n.add_argument("--context", default="", help="why this reel fits the persona")
    n.add_argument("--idea", default="", help="your idea / twist")
    n.add_argument("--image-model", default="")
    n.add_argument("--video-model", default="")
    n.add_argument("--asset", action="append", default=[], help="path[:kind[:label]]")
    n.add_argument("--source-job", help="reuse analysis from an earlier job")
    n.add_argument("--run", action="store_true")
    r = sub.add_parser("run", help="run / resume a job")
    r.add_argument("job")
    r.add_argument("--redo", default="", help="comma list of stages to force")
    sub.add_parser("list")
    sub.add_parser("health", help="which tools / keys are ready (JSON)")
    a = ap.parse_args(argv)

    if a.cmd == "health":
        print(json.dumps(health()))
        return 0

    if a.cmd == "list":
        for d in sorted(JOBS_DIR.glob("*/job.json"), reverse=True)[:30]:
            j = Job(d.parent)
            print(f"{j.id}  {j.status.get('state', '?'):8}  {j.spec.get('persona') or '-':8}  {j.spec.get('url') or 'upload'}")
        return 0

    if a.cmd == "new":
        if not (a.url or a.video or a.source_job):
            ap.error("give --url, --video or --source-job")
        assets = []
        for raw in a.asset:
            path, _, rest = raw.partition(":")
            kind, _, label = rest.partition(":")
            assets.append({"src": path, "kind": kind or "other", "label": label})
        job = Job.create({
            "url": a.url, "persona": a.persona, "mode": a.mode, "context": a.context,
            "idea": a.idea, "source_job": a.source_job,
            "targets": {"image": a.image_model, "video": a.video_model}, "assets": [],
        })
        if a.video:
            shutil.copy2(a.video, job.media / f"source{Path(a.video).suffix.lower()}")
        spec = job.spec
        for x in assets:
            dest = job.assets / Path(x["src"]).name
            shutil.copy2(x["src"], dest)
            spec["assets"].append({"file": f"assets/{dest.name}", "kind": x["kind"], "label": x["label"]})
        job.write_json("job.json", spec)
        print(job.id)
        if not a.run:
            return 0
        path = job.path
    else:
        path = _job_path(a.job)

    status = pipeline.run(path, redo={s for s in a.redo.split(",") if s} if a.cmd == "run" else None)
    for name, s in status["stages"].items():
        print(f"  {s['state']:8} {name:11} {s.get('message', '')}", file=sys.stderr)
    print(json.dumps({"id": path.name, "state": status["state"], "error": status.get("error")}))
    return 0 if status["state"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
