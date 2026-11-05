"""Speech → timestamped transcript.

Providers (UGC_TRANSCRIBE=auto|local|groq|openai|none):
  local   faster-whisper on this machine (free; UGC_WHISPER_MODEL=small)
  groq    whisper-large-v3 on Groq (GROQ_API_KEY) — fastest
  openai  whisper-1 on OpenAI (OPENAI_API_KEY)
auto = local if faster-whisper is installed, else groq, else openai.
"""
from __future__ import annotations

import os
from pathlib import Path


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


def _api(wav: Path, provider: str, progress) -> dict:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise TranscribeError("openai package not installed (pip install openai)") from e
    if provider == "groq":
        client = OpenAI(api_key=os.environ["GROQ_API_KEY"],
                        base_url="https://api.groq.com/openai/v1")
        model = os.environ.get("UGC_WHISPER_MODEL_API", "whisper-large-v3")
    else:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        model = os.environ.get("UGC_WHISPER_MODEL_API", "whisper-1")
    progress(f"uploading audio to {provider}")
    with open(wav, "rb") as f:
        r = client.audio.transcriptions.create(model=model, file=f,
                                               response_format="verbose_json",
                                               timestamp_granularities=["segment"])
    data = r.model_dump() if hasattr(r, "model_dump") else dict(r)
    segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2),
             "text": s["text"].strip(), "words": []} for s in data.get("segments") or []]
    if not segs and data.get("text"):
        segs = [{"start": 0.0, "end": float(data.get("duration") or 0), "text": data["text"].strip(), "words": []}]
    return {"provider": f"{provider}/{model}", "language": data.get("language"), "segments": segs}


def transcribe(wav: Path, progress=lambda m: None) -> dict:
    provider = pick_provider()
    if provider == "none":
        return {"provider": "none", "language": None, "segments": [],
                "note": "No transcriber configured — pip install faster-whisper, or set GROQ_API_KEY / OPENAI_API_KEY."}
    try:
        result = _local(wav, progress) if provider == "local" else _api(wav, provider, progress)
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
