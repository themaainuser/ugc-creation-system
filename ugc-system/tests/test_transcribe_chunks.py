import subprocess
from pathlib import Path

import pytest

from ugc_system.reel_lab import media, transcribe as tr


# ---------------------------------------------------------------- plan
def test_chunks_cut_at_silences_with_overlap():
    spans = tr.plan_chunks(1500, 600, 1.5, cut_points=[200, 570, 1150])
    assert spans == [(0.0, 570), (568.5, 1150), (1148.5, 1500)]


def test_chunks_without_silences_cover_everything():
    spans = tr.plan_chunks(1900, 600, 1.5)
    assert spans[0][0] == 0 and spans[-1][1] == 1900
    for (a1, b1), (a2, _) in zip(spans, spans[1:]):
        assert b1 - a1 <= 600 and b1 - a2 == pytest.approx(1.5)


def test_short_tail_is_folded_into_the_last_chunk():
    spans = tr.plan_chunks(1210, 600, 1.5)  # 600 + 598.5 would leave ~13 s
    assert len(spans) == 2 and spans[-1] == (598.5, 1210)


def test_silence_too_early_is_ignored():
    spans = tr.plan_chunks(1300, 600, 1.5, cut_points=[100])  # outside the 90 s lookback
    assert spans[0] == (0.0, 600)


# ---------------------------------------------------------------- merge
def seg(a, b, text, words=None):
    return {"start": a, "end": b, "text": text, "words": words or []}


def test_merge_shifts_offsets_and_drops_overlap_duplicates():
    results = [
        (0.0, 600.0, [seg(10, 14, "Welcome back to the channel."),
                      seg(596.0, 599.9, "So we drove to the")]),          # cut off at the edge
        (598.5, 1200.0, [seg(0.0, 3.5, "So we drove to the beach."),      # same line, complete
                         seg(4.0, 6.0, "And then it rained.",
                             [{"start": 4.0, "end": 4.4, "word": "And"}])]),
    ]
    out = tr.merge_chunks(results)
    assert [s["text"] for s in out] == ["Welcome back to the channel.", "So we drove to the beach.",
                                        "And then it rained."]
    assert out[1]["start"] == 596.0 and out[1]["end"] == 602.0          # kept the earlier start, longer text
    assert out[2]["start"] == 602.5 and out[2]["words"][0]["start"] == 602.5


def test_merge_keeps_real_repeats_outside_the_overlap():
    results = [(0.0, 600.0, [seg(100, 102, "La la la")]),
               (598.5, 1200.0, [seg(101.5, 103.5, "La la la")])]        # at 700 s: a chorus, not a duplicate
    out = tr.merge_chunks(results)
    assert [s["start"] for s in out] == [100, 700.0]


def test_merge_keeps_different_lines_in_the_overlap():
    results = [(0.0, 600.0, [seg(598.0, 599.8, "Okay.")]),
               (598.5, 1200.0, [seg(0.5, 2.0, "Now the second part starts")])]
    assert len(tr.merge_chunks(results)) == 2


# ---------------------------------------------------------------- end to end (real ffmpeg, fake API)
@pytest.fixture
def speechy_wav(tmp_path) -> Path:
    """25 s: tone bursts separated by silences, like speech with pauses."""
    out = tmp_path / "audio.wav"
    filt = "sine=f=300:d=6[a];anullsrc=r=16000:cl=mono:d=1.2[s1];sine=f=350:d=7[b];" \
           "anullsrc=r=16000:cl=mono:d=1.2[s2];sine=f=400:d=9.6[c];[a][s1][b][s2][c]concat=n=5:v=0:a=1"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-filter_complex", filt, "-ar", "16000", "-ac", "1", str(out)], check=True)
    return out


def test_long_audio_is_encoded_chunked_and_merged(speechy_wav, monkeypatch):
    profile = media.audio_profile(speechy_wav, 25.0)
    assert len(profile["cut_points"]) >= 2
    monkeypatch.setattr(tr, "MAX_UPLOAD", 1000)   # force the chunked path
    monkeypatch.setattr(tr, "CHUNK_SECONDS", 10.0)
    monkeypatch.setattr(tr, "_api_client", lambda provider: (None, "fake-whisper"))
    uploads = []

    def fake_api_file(client, model, path):
        dur = tr._duration(path)
        uploads.append((path.suffix, path.stat().st_size, round(dur, 1)))
        return {"language": "en", "segments": [seg(0.2, round(dur - 0.2, 2), f"words in {path.stem}")]}

    monkeypatch.setattr(tr, "_api_file", fake_api_file)
    msgs = []
    out = tr._api(speechy_wav, "groq", msgs.append, duration=25.0, cut_points=profile["cut_points"])

    assert out["upload"]["chunks"] == len(uploads) >= 3
    assert all(ext == ".ogg" and size < 200_000 for ext, size, _ in uploads)   # small speech format, not WAV
    assert any(m.startswith("chunk 2/") for m in msgs) and msgs[-1].startswith("merging")
    starts = [s["start"] for s in out["segments"]]
    assert starts == sorted(starts) and starts[0] == pytest.approx(0.2)
    assert out["segments"][-1]["end"] == pytest.approx(25.0 - 0.2, abs=0.3)
    assert not (speechy_wav.parent / "upload_tmp").exists()                     # temp files cleaned up


def test_short_audio_is_one_small_upload(speechy_wav, monkeypatch):
    monkeypatch.setattr(tr, "_api_client", lambda provider: (None, "fake-whisper"))
    sent = []
    monkeypatch.setattr(tr, "_api_file", lambda c, m, p: sent.append((p.suffix, p.stat().st_size)) or
                        {"language": "en", "segments": [seg(0, 1, "hi")]})
    out = tr._api(speechy_wav, "openai", lambda m: None)
    assert out["upload"]["chunks"] == 1 and sent[0][0] == ".ogg"
    assert sent[0][1] < speechy_wav.stat().st_size / 5   # far smaller than the raw WAV
