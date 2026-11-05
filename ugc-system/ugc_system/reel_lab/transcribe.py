"""Speech → timestamped transcript.

Providers (UGC_TRANSCRIBE=auto|local|groq|openai|none):
  local   faster-whisper on this machine (free; UGC_WHISPER_MODEL=small)
  groq    whisper-large-v3 on Groq (GROQ_API_KEY) — fastest
  openai  whisper-1 on OpenAI (OPENAI_API_KEY)
auto = local if faster-whisper is installed, else groq, else openai.

Hosted APIs (Groq, OpenAI) cap uploads at 25 MB, so before uploading the
audio is re-encoded to a small speech format (16 kHz mono Opus at 32 kbps,
falling back to MP3, then FLAC): about 0.2 MB a minute instead of WAV's
1.9 MB. If that is still over 24 MB (~110 minutes) it is split into
~10-minute chunks with 1.5 s of overlap, cut at silences where possible.
Each chunk is transcribed, its timestamps are shifted by the chunk's start,
and lines repeated in the overlaps are dropped.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

MAX_UPLOAD = 24 * 1024 * 1024  # bytes; above this we split (keeps a margin under the limit)
API_LIMIT = 25 * 1024 * 1024   # what Groq / OpenAI actually refuse
CHUNK_SECONDS = 600.0          # ~10 minutes per chunk
OVERLAP = 1.5                  # seconds shared by neighbouring chunks
SILENCE_LOOKBACK = 90.0        # how far before the ideal cut we look for a silence
MATCH_TOL = 0.5                # seconds of slack when comparing lines near a boundary
# Smallest first. Every one of these is accepted by both Groq and OpenAI.
ENCODINGS = [
    ("libopus", ".ogg", ["-c:a", "libopus", "-b:a", "32k", "-application", "voip"]),
    ("libmp3lame", ".mp3", ["-c:a", "libmp3lame", "-b:a", "32k"]),
    ("flac", ".flac", ["-c:a", "flac", "-compression_level", "8"]),
]


class TranscribeError(RuntimeError):
    pass


def _have_local() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def pick_provider() -> str:
    choice = (os.environ.get("UGC_TRANSCRIBE") or "auto").lower()
    if choice != "auto":
        return choice
    if _have_local():
        return "local"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "none"


def _local(wav: Path, progress) -> dict:
    from faster_whisper import WhisperModel

    size = os.environ.get("UGC_WHISPER_MODEL", "small")
    progress(f"loading whisper-{size} (first run downloads the model)")
    model = WhisperModel(size, device=os.environ.get("UGC_WHISPER_DEVICE", "auto"),
                         compute_type=os.environ.get("UGC_WHISPER_COMPUTE", "int8"))
    segments, info = model.transcribe(str(wav), vad_filter=True, word_timestamps=True,
                                      beam_size=5)
    segs = []
    for s in segments:
        segs.append({
            "start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
            "words": [{"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word.strip()}
                      for w in (s.words or [])],
        })
        progress(f"transcribed to {s.end:.1f}s")
    return {"provider": f"local/faster-whisper-{size}", "language": info.language,
            "language_probability": round(info.language_probability, 3), "segments": segs}


# ------------------------------------------------------------- encoding
@lru_cache(maxsize=1)
def _encoders() -> str:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    return out.stdout


def encode_speech(src: Path, dest_stem: Path, start: float | None = None,
                  length: float | None = None) -> Path:
    """16 kHz mono speech file (optionally a slice of `src`), smallest codec first."""
    available = _encoders()
    for codec, ext, args in ENCODINGS:
        if codec not in available:
            continue
        out = dest_stem.with_suffix(ext)
        cmd = ["ffmpeg", "-y", "-v", "error"]
        if start:
            cmd += ["-ss", f"{start:.3f}"]
        cmd += ["-i", str(src)]
        if length:
            cmd += ["-t", f"{length:.3f}"]
        cmd += ["-vn", "-ac", "1", "-ar", "16000", *args, str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
    raise TranscribeError("ffmpeg could not encode the audio (needs libopus, libmp3lame or flac)")


def _duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError as e:
        raise TranscribeError(f"could not read the audio length: {r.stderr.strip()[:200]}") from e


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


# ------------------------------------------------------------- chunking
def plan_chunks(duration: float, target: float = CHUNK_SECONDS, overlap: float = OVERLAP,
                cut_points: list[float] | None = None, lookback: float = SILENCE_LOOKBACK) -> list[tuple[float, float]]:
    """[(start, end)] covering 0..duration. Each chunk ends at the latest silence
    within `lookback` seconds before its ideal end (else at the ideal end), and the
    next chunk starts `overlap` seconds earlier so no word is lost at a cut."""
    cuts = sorted(cut_points or [])
    min_tail = min(30.0, target / 4)  # don't leave a few-second scrap at the end
    spans: list[tuple[float, float]] = []
    start = 0.0
    while True:
        ideal = start + target
        if ideal >= duration - min_tail:
            spans.append((round(start, 3), round(duration, 3)))
            return spans
        near = [c for c in cuts if ideal - lookback <= c <= ideal and c > start + overlap + 1]
        end = near[-1] if near else ideal
        spans.append((round(start, 3), round(end, 3)))
        start = end - overlap


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _same_line(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na or SequenceMatcher(None, na, nb).ratio() >= 0.8


def _shift(seg: dict, offset: float) -> dict:
    return {**seg,
            "start": round(seg["start"] + offset, 2), "end": round(seg["end"] + offset, 2),
            "words": [{**w, "start": round(w["start"] + offset, 2), "end": round(w["end"] + offset, 2)}
                      for w in seg.get("words") or []]}


def merge_chunks(results: list[tuple[float, float, list[dict]]]) -> list[dict]:
    """results: [(chunk_start, chunk_end, segments with chunk-relative times)].

    Shifts every segment to absolute time. A segment that starts inside the
    overlap with the previous chunk and repeats a line already kept near that
    boundary is dropped; if the new copy is longer (the old one was cut off at
    the chunk edge), the longer text replaces it. Repeats outside an overlap
    (a chorus, a catchphrase) are kept.
    """
    merged: list[dict] = []
    prev_end: float | None = None
    for chunk_start, chunk_end, segs in results:
        for seg in (_shift(s, chunk_start) for s in segs):
            if prev_end is not None and seg["start"] < prev_end + MATCH_TOL:
                dup = next((m for m in reversed(merged)
                            if m["end"] > chunk_start - MATCH_TOL and _same_line(m["text"], seg["text"])), None)
                if dup is not None:
                    if len(_norm(seg["text"])) > len(_norm(dup["text"])):
                        dup["text"], dup["words"] = seg["text"], seg.get("words") or []
                    dup["start"] = min(dup["start"], seg["start"])
                    dup["end"] = max(dup["end"], seg["end"])
                    continue
            merged.append(seg)
        prev_end = chunk_end
    return sorted(merged, key=lambda s: s["start"])


# ------------------------------------------------------------- hosted APIs
def _api_client(provider: str):
    try:
        from openai import OpenAI
    except ImportError as e:
        raise TranscribeError("openai package not installed (pip install openai)") from e
    if provider == "groq":
        return (OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1"),
                os.environ.get("UGC_WHISPER_MODEL_API", "whisper-large-v3"))
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"]), os.environ.get("UGC_WHISPER_MODEL_API", "whisper-1")


def _api_file(client, model: str, path: Path) -> dict:
    """One upload -> {"language", "segments"} with times relative to the file."""
    with open(path, "rb") as f:
        r = client.audio.transcriptions.create(model=model, file=f, response_format="verbose_json",
                                               timestamp_granularities=["segment"])
    data = r.model_dump() if hasattr(r, "model_dump") else dict(r)
    segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2),
             "text": s["text"].strip(), "words": []} for s in data.get("segments") or []]
    if not segs and data.get("text"):
        segs = [{"start": 0.0, "end": float(data.get("duration") or 0), "text": data["text"].strip(), "words": []}]
    return {"language": data.get("language"), "segments": segs}


def _api(wav: Path, provider: str, progress, duration: float | None = None,
         cut_points: list[float] | None = None) -> dict:
    client, model = _api_client(provider)
    tmp = wav.parent / "upload_tmp"
    tmp.mkdir(exist_ok=True)
    try:
        progress("encoding audio for upload (16 kHz mono)")
        full = encode_speech(wav, tmp / "audio")
        size = full.stat().st_size
        fmt = full.suffix.lstrip(".")
        if size <= MAX_UPLOAD:
            progress(f"uploading {size / 1e6:.1f} MB {fmt} to {provider}")
            res = _api_file(client, model, full)
            segs, language, n = res["segments"], res["language"], 1
        else:
            duration = duration or _duration(wav)
            spans = plan_chunks(duration, CHUNK_SECONDS, OVERLAP, cut_points,
                                lookback=min(SILENCE_LOOKBACK, CHUNK_SECONDS / 3))
            full.unlink(missing_ok=True)
            results, language = [], None
            for i, (a, b) in enumerate(spans, 1):
                progress(f"chunk {i}/{len(spans)} · {_clock(a)}–{_clock(b)} → {provider}")
                part = encode_speech(wav, tmp / f"chunk_{i:03d}", start=a, length=b - a)
                if part.stat().st_size > API_LIMIT:
                    raise TranscribeError(f"chunk {i} is still {part.stat().st_size / 1e6:.0f} MB after encoding")
                res = _api_file(client, model, part)
                part.unlink(missing_ok=True)
                language = language or res["language"]
                results.append((a, b, res["segments"]))
            progress(f"merging {len(spans)} chunks")
            segs, n = merge_chunks(results), len(spans)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"provider": f"{provider}/{model}", "language": language, "segments": segs,
            "upload": {"format": fmt, "bytes": size, "chunks": n}}


def transcribe(wav: Path, progress=lambda m: None, *, duration: float | None = None,
               cut_points: list[float] | None = None) -> dict:
    """cut_points: silence midpoints (seconds) from the audio profile, used to
    place chunk boundaries when a long recording has to be split."""
    provider = pick_provider()
    if provider == "none":
        return {"provider": "none", "language": None, "segments": [],
                "note": "No transcriber configured — pip install faster-whisper, or set GROQ_API_KEY / OPENAI_API_KEY."}
    try:
        result = (_local(wav, progress) if provider == "local"
                  else _api(wav, provider, progress, duration=duration, cut_points=cut_points))
    except TranscribeError:
        raise
    except Exception as e:
        raise TranscribeError(f"{provider} transcription failed: {type(e).__name__}: {e}") from e
    result["text"] = " ".join(s["text"] for s in result["segments"]).strip()
    return result


def as_timed_text(tr: dict) -> str:
    """'[00.0–02.4] line' — what the mastermind reads."""
    lines = [f"[{s['start']:05.1f}–{s['end']:05.1f}] {s['text']}" for s in tr.get("segments") or []]
    return "\n".join(lines)
