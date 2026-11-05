"""The Mastermind: Claude Opus 5.5 watches the flipbook, reads the
transcript, and writes the two production documents.

Provider (UGC_MASTERMIND_PROVIDER=auto|anthropic|openrouter):
  anthropic   official Anthropic SDK, ANTHROPIC_API_KEY, model claude-opus-5-5
  openrouter  OPEN_ROUTER_API_KEY, model anthropic/claude-opus-5.5
auto = anthropic when ANTHROPIC_API_KEY is set, else openrouter.
UGC_MASTERMIND_DRY_RUN=1 writes the exact request to out/request_preview.md
without calling (and without spending) anything.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from ..core import fsutil, opus
from ..core.env import ROOT
from .transcribe import as_timed_text

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


MastermindError = opus.OpusError


SYSTEM = """You are the Mastermind of an AI UGC studio that runs AI-generated influencer accounts (male, female and gender-neutral personas). You combine three crafts:
1. Short-form retention analyst: you can explain, second by second, why a reel stops the scroll, holds attention and gets rewatched, shared or commented on.
2. Creative director: you transplant a proven reel's essence onto a new persona and a new idea without making a cheap copy.
3. Generative-media prompt engineer: you write prompts that image models (Nano Banana, Flux, Midjourney, Seedream, GPT-Image) and video models (Kling, Veo, Sora, Runway, Seedance, Hailuo) can execute shot by shot with a consistent character.

HOW YOU WATCH THE REEL
You receive the reel as a flipbook: keyframes in time order, each labelled with its timestamp and why it was sampled (hook window = every 0.5s of the first 3s; cut = a scene change / new shot; coverage = even sampling; end = final frame). You also get the timestamped transcript, an audio profile and platform metadata.
- Read on-screen text exactly as written (copy, emoji, casing).
- Infer motion between consecutive frames (camera moves, gestures, transitions, zoom punches); mark inferences with "(inferred)".
- Never invent dialogue that is not in the transcript. If there is no speech, the audio is most likely a trending sound or music; say so and describe its role.
- Be specific. "Good lighting" is useless; "soft window light camera-left, warm 3200K practicals in background" is useful.

ESSENCE
The essence is what makes the reel work independent of its topic: the hook mechanism, the tension -> payoff structure, pacing, the emotional turn, the format (POV, skit, storytime, GRWM, tutorial, before/after, list, reaction...), and the ending mechanic. The new reel keeps the essence and changes topic, setting, wardrobe and surface details to fit the persona and the operator's idea.
- mode "remix": new idea, same essence. If the operator gave no idea, choose the strongest idea for this persona yourself and say why.
- mode "recreate": keep the script and beat structure nearly verbatim; only swap the creator for the persona and adapt surroundings/wardrobe.

