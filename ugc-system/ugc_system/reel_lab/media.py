"""Download a reel, probe it, and separate its audio (yt-dlp + ffmpeg)."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from ..core import proc

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


class MediaError(RuntimeError):
    pass


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise MediaError(f"`{tool}` not found on PATH — install ffmpeg "
                             "(brew install ffmpeg / apt install ffmpeg / winget install ffmpeg)")


def find_video(media_dir: Path) -> Path | None:
    for p in sorted(media_dir.glob("source.*")):
        if p.suffix.lower() in VIDEO_EXTS:
            return p
    return None


# Instagram/TikTok/YT metadata worth giving the mastermind.
_INFO_KEYS = ("title", "description", "uploader", "uploader_id", "channel",
              "duration", "view_count", "like_count", "comment_count",
              "upload_date", "track", "artist", "webpage_url", "extractor",
              "width", "height", "fps")


def download(url: str, media_dir: Path, progress=lambda msg: None) -> tuple[Path, dict]:
    """Download `url` to media_dir/source.mp4. Returns (path, metadata)."""
    try:
        import yt_dlp
    except ImportError as e:
        raise MediaError("yt-dlp not installed — run: pip install yt-dlp") from e

    def hook(d):
        if d.get("status") == "downloading":
            pct = (d.get("_percent_str") or "").strip()
            progress(f"downloading {pct}".strip())
        elif d.get("status") == "finished":
            progress("merging streams")

    opts = {
        "outtmpl": str(media_dir / "source.%(ext)s"),
        "format": "bv*[height<=1920]+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "max_filesize": 300 * 1024 * 1024,
    }
    # Instagram often needs a logged-in session: export cookies.txt or
    # point yt-dlp at your browser profile.
    if os.environ.get("UGC_COOKIES_FILE"):
        opts["cookiefile"] = os.environ["UGC_COOKIES_FILE"]
    elif os.environ.get("UGC_COOKIES_FROM_BROWSER"):
        opts["cookiesfrombrowser"] = (os.environ["UGC_COOKIES_FROM_BROWSER"],)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:  # yt-dlp raises many types
        msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e))
        hint = ""
        if "instagram" in url and re.search(r"login|cookie|rate|private|401|403", msg, re.I):
            hint = (" — Instagram wants a logged-in session: set UGC_COOKIES_FROM_BROWSER=chrome "
                    "(or UGC_COOKIES_FILE=path/to/cookies.txt) in .env, or upload the video file instead.")
        raise MediaError(f"download failed: {msg}{hint}") from e

    if info and info.get("entries"):
        info = info["entries"][0]
    video = find_video(media_dir)
    if not video:
        raise MediaError("download finished but no video file was written")
    meta = {k: info.get(k) for k in _INFO_KEYS if info and info.get(k) is not None}
    return video, meta


def probe(video: Path) -> dict:
    out = proc.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(video)],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise MediaError(f"ffprobe failed: {out.stderr.strip()[:300]}")
    data = json.loads(out.stdout or "{}")
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fps = 0.0
    if v.get("avg_frame_rate") and v["avg_frame_rate"] != "0/0":
        n, _, d = v["avg_frame_rate"].partition("/")
        fps = round(float(n) / float(d or 1), 2)
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    rot = str((v.get("tags") or {}).get("rotate") or "")
    for sd in v.get("side_data_list") or []:
        rot = str(sd.get("rotation", rot))
    if rot.strip("-") in ("90", "270"):
        w, h = h, w
    return {
        "duration": round(float(data.get("format", {}).get("duration") or v.get("duration") or 0), 2),
        "width": w, "height": h, "fps": fps,
        "aspect": f"{w}:{h}" if w and h else "",
        "has_audio": a is not None,
    }


def extract_audio(video: Path, wav: Path) -> None:
    """16 kHz mono PCM — what every speech model wants."""
    out = proc.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1",
         "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise MediaError(f"audio extraction failed: {out.stderr.strip()[:300]}")


def audio_profile(wav: Path, duration: float) -> dict:
    """Loudness + silent stretches. Lets the mastermind tell talking-head
    reels from trending-sound reels and spot beat drops / dead air."""
    out = proc.run(
        ["ffmpeg", "-v", "info", "-i", str(wav), "-af",
         "silencedetect=noise=-35dB:d=0.4,volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    err = out.stderr
    silences, start = [], None
    for line in err.splitlines():
        if m := re.search(r"silence_start: ([\d.]+)", line):
            start = float(m.group(1))
        elif (m := re.search(r"silence_end: ([\d.]+)", line)) and start is not None:
            silences.append([round(start, 2), round(float(m.group(1)), 2)])
            start = None
    if start is not None:
        silences.append([round(start, 2), round(duration, 2)])
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", err)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", err)
    silent_total = sum(b - a for a, b in silences)
    return {
        "mean_volume_db": float(mean.group(1)) if mean else None,
        "max_volume_db": float(peak.group(1)) if peak else None,
        "silences": silences[:40],
        # every silence midpoint, so long recordings can be split between words
        "cut_points": [round((a + b) / 2, 2) for a, b in silences],
        "silent_ratio": round(silent_total / duration, 3) if duration else None,
    }
