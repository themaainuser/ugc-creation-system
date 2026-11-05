"""File writes that survive Windows file locks.

On Windows, OneDrive sync and antivirus scanners briefly open files they
see change. While they hold one, renaming over it or deleting it fails
with "PermissionError: [WinError 5] Access is denied". These helpers retry
for a couple of seconds, then fall back to a plain overwrite, so a sync
client can't crash a pipeline stage.
"""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

RETRY_DELAYS = (0.05, 0.1, 0.2, 0.3, 0.5, 0.8)  # ~2 s in total


def write_text(path: Path, text: str) -> None:
    """Atomic when possible (readers never see half a file), never fails on a brief lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{secrets.token_hex(3)}.tmp")  # unique: a scanner may still hold the last one
    tmp.write_text(text, encoding="utf-8")
    try:
        for delay in (*RETRY_DELAYS, None):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if delay is None:
                    break
                time.sleep(delay)
        # Still locked: overwrite in place (not atomic, but readers retry anyway).
        for delay in (*RETRY_DELAYS, None):
            try:
                path.write_text(text, encoding="utf-8")
                return
            except PermissionError:
                if delay is None:
                    raise
                time.sleep(delay)
    finally:
        remove(tmp)


def remove(path: Path) -> bool:
    """Delete if possible; a temp file that's locked right now is not worth crashing over."""
    try:
        Path(path).unlink(missing_ok=True)
        return True
    except PermissionError:
        return False
