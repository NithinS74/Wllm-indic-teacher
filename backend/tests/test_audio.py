"""Audio preprocessing + segmentation tests."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.core.errors import UnsupportedMediaError, ValidationAppError
from app.services import audio as audio_service
from app.services.segmentation import (
    build_segments,
    dedupe_overlap,
    detect_speech_regions,
)


def _pcm(sample_rate: int = 16000) -> bytes:
    """2 s tone + 1 s silence + 2 s tone."""
    out = bytearray()
    for freq, secs in ((300, 2.0), (0, 1.0), (500, 2.0)):
        n = int(sample_rate * secs)
        for i in range(n):
            if freq == 0:
                out.extend(b"\x00\x00")
            else:
                import math
                v = 0.5 * math.sin(2 * math.pi * freq * i / sample_rate)
                out.extend(struct.pack("<h", int(v * 32767)))
    return bytes(out)


def test_detect_speech_regions_finds_silence_gap():
    regions = detect_speech_regions(_pcm(), 16000, threshold_db=-35.0)
    assert len(regions) >= 2
    # first region starts near 0, second after the silence gap (~2 s)
    assert regions[0][0] < 0.5
    assert regions[-1][1] > 3.5
    gap_starts = [r[0] for r in regions[1:]]
    assert all(g >= 1.5 for g in gap_starts)


def test_build_segments_short_audio_single_chunk():
    segs = build_segments(_pcm(), 16000, total_duration=5.0)
    assert len(segs) == 1
    assert segs[0].start == 0.0
    assert segs[0].end == 5.0


def test_build_segments_long_audio_overlapping_chunks():
    # simulate a 100 s recording; default chunk is 30 s
    pcm = _pcm() * 20
    duration = 100.0
    segs = build_segments(pcm, 16000, total_duration=duration)
    assert len(segs) >= 3
    assert segs[0].start == 0.0
    assert abs(segs[-1].end - duration) < 0.6
    # contiguous coverage with overlap (next start < previous end)
    for prev, cur in zip(segs, segs[1:]):
        assert cur.start < prev.end
        assert cur.start >= prev.start
    # indices are 1-based sequential
    assert [s.index for s in segs] == list(range(1, len(segs) + 1))


def test_dedupe_overlap_removes_repeated_prefix():
    prev = "the process scheduler decides next"
    cur = "decides next which process runs"
    merged = dedupe_overlap(prev, cur, overlap_seconds=2.0)
    assert merged == "which process runs"


def test_dedupe_overlap_no_match_returns_current():
    assert dedupe_overlap("alpha beta", "gamma delta", 1.0) == "gamma delta"


def test_probe_rejects_non_audio(tmp_path: Path):
    bad = tmp_path / "not_audio.wav"
    bad.write_bytes(b"this is definitely not audio data" * 10)
    with pytest.raises((UnsupportedMediaError, ValidationAppError)):
        audio_service.probe(bad)


def test_preprocess_produces_16k_mono_wav(tmp_path: Path, demo_wav_bytes: bytes):
    src = tmp_path / "in.wav"
    src.write_bytes(demo_wav_bytes)
    info = audio_service.probe(src)
    assert info.has_audio
    assert info.duration > 5.0
    out = audio_service.preprocess(src, dest_dir=tmp_path / "out")
    assert out.exists()
    out_info = audio_service.probe(out)
    assert out_info.sample_rate == 16000
    assert out_info.channels == 1
