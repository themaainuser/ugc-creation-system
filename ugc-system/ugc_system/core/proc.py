"""Run external tools (ffmpeg, ffprobe) without flashing console windows.

The UI starts the pipeline as a detached background process. On Windows a
detached process has no console, so every console program it starts
(ffmpeg once per flipbook frame) would get its own new console window that
pops up and closes. CREATE_NO_WINDOW runs them with no window at all.
Every subprocess in ugc_system must go through `run` (a test enforces it).
"""
from __future__ import annotations

import os
import subprocess

IS_WINDOWS = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000  # subprocess.CREATE_NO_WINDOW; spelled out so this imports on any OS


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    if IS_WINDOWS:
        kw["creationflags"] = kw.get("creationflags", 0) | CREATE_NO_WINDOW
    return subprocess.run(cmd, **kw)
