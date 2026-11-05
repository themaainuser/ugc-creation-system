"""Run a job through: download -> audio -> transcribe -> flipbook -> mastermind.

Each stage is cached on disk, so re-running a job (or a remix job that
points at a `source_job`) skips straight to the stages that are missing.
"""
from __future__ import annotations

import json
import os
import shutil
import traceback
from pathlib import Path

from ..core.env import load_env
from . import flipbook, mastermind, media, transcribe
from .job import JOBS_DIR, Job, read_json


def _reuse_source(job: Job, source_id: str) -> None:
    """Remix of an earlier job: copy its analysis instead of redoing it."""
    src = Job(JOBS_DIR / source_id)
    if not (src.path / "job.json").exists():
        raise media.MediaError(f"source job {source_id} not found")
    for rel in ("media/info.json", "transcript.json"):
        if (src.path / rel).exists() and not (job.path / rel).exists():
            shutil.copy2(src.path / rel, job.path / rel)
    if (src.flipbook / "index.json").exists() and not (job.flipbook / "index.json").exists():
        shutil.copytree(src.flipbook, job.flipbook, dirs_exist_ok=True)
    video = media.find_video(src.media)
    if video and not media.find_video(job.media):
        dest = job.media / video.name
        try:
            os.link(video, dest)  # hardlink: no extra disk
        except OSError:
            shutil.copy2(video, dest)


def run(job_path: Path, redo: set[str] | None = None) -> dict:
    load_env()
    redo = redo or set()
    job = Job(job_path)
    spec = job.spec
    stage = "download"
    job.update(job_state="running", error=None)
    try:
        if spec.get("source_job"):
            _reuse_source(job, spec["source_job"])
        info_path = job.media / "info.json"
        info = read_json(info_path, {}) or {}

        # 1. download ---------------------------------------------------
        video = media.find_video(job.media)
        if video:
            media.require_ffmpeg()
            why = "reused from source job" if spec.get("source_job") else (
                "uploaded file" if not spec.get("url") else "cached")
            job.update("download", state="skipped", message=why)
        elif spec.get("url"):
            media.require_ffmpeg()
            job.update("download", state="running", message="contacting platform")
            video, meta = media.download(spec["url"], job.media,
                                         lambda m: job.update("download", message=m))
            info["platform"] = meta
            job.update("download", state="done", message=f"{video.stat().st_size / 1e6:.1f} MB")
        else:
            raise media.MediaError("give a reel URL or upload a video file")

        if "probe" not in info:
            info["probe"] = media.probe(video)
        info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        duration = info["probe"]["duration"]

        # 2. audio ------------------------------------------------------
        stage = "audio"
        wav = job.media / "audio.wav"
        tr_path = job.path / "transcript.json"
        need_audio = info["probe"]["has_audio"] and ("audio" not in info or (
            not tr_path.exists() or "transcribe" in redo))
        if not info["probe"]["has_audio"]:
            job.update("audio", state="skipped", message="video has no audio track")
        elif need_audio:
            job.update("audio", state="running", message="ffmpeg -> 16 kHz mono wav")
            media.extract_audio(video, wav)
            info["audio"] = media.audio_profile(wav, duration)
            info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
            sr = info["audio"].get("silent_ratio")
            job.update("audio", state="done", message=f"{duration:.1f}s" + (f" - {sr:.0%} silent" if sr is not None else ""))
        else:
            job.update("audio", state="skipped", message="cached")

        # 3. transcribe -------------------------------------------------
        stage = "transcribe"
        if tr_path.exists() and "transcribe" not in redo:
            job.update("transcribe", state="skipped", message="cached")
        elif not info["probe"]["has_audio"]:
            tr_path.write_text(json.dumps({"provider": "none", "segments": [], "note": "no audio track"}), encoding="utf-8")
            job.update("transcribe", state="skipped", message="no audio")
        else:
            job.update("transcribe", state="running", message=f"provider: {transcribe.pick_provider()}")
            tr = transcribe.transcribe(wav, lambda m: job.update("transcribe", message=m))
            tr_path.write_text(json.dumps(tr, indent=2, ensure_ascii=False), encoding="utf-8")
            words = len(tr.get("text", "").split())
            msg = tr.get("note") or f"{words} words - {tr.get('language') or '?'} - {tr['provider']}"
            job.update("transcribe", state="done" if tr["provider"] != "none" else "skipped", message=msg)
        if wav.exists() and os.environ.get("UGC_KEEP_MEDIA") != "1":
            wav.unlink()  # temp file; the transcript is what we keep

        # 4. flipbook ---------------------------------------------------
        stage = "flipbook"
        idx_path = job.flipbook / "index.json"
        if idx_path.exists() and "flipbook" not in redo:
            n = len((read_json(idx_path, {}) or {}).get("frames", []))
            job.update("flipbook", state="skipped", message=f"cached - {n} frames")
        else:
            job.update("flipbook", state="running", message="sampling keyframes")
            idx = flipbook.build(video, job.flipbook, duration, lambda m: job.update("flipbook", message=m))
            idx_path.write_text(json.dumps(idx, indent=2), encoding="utf-8")
            s = idx["stats"]
            job.update("flipbook", state="done",
                       message=f"{len(idx['frames'])} frames - {s['shots']} shots - avg {s['avg_shot_s']}s")

        # 5. mastermind -------------------------------------------------
        stage = "mastermind"
        if (job.out / "generation_prompts.md").exists() and "mastermind" not in redo:
            job.update("mastermind", state="skipped", message="cached")
        else:
            job.update("mastermind", state="running", message="building request")
            usage = mastermind.run(job, lambda m: job.update("mastermind", message=m))
            if usage.get("dry_run"):
                job.update("mastermind", state="skipped",
                           message=f"dry run - request saved ({usage['images']} images)")
            else:
                job.update("mastermind", state="done",
                           message=f"{usage['output_tokens']:,} tokens out - ~${usage['est_cost_usd']:.2f}",
                           usage=usage)

        if os.environ.get("UGC_KEEP_MEDIA") == "0" and video.exists():
            video.unlink()
        job.update(job_state="done")
    except Exception as e:  # report on the stage that failed, never crash silently
        msg = f"{type(e).__name__}: {e}" if not isinstance(
            e, (media.MediaError, transcribe.TranscribeError, mastermind.MastermindError)) else str(e)
        job.update(stage, state="error", message=msg[:600], job_state="error", error=msg[:600])
        (job.path / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
    return job.status
