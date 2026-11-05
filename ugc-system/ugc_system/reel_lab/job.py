"""A Reel Lab job = one folder under data/jobs/<id>/.

    job.json        inputs (url, persona, context, idea, assets, options)
    status.json     live per-stage progress, read by the UI
    media/          downloaded video, audio.wav, info.json   (temp media)
    transcript.json timestamped speech
    flipbook/       timestamped keyframes + index.json + sheet.jpg
    assets/         files the user uploaded (character refs, outfits, ...)
    out/            reel_flow.md, generation_prompts.md, blueprint.json
"""
from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from ..core.env import ROOT

JOBS_DIR = ROOT / "data" / "jobs"
STAGES = ["download", "audio", "transcribe", "flipbook", "mastermind"]
STAGE_LABELS = {
    "download": "Download reel",
    "audio": "Separate audio",
    "transcribe": "Transcribe speech",
    "flipbook": "Flipbook visuals",
    "mastermind": "Opus mastermind",
}


def new_job_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)  # atomic, so the UI never reads half a file


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


class Job:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.media = self.path / "media"
        self.flipbook = self.path / "flipbook"
        self.assets = self.path / "assets"
        self.out = self.path / "out"
        for d in (self.media, self.flipbook, self.assets, self.out):
            d.mkdir(parents=True, exist_ok=True)

    # ---- inputs -------------------------------------------------------
    @classmethod
    def create(cls, spec: dict, jobs_dir: Path = JOBS_DIR) -> "Job":
        job_id = spec.get("id") or new_job_id()
        job = cls(jobs_dir / job_id)
        spec = {**spec, "id": job_id,
                "created_at": datetime.now(timezone.utc).isoformat()}
        _write_json(job.path / "job.json", spec)
        job.reset_status()
        return job

    @property
    def id(self) -> str:
        return self.path.name

    @property
    def spec(self) -> dict:
        return read_json(self.path / "job.json", {}) or {}

    # ---- status -------------------------------------------------------
    def reset_status(self) -> None:
        _write_json(self.path / "status.json", {
            "state": "queued",
            "error": None,
            "updated_at": time.time(),
            "stages": {s: {"state": "pending", "message": "", "label": STAGE_LABELS[s]}
                       for s in STAGES},
        })

    @property
    def status(self) -> dict:
        return read_json(self.path / "status.json", {}) or {}

    def update(self, stage: str | None = None, *, state: str | None = None,
               message: str | None = None, job_state: str | None = None,
               error: str | None | object = ..., **extra) -> None:
        st = self.status or {"stages": {}}
        if stage:
            s = st["stages"].setdefault(stage, {"label": STAGE_LABELS.get(stage, stage)})
            if state:
                if state == "running" and s.get("state") != "running":
                    s["started_at"] = time.time()
                if state in ("done", "skipped", "error"):
                    s["finished_at"] = time.time()
                s["state"] = state
            if message is not None:
                s["message"] = message
            s.update(extra)
        if job_state:
            st["state"] = job_state
        if error is not ...:
            st["error"] = error
        st["updated_at"] = time.time()
        _write_json(self.path / "status.json", st)

    def write_json(self, rel: str, data) -> Path:
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        _write_json(p, data)
        return p
