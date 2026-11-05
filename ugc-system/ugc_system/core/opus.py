"""Shared Claude Opus 5.5 access for every engine (Reel Lab, stylist, wardrobe tagger).

Provider (UGC_MASTERMIND_PROVIDER=auto|anthropic|openrouter):
  anthropic   official Anthropic SDK, ANTHROPIC_API_KEY, model claude-opus-5-5
  openrouter  OPEN_ROUTER_API_KEY, model anthropic/claude-opus-5.5
auto = anthropic when ANTHROPIC_API_KEY is set, else openrouter.

A request is {"system": str, "parts": [{"type": "text", "text": ...} |
{"type": "image", "path": ...}]}, so callers never touch provider formats.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path

from PIL import Image

PRICE = {"input": 4.0, "output": 20.0}  # USD per 1M tokens, Opus 5.5


class OpusError(RuntimeError):
    pass


def _b64_image(path: Path, long_side: int = 1280) -> tuple[str, str]:
    """Re-encode to JPEG under a size cap (keeps the request small)."""
    img = Image.open(path)
    img = img.convert("RGB") if img.mode not in ("RGB",) else img
    if max(img.size) > long_side:
        img.thumbnail((long_side, long_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return "image/jpeg", base64.standard_b64encode(buf.getvalue()).decode()


def pick_provider() -> str:
    forced = (os.environ.get("UGC_MASTERMIND_PROVIDER") or "auto").lower()
    if forced != "auto":
        return forced
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPEN_ROUTER_API_KEY") or os.environ.get("UGC_LLM_API_KEY"):
        return "openrouter"
    raise OpusError("No model key: set ANTHROPIC_API_KEY or OPEN_ROUTER_API_KEY in ugc-system/.env")


def _call_anthropic(req: dict, on_text, max_tokens: int, effort: str) -> dict:
    try:
        import anthropic
    except ImportError as e:
        raise OpusError("anthropic package not installed (pip install anthropic)") from e
    blocks = []
    for p in req["parts"]:
        if p["type"] == "text":
            blocks.append({"type": "text", "text": p["text"]})
        else:
            mt, data = _b64_image(Path(p["path"]))
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}})
    model = os.environ.get("UGC_MASTERMIND_MODEL", "claude-opus-5-5")
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        system=[{"type": "text", "text": req["system"], "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": blocks}],
        # Server-side fallback: if a safety classifier declines (e.g. on an
        # adult-wellness brief), the API retries on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
    ) as stream:
        for text in stream.text_stream:
            on_text(text)
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise OpusError(f"model declined the request ({getattr(msg, 'stop_details', None)})")
    text = "".join(b.text for b in msg.content if b.type == "text")
    u = msg.usage
    return {"text": text, "model": msg.model, "stop_reason": msg.stop_reason,
            "input_tokens": u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0),
            "output_tokens": u.output_tokens}


def _call_openrouter(req: dict, on_text, max_tokens: int, effort: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise OpusError("openai package not installed (pip install openai)") from e
    key = os.environ.get("OPEN_ROUTER_API_KEY") or os.environ.get("UGC_LLM_API_KEY")
    base = (os.environ.get("OPEN_ROUTER_BASE_URL") or "https://openrouter.ai/api/v1")
    base = re.sub(r"/chat/completions/?$", "", base)
    model = os.environ.get("UGC_MASTERMIND_MODEL", "anthropic/claude-opus-5.5")
    content = []
    for p in req["parts"]:
        if p["type"] == "text":
            content.append({"type": "text", "text": p["text"]})
        else:
            mt, data = _b64_image(Path(p["path"]))
            content.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64,{data}"}})
    client = OpenAI(api_key=key, base_url=base, timeout=900)
    stream = client.chat.completions.create(
        model=model, max_tokens=max_tokens, stream=True,
        messages=[{"role": "system", "content": req["system"]}, {"role": "user", "content": content}],
        extra_body={"reasoning": {"effort": effort},
                    "usage": {"include": True}},
    )
    chunks, usage, finish = [], None, None
    for ev in stream:
        if getattr(ev, "usage", None):
            usage = ev.usage
        if ev.choices:
            d = ev.choices[0].delta
            if d and d.content:
                chunks.append(d.content)
                on_text(d.content)
            finish = ev.choices[0].finish_reason or finish
    return {"text": "".join(chunks), "model": model, "stop_reason": finish,
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0}


def available() -> bool:
    try:
        pick_provider()
        return True
    except OpusError:
        return False


def complete(req: dict, on_text=lambda t: None, *, max_tokens: int = 64000,
             effort: str | None = None) -> dict:
    """Stream one Opus reply. Returns text, model, stop_reason, tokens, est_cost_usd, provider."""
    provider = pick_provider()
    effort = effort or os.environ.get("UGC_MASTERMIND_EFFORT", "high")
    call = _call_anthropic if provider == "anthropic" else _call_openrouter
    res = call(req, on_text, max_tokens, effort)
    res["provider"] = provider
    res["est_cost_usd"] = round(res["input_tokens"] / 1e6 * PRICE["input"]
                                + res["output_tokens"] / 1e6 * PRICE["output"], 4)
    return res


def extract_json(text: str):
    """First JSON object/array in a reply (tolerates ```json fences and prose)."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = m.group(1) if m else text
    start = min([i for i in (body.find("{"), body.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise OpusError("reply contained no JSON")
    depth, in_str, esc = 0, False, False
    opener = body[start]
    closer = "}" if opener == "{" else "]"
    for i, ch in enumerate(body[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0 and ch == closer:
                return json.loads(body[start:i + 1])
    raise OpusError("reply JSON was cut off")
