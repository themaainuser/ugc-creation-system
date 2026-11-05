"""Windows: OneDrive/antivirus file locks and console windows popping up."""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from ugc_system.core import fsutil, proc
from ugc_system.reel_lab.job import Job

ROOT = Path(__file__).resolve().parents[1] / "ugc_system"


def test_write_text_retries_through_a_brief_lock(tmp_path, monkeypatch):
    target = tmp_path / "status.json"
    real_replace, calls = os.replace, {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:  # OneDrive holds the file for a moment
            raise PermissionError(5, "Access is denied", str(src))
        real_replace(src, dst)

    monkeypatch.setattr(fsutil.os, "replace", flaky_replace)
    monkeypatch.setattr(fsutil, "RETRY_DELAYS", (0, 0, 0))
    fsutil.write_text(target, '{"ok": 1}')
    assert json.loads(target.read_text()) == {"ok": 1} and calls["n"] == 3
    assert not list(tmp_path.glob("*.tmp"))  # temp file cleaned up


def test_write_text_falls_back_to_overwrite_when_rename_stays_locked(tmp_path, monkeypatch):
    target = tmp_path / "status.json"
    target.write_text("old")

    def locked(src, dst):
        raise PermissionError(5, "Access is denied", str(src))

    monkeypatch.setattr(fsutil.os, "replace", locked)
    monkeypatch.setattr(fsutil, "RETRY_DELAYS", (0,))
    fsutil.write_text(target, "new")
    assert target.read_text() == "new" and not list(tmp_path.glob("*.tmp"))


def test_progress_updates_are_throttled_but_state_changes_never(tmp_path, monkeypatch):
    job = Job.create({"persona": "aria"}, jobs_dir=tmp_path)
    writes = []
    real = fsutil.write_text
    monkeypatch.setattr(fsutil, "write_text", lambda p, t: (writes.append(p.name), real(p, t)))
    job.update("flipbook", state="running", message="start")
    for i in range(48):  # one message per frame
        job.update("flipbook", message=f"frame {i + 1}/48")
    job.update("flipbook", state="done", message="48 frames")
    assert writes.count("status.json") <= 4
    assert job.status["stages"]["flipbook"]["state"] == "done"


def test_a_locked_progress_write_does_not_crash_the_stage(tmp_path, monkeypatch):
    job = Job.create({"persona": "aria"}, jobs_dir=tmp_path)
    job._last_write = 0

    def locked(p, t):
        raise PermissionError(5, "Access is denied", str(p))

    monkeypatch.setattr(fsutil, "write_text", locked)
    job.update("flipbook", message="frame 3/48")  # swallowed
    with pytest.raises(PermissionError):
        job.update("flipbook", state="done")      # a real state change must not be lost silently


def test_tools_run_without_a_console_window_on_windows(monkeypatch):
    seen = {}
    monkeypatch.setattr(proc, "IS_WINDOWS", True)
    monkeypatch.setattr(proc.subprocess, "run", lambda cmd, **kw: seen.update(kw) or subprocess.CompletedProcess(cmd, 0))
    proc.run(["ffmpeg", "-version"], capture_output=True)
    assert seen["creationflags"] & 0x08000000 and seen["capture_output"]


def test_no_module_starts_processes_without_the_no_window_flag():
    offenders = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py")
                 if p.name != "proc.py" and re.search(r"subprocess\.(run|Popen|call|check_output)\(", p.read_text())]
    assert offenders == [], f"use ugc_system.core.proc.run instead: {offenders}"