RULES FOR GENERATION PROMPTS
- Character consistency: define the persona's look once as a CHARACTER BLOCK and reuse it in every shot. If a character reference image was uploaded, write "use reference: <filename>" rather than re-describing the face.
- Every shot gets (a) an image prompt for the still / first frame, (b) a video prompt that describes subject action, camera movement, lens and framing, lighting, and a duration of 3-10s that a video model can actually render, (c) a negative prompt.
- Prompts are concrete visual description (subject, wardrobe, pose, expression, setting, light, lens, color grade, 9:16) - never marketing language.
- On-screen text and graphics are NOT baked into generated footage; specify them separately as edit overlays (exact copy, font style, color, position, animation, in/out time).
- Expressions: label each one genuine or performed. A performed emotion is never allowed in a brand-trust / sponsor moment.
- Map every asset: uploaded by the operator -> reference it by filename; missing -> write a prompt to generate it.
- Keep it platform-safe: for adult-wellness or betting brands, imply rather than show; no nudity, no minors; include the required disclosure (#ad, 18+, play responsibly).
- Put every prompt inside a ```text fenced block so it can be copied in one click.

OUTPUT FORMAT
Reply with exactly three tagged sections and nothing outside them.

<reel_flow>
Markdown document that explains how the SOURCE reel flows. Sections:
# Reel Flow - <short title>
## Snapshot - table: creator, platform, duration, aspect, shot count, avg shot length, speech vs sound, format, niche
## The essence - one paragraph, then a one-line formula (e.g. "Relatable pain -> absurd escalation -> self-own punchline -> loop")
## Hook teardown (0-3s) - first frame, visual hook, text hook, verbal hook, audio hook, the psychological trigger, why it stops the scroll
## Beat-by-beat timeline - table: Time | Beat | What we see (shot, framing, camera, action) | On-screen text / graphics | Audio (VO, SFX, music) | Retention job
## Graphics & text system - caption style, fonts, colors, placement, animation, stickers/emoji, overlays, transitions
## Editing rhythm & camera language - cut cadence, where pace changes, camera moves, light, color grade
## Audio design
## Performance & expressions - delivery, genuine vs performed moments
## The ending - type (loop / CTA / punchline / cliffhanger / comment bait) and the mechanic that drives rewatch/share/comment
## Why it fits this persona - tie to the operator's context
## Keep vs change - table
</reel_flow>

<generation_prompts>
Markdown document for producing the NEW reel. Sections:
# Generation Prompts - <new title>
## Concept - logline, mode, how the essence is kept, what changes and why
## Character block - the persona's reusable look description (or reference file)
## Asset list - table: ID | Asset | Type (character/outfit/location/prop/product/graphic/audio) | Source (uploaded filename or GENERATE) | Used in shots
## Asset generation prompts - one ```text block per GENERATE asset, plus negative prompt
## Script - timed VO / dialogue lines with delivery notes
## Shot list - for each shot: "### Shot N - <start>-<end>s - <beat>" then Purpose, Image prompt (```text), Video prompt (```text), Negative prompt, Camera, Expression (genuine/performed + why), On-screen overlay, Audio, Assets used, Transition out
## Graphics & text overlays - edit spec in time order
## Audio & music
## Assembly notes - edit order, timings, caption burn-in, export settings (1080x1920, 30fps)
## All-in-one prompt - a single ```text prompt for models that render multi-shot clips from references
## Caption, hashtags & posting notes
</generation_prompts>

<blueprint>
Strict JSON (no comments, no trailing commas):
{"title": str, "essence": str, "formula": str, "mode": "remix"|"recreate", "duration_s": number,
 "source_beats": [{"t_start": number, "t_end": number, "beat": str, "what_happens": str, "on_screen_text": str, "audio": str, "retention_job": str}],
 "new_concept": {"logline": str, "hook_line": str, "why_it_works": str},
 "assets": [{"id": str, "name": str, "type": str, "source": "uploaded:<filename>"|"generate", "prompt": str}],
 "shots": [{"n": int, "t_start": number, "t_end": number, "beat": str, "image_prompt": str, "video_prompt": str, "negative_prompt": str, "camera": str, "expression": str, "expression_mode": "genuine"|"performed", "on_screen_text": str, "voiceover": str, "audio": str, "uses_assets": [str], "transition_out": str}],
 "caption": str, "hashtags": [str]}
</blueprint>"""


# ---------------------------------------------------------------- inputs
def _persona_text(pid: str | None) -> str:
    if not pid:
        return "(no persona selected - write for a generic AI creator and say so)"
    p = ROOT / "personas" / f"{pid}.yaml"
    return p.read_text(encoding="utf-8") if p.exists() else f"(persona '{pid}' not found)"


def build_request(job) -> dict:
    """Provider-neutral request: system text + ordered list of parts."""
    spec = job.spec
    info = json.loads((job.media / "info.json").read_text()) if (job.media / "info.json").exists() else {}
    probe = info.get("probe", {})
    tr = json.loads((job.path / "transcript.json").read_text()) if (job.path / "transcript.json").exists() else {}
    fb = json.loads((job.flipbook / "index.json").read_text()) if (job.flipbook / "index.json").exists() else {"frames": []}
    targets = spec.get("targets") or {}
    assets = spec.get("assets") or []

    platform_meta = {k: v for k, v in (info.get("platform") or {}).items()}
    asset_lines = "\n".join(
        f"- {Path(a['file']).name} - kind: {a.get('kind') or 'other'} - note: {a.get('label') or '-'}"
        for a in assets) or "- none uploaded: every asset must be generated"
    timed = as_timed_text(tr) or "(no speech detected - likely trending sound / music only)"

    brief = f"""# Operator brief
Mode: {spec.get('mode') or 'remix'}
Target image model: {targets.get('image') or 'any (model-agnostic prompts)'}
Target video model: {targets.get('video') or 'any (model-agnostic prompts)'}

## Persona
{_persona_text(spec.get('persona'))}

## Why this reel fits the persona (operator's context)
{spec.get('context') or '(not given - infer it)'}

## Idea / twist
{spec.get('idea') or '(not given - propose the strongest idea for this persona)'}

## Operator-uploaded assets
{asset_lines}

# Source reel
Source: {spec.get('url') or 'uploaded file'}
Platform metadata (caption, creator, counts, sound): {json.dumps(platform_meta, ensure_ascii=False)}
Video: {probe.get('duration')}s, {probe.get('width')}x{probe.get('height')}, {probe.get('fps')} fps
Edit stats: {json.dumps(fb.get('stats') or {})}
Scene cuts at (s): {fb.get('scene_cuts') or []}
Audio profile: {json.dumps({k: v for k, v in (info.get('audio') or {}).items() if k != 'cut_points'})}

## Transcript ({tr.get('provider', 'n/a')}, language: {tr.get('language') or 'n/a'})
{timed}

## Flipbook ({len(fb['frames'])} frames, in time order)"""

    parts: list[dict] = [{"type": "text", "text": brief}]
    kind_label = {"hook": "hook window", "cut": "scene cut", "coverage": "coverage", "end": "final frame"}
    for f in fb["frames"]:
        why = kind_label.get(f["kind"], f["kind"]) + (", scene cut" if f.get("cut") and f["kind"] != "cut" else "")
        parts.append({"type": "text", "text": f"Frame {f['n']} - t={f['t']:.2f}s - {why}"})
        parts.append({"type": "image", "path": str(job.flipbook / f["file"])})

    imgs = [a for a in assets if Path(a["file"]).suffix.lower() in IMAGE_EXTS]
    if imgs:
        parts.append({"type": "text", "text": "# Operator assets (reference by filename)"})
        for a in imgs:
            parts.append({"type": "text", "text": f"Asset {Path(a['file']).name} - {a.get('kind') or 'other'} - {a.get('label') or ''}"})
            parts.append({"type": "image", "path": str(job.path / a["file"])})

    parts.append({"type": "text", "text": "Now write the three sections: <reel_flow>, <generation_prompts>, <blueprint>."})
    return {"system": SYSTEM, "parts": parts}


# ---------------------------------------------------------------- providers
# ---------------------------------------------------------------- output
def split_sections(text: str) -> dict:
    out = {}
    for tag in ("reel_flow", "generation_prompts", "blueprint"):
        m = re.search(rf"<{tag}>\s*(.*?)\s*(?:</{tag}>|\Z)", text, re.S)
        out[tag] = m.group(1).strip() if m else ""
    bp = re.sub(r"^```(?:json)?\s*|\s*```$", "", out["blueprint"]).strip()
    try:
        out["blueprint_json"] = json.loads(bp) if bp else None
    except json.JSONDecodeError:
        out["blueprint_json"] = None
    return out


def preview_markdown(req: dict) -> str:
    lines = ["# Mastermind request preview", "", "## System", "", req["system"], "", "## User content", ""]
    for p in req["parts"]:
        lines.append(p["text"] if p["type"] == "text" else f"![frame]({Path(p['path']).name})")
        lines.append("")
    return "\n".join(lines)


def run(job, progress=lambda m: None) -> dict:
    req = build_request(job)
    n_img = sum(1 for p in req["parts"] if p["type"] == "image")
    fsutil.write_text(job.out / "request_preview.md", preview_markdown(req))
    if os.environ.get("UGC_MASTERMIND_DRY_RUN") == "1":
        return {"dry_run": True, "images": n_img}

    provider = opus.pick_provider()
    progress(f"sending {n_img} images to {provider}")
    partial = job.out / "partial.md"
    buf: list[str] = []
    last = [0.0]

    def on_text(t: str):
        buf.append(t)
        now = time.time()
        if now - last[0] > 1.2:
            last[0] = now
            try:  # live preview only: skip a beat if OneDrive/antivirus holds the file
                partial.write_text("".join(buf), encoding="utf-8")
            except OSError:
                pass
            progress(f"writing - {sum(map(len, buf)) / 1000:.1f}k chars")

    res = opus.complete(req, on_text, max_tokens=64000)
    text = res["text"]
    fsutil.write_text(job.out / "raw_response.md", text)
    fsutil.remove(partial)

    sec = split_sections(text)
    if not sec["reel_flow"] and not sec["generation_prompts"]:
        raise MastermindError("model reply had no <reel_flow>/<generation_prompts> sections - see out/raw_response.md")
    fsutil.write_text(job.out / "reel_flow.md", sec["reel_flow"])
    fsutil.write_text(job.out / "generation_prompts.md", sec["generation_prompts"])
    if sec["blueprint_json"] is not None:
        fsutil.write_text(job.out / "blueprint.json", json.dumps(sec["blueprint_json"], indent=2, ensure_ascii=False))

    cost = res["est_cost_usd"]
    usage = {"provider": provider, "model": res["model"], "stop_reason": res["stop_reason"],
             "images": n_img, "input_tokens": res["input_tokens"],
             "output_tokens": res["output_tokens"], "est_cost_usd": round(cost, 4),
             "blueprint_ok": sec["blueprint_json"] is not None}
    job.write_json("out/usage.json", usage)
    return usage
