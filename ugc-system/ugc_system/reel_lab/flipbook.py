"""Flipbook: turn a reel into a timestamped sequence of keyframes.

The mastermind "watches" the reel by flipping through these frames in
order. Frame selection:
  * hook window   — every 0.5s for the first 3s (the scroll-stop moment)
  * scene cuts    — ffmpeg scene-change detection (every edit / new shot)
  * coverage      — an even sample of the rest of the reel
  * last frame    — how the reel ends (loop / CTA / punchline)
capped at UGC_FLIPBOOK_MAX frames (default 48).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from ..core import fsutil, proc

HOOK_WINDOW = 3.0
MIN_GAP = 0.35  # seconds; closer frames are near-duplicates


def scene_cuts(video: Path, threshold: float = 0.27) -> list[float]:
    out = proc.run(
        ["ffmpeg", "-v", "info", "-i", str(video), "-an", "-vf",
         f"select='gt(scene,{threshold})',showinfo", "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True)
    return [round(float(m.group(1)), 2) for m in re.finditer(r"pts_time:([\d.]+)", out.stderr)]


def plan_timestamps(duration: float, cuts: list[float], max_frames: int) -> list[dict]:
    if duration <= 0:
        return [{"t": 0.0, "kind": "hook"}]
    end = max(0.0, duration - 0.15)
    picks: list[dict] = []
    t = 0.0
    while t <= min(HOOK_WINDOW, end):
        picks.append({"t": round(t, 2), "kind": "hook"})
        t += 0.5
    picks += [{"t": c, "kind": "cut"} for c in cuts if 0 < c < end]
    picks.append({"t": round(end, 2), "kind": "end"})

    budget = max_frames - len(picks)
    if budget > 0:
        step = max(0.75, (end - HOOK_WINDOW) / (budget + 1))
        t = HOOK_WINDOW + step
        while t < end - 0.2:
            picks.append({"t": round(t, 2), "kind": "coverage"})
            t += step

    # De-duplicate: keep the highest-priority frame in each MIN_GAP window.
    rank = {"hook": 0, "end": 1, "cut": 2, "coverage": 3}
    picks.sort(key=lambda p: (rank[p["kind"]], p["t"]))
    kept: list[dict] = []
    for p in picks:
        if all(abs(p["t"] - k["t"]) >= MIN_GAP for k in kept):
            kept.append(p)
    # Over budget (cut-heavy edits): thin coverage first, then cuts evenly.
    while len(kept) > max_frames:
        for kind in ("coverage", "cut"):
            pool = [k for k in kept if k["kind"] == kind]
            if pool:
                kept.remove(pool[len(pool) // 2] if kind == "cut" else pool[-1])
                break
        else:
            break
    for k in kept:  # a hook/coverage frame that lands on an edit is also a cut
        k["cut"] = k["kind"] == "cut" or any(abs(c - k["t"]) < MIN_GAP for c in cuts)
    return sorted(kept, key=lambda p: p["t"])


def _grab(video: Path, t: float, dest: Path, long_side: int) -> bool:
    scale = f"scale='if(gt(iw,ih),{long_side},-2)':'if(gt(iw,ih),-2,{long_side})'"
    out = proc.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
         "-frames:v", "1", "-vf", scale, "-q:v", "3", str(dest)],
        capture_output=True, text=True)
    return out.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def build(video: Path, out_dir: Path, duration: float, progress=lambda m: None) -> dict:
    max_frames = int(os.environ.get("UGC_FLIPBOOK_MAX", "48"))
    long_side = int(os.environ.get("UGC_FLIPBOOK_PX", "896"))
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("*.jpg"):
        fsutil.remove(old)

    progress("detecting scene cuts")
    cuts = scene_cuts(video)
    plan = plan_timestamps(duration, cuts, max_frames)
    frames = []
    for i, p in enumerate(plan, 1):
        name = f"f{i:03d}_{p['t']:06.2f}s.jpg"
        if _grab(video, p["t"], frames_dir / name, long_side):
            frames.append({"n": i, "t": p["t"], "kind": p["kind"], "cut": p.get("cut", False),
                           "file": f"frames/{name}"})
        progress(f"frame {i}/{len(plan)}")

    shots = [0.0] + [c for c in cuts if 0 < c < duration] + [duration]
    lengths = [b - a for a, b in zip(shots, shots[1:]) if b - a > 0.05]
    index = {
        "frames": frames,
        "scene_cuts": cuts,
        "stats": {
            "shots": len(lengths),
            "avg_shot_s": round(sum(lengths) / len(lengths), 2) if lengths else None,
            "cuts_in_first_3s": sum(1 for c in cuts if c <= HOOK_WINDOW),
            "cuts_per_10s": round(len(cuts) / duration * 10, 2) if duration else None,
        },
    }
    if frames:
        contact_sheet(out_dir, frames)
        index["sheet"] = "sheet.jpg"
    return index


def contact_sheet(out_dir: Path, frames: list[dict], cols: int = 8, cell_w: int = 220) -> Path:
    """One shareable overview image with timestamps burned in."""
    first = Image.open(out_dir / frames[0]["file"])
    cell_h = int(cell_w * first.height / first.width)
    rows = (len(frames) + cols - 1) // cols
    pad = 6
    sheet = Image.new("RGB", (cols * (cell_w + pad) + pad, rows * (cell_h + pad) + pad), (12, 12, 13))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=15)
    except TypeError:  # old Pillow
        font = ImageFont.load_default()
    for i, f in enumerate(frames):
        img = Image.open(out_dir / f["file"]).convert("RGB").resize((cell_w, cell_h))
        x, y = pad + (i % cols) * (cell_w + pad), pad + (i // cols) * (cell_h + pad)
        sheet.paste(img, (x, y))
        label = f"{f['t']:.1f}s" + (" CUT" if f.get("cut") else "")
        draw.rectangle([x, y, x + 8 + 9 * len(label), y + 20], fill=(0, 0, 0))
        draw.text((x + 4, y + 2), label, fill=(212, 255, 63) if f.get("cut") else (240, 240, 240), font=font)
    dest = out_dir / "sheet.jpg"
    sheet.save(dest, quality=85)
    return dest
