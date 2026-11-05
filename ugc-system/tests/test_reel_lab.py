import json
import subprocess
from pathlib import Path

import pytest

from ugc_system.core.env import parse_env_file
from ugc_system.reel_lab import flipbook, mastermind, pipeline
from ugc_system.reel_lab.job import Job


def test_env_parser_keeps_urls_and_strips_comments():
    v = parse_env_file("# c\nA=1\nURL=https://x.y/z // note\nQ=\"quoted\"\n")
    assert v == {"A": "1", "URL": "https://x.y/z", "Q": "quoted"}


def test_plan_covers_hook_cuts_and_end():
    plan = flipbook.plan_timestamps(30.0, [4.0, 4.1, 12.0, 20.0], 48)
    ts = [p["t"] for p in plan]
    assert ts[:7] == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]   # dense hook window
    assert 12.0 in ts and 20.0 in ts                        # every cut kept
    assert ts[-1] == pytest.approx(29.85)                   # final frame
    assert all(b - a >= flipbook.MIN_GAP - 1e-9 for a, b in zip(ts, ts[1:]))


def test_plan_respects_cap_on_cut_heavy_edits():
    cuts = [round(0.4 * i, 2) for i in range(1, 150)]
    plan = flipbook.plan_timestamps(60.0, cuts, 24)
    assert len(plan) <= 24
    assert plan[0]["t"] == 0.0 and plan[-1]["kind"] == "end"


def test_split_sections_parses_all_three():
    text = ("<reel_flow>\n# Flow\n</reel_flow>\n<generation_prompts>\n# Prompts\n</generation_prompts>\n"
            "<blueprint>\n```json\n{\"title\": \"x\", \"shots\": []}\n```\n</blueprint>")
    s = mastermind.split_sections(text)
    assert s["reel_flow"] == "# Flow" and s["generation_prompts"] == "# Prompts"
    assert s["blueprint_json"] == {"title": "x", "shots": []}


def test_split_sections_survives_truncated_reply():
    s = mastermind.split_sections("<reel_flow>\n# Flow\n</reel_flow>\n<generation_prompts>\n# half")
    assert s["generation_prompts"] == "# half" and s["blueprint_json"] is None


@pytest.fixture
def clip(tmp_path):
    out = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=270x480:d=2",
         "-f", "lavfi", "-i", "color=c=blue:s=270x480:d=2", "-f", "lavfi", "-i", "sine=f=300:d=4",
         "-filter_complex", "[0][1]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)], check=True)
    return out


def test_pipeline_end_to_end_dry_run(tmp_path, clip, monkeypatch):
    monkeypatch.setenv("UGC_MASTERMIND_DRY_RUN", "1")
    monkeypatch.setenv("UGC_TRANSCRIBE", "none")
    job = Job.create({"persona": "aria", "mode": "remix", "idea": "thrift haul"}, jobs_dir=tmp_path)
    (job.media / "source.mp4").write_bytes(clip.read_bytes())
    status = pipeline.run(job.path)
    assert status["state"] == "done", status
    idx = json.loads((job.flipbook / "index.json").read_text())
    assert idx["stats"]["shots"] == 2 and idx["scene_cuts"]
    assert any(f["cut"] for f in idx["frames"])
    preview = (job.out / "request_preview.md").read_text()
    assert "thrift haul" in preview and "id: aria" in preview


def test_pipeline_reports_stage_error(tmp_path):
    job = Job.create({"persona": "aria"}, jobs_dir=tmp_path)  # no url, no file
    status = pipeline.run(job.path)
    assert status["state"] == "error"
    assert status["stages"]["download"]["state"] == "error"
