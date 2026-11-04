"""LLM access layer with a deterministic offline fallback.

Set UGC_LLM_API_KEY (and optionally UGC_LLM_BASE_URL / UGC_LLM_MODEL) to
use a real model. Without it, `analyze_text` raises and engines fall back
to their heuristics so the whole pipeline still runs.
"""
from __future__ import annotations

import json
import os
import sys


class LLMUnavailable(Exception):
    pass


def _client():
    key = os.environ.get("UGC_LLM_API_KEY")
    if not key:
        raise LLMUnavailable("UGC_LLM_API_KEY not set")
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover
        raise LLMUnavailable("openai package not installed (pip install openai)") from e
    return OpenAI(
        api_key=key,
        base_url=os.environ.get("UGC_LLM_BASE_URL") or None,
    )


def analyze_text(system: str, user: str, *, expect_json: bool = True,
                 temperature: float = 0.4) -> str:
    """Single-turn completion. Raises LLMUnavailable when not configured."""
    client = _client()
    model = os.environ.get("UGC_LLM_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"} if expect_json else None,
    )
    return resp.choices[0].message.content or ""


def analyze_text_or_none(system: str, user: str, **kw) -> str | None:
    """None when unconfigured *or* when the provider fails (bad key, network,
    unsupported response_format…) — the deterministic heuristic takes over
    either way, so the pipeline never dies on an LLM hiccup."""
    try:
        return analyze_text(system, user, **kw)
    except LLMUnavailable:
        return None
    except Exception as e:
        print(f"[llm] {type(e).__name__}: {e} — heuristic fallback",
              file=sys.stderr)
        return None
