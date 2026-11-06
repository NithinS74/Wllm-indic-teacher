"""Speech-aware audio segmentation.

Implements an energy-based voice activity detector over the PCM stream
produced by FFmpeg, then cuts the audio into chunks that:

* end on low-energy (silence) boundaries so words are not clipped,
* overlap slightly so ASR does not drop words at cut points,
* preserve absolute start/end offsets in the original recording.

No third-party VAD library is required; thresholds are configurable via
environment variables (VAD_*, CHUNK_*).
"""
from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from app.core.config import settings

logger = logging.getLogger("lecturelens.segmentation")


@dataclass(frozen=True)
class Segment:
    start: float   # seconds, absolute in original file
    end: float
    index: int     # 1-based


def _frame_energy_db(pcm: np.ndarray, sample_rate: int,
                     frame_ms: int = 25, hop_ms: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    frame_len = int(sample_rate * frame_ms / 1000)
    hop_len = int(sample_rate * hop_ms / 1000)
    if len(pcm) < frame_len:
        return np.array([0.0]), np.array([0.0])
    n_frames = 1 + (len(pcm) - frame_len) // hop_len
    starts = np.arange(n_frames) * hop_len
    frames = np.lib.stride_tricks.as_strided(
        pcm,
        shape=(n_frames, frame_len),
        strides=(pcm.strides[0] * hop_len, pcm.strides[0]),
    )
    energy = np.mean(frames.astype(np.float64) ** 2, axis=1)
    energy_db = 10.0 * np.log10(np.maximum(energy, 1e-12))
    times = starts / float(sample_rate)
    return times, energy_db


def detect_speech_regions(pcm_s16le: bytes, sample_rate: int,
                          threshold_db: float) -> List[Tuple[float, float]]:
    """Return merged speech intervals [(start_s, end_s), ...]."""
    if not pcm_s16le:
        return []
    samples = np.frombuffer(pcm_s16le, dtype=np.int16).astype(np.float64) / 32768.0
    times, energy_db = _frame_energy_db(samples, sample_rate)
    if len(times) == 0:
        return []

    speech = energy_db > threshold_db
    hop_s = 0.010
    min_speech = settings.vad_min_speech_seconds
    max_gap = settings.vad_max_silence_for_split_seconds

    regions: List[Tuple[float, float]] = []
    in_speech = False
    start_t = 0.0
    last_speech_t = 0.0
    for t, is_sp in zip(times, speech):
        if is_sp and not in_speech:
            in_speech = True
            start_t = float(t)
        elif is_sp:
            last_speech_t = float(t)
        elif in_speech and (float(t) - last_speech_t) > max_gap:
            in_speech = False
            regions.append((start_t, last_speech_t + hop_s))
    if in_speech:
        regions.append((start_t, last_speech_t + hop_s))

    # merge regions separated by less than max_gap, drop very short blips
    merged: List[Tuple[float, float]] = []
    for s, e in regions:
        if merged and (s - merged[-1][1]) <= max_gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    merged = [(s, e) for (s, e) in merged if (e - s) >= min_speech]

    if not merged:
        # all silence or speech below threshold: treat whole file as one region
        duration = len(samples) / float(sample_rate)
        merged = [(0.0, duration)]
    return merged


def _find_split_point(times: np.ndarray, energy_db: np.ndarray,
                      lo: float, hi: float, threshold_db: float) -> float:
    """Pick a split time inside [lo, hi] closest to the midpoint that lies in
    a low-energy region (silence preferred, otherwise lowest energy)."""
    if hi - lo < 1.0:
        return (lo + hi) / 2.0
    mid = (lo + hi) / 2.0
    window = 0.75  # search ±0.75 s around the midpoint
    mask = (times >= mid - window) & (times <= mid + window)
    if not np.any(mask):
        return mid
    idx = np.where(mask)[0]
    sub_e = energy_db[idx]
    # prefer frames below threshold; among them choose the one closest to mid
    below = idx[sub_e < threshold_db]
    if len(below) > 0:
        best = min(below, key=lambda i: abs(times[i] - mid))
        return float(times[best])
    # fall back to the quietest frame in the window
    best = idx[int(np.argmin(sub_e))]
    return float(times[best])


def build_segments(pcm_s16le: bytes, sample_rate: int,
                   total_duration: float) -> List[Segment]:
    """Split the recording into speech-aware, overlapping chunks."""
    chunk = max(5.0, settings.chunk_duration_seconds)
    overlap = max(0.0, min(settings.chunk_overlap_seconds, chunk / 4))
    threshold = settings.vad_energy_threshold_db

    if total_duration <= chunk:
        return [Segment(0.0, total_duration, 1)]

    samples = np.frombuffer(pcm_s16le, dtype=np.int16).astype(np.float64) / 32768.0
    times, energy_db = _frame_energy_db(samples, sample_rate)

    segments: List[Segment] = []
    start = 0.0
    idx = 1
    while start < total_duration - 0.5:
        ideal_end = min(start + chunk, total_duration)
        if ideal_end < total_duration - 0.5:
            end = _find_split_point(times, energy_db, start + chunk * 0.5,
                                    ideal_end, threshold)
            end = max(start + 2.0, min(end, ideal_end))
        else:
            end = total_duration
        segments.append(Segment(round(start, 3), round(end, 3), idx))
        idx += 1
        if end >= total_duration - 0.1:
            break
        start = max(end - overlap, start + 1.0)

    return segments


def slice_pcm(pcm_s16le: bytes, sample_rate: int, seg: Segment) -> bytes:
    width = 2  # s16le
    start_b = int(seg.start * sample_rate) * width
    end_b = int(seg.end * sample_rate) * width
    start_b = max(0, min(start_b, len(pcm_s16le)))
    end_b = max(start_b, min(end_b, len(pcm_s16le)))
    return pcm_s16le[start_b:end_b]


def dedupe_overlap(previous_text: str, current_text: str,
                   overlap_seconds: float) -> str:
    """Remove duplicated speech introduced by overlapping chunks.

    ASR output is not word-aligned, so we use a suffix/prefix token overlap
    heuristic on whitespace-tokenized text (works for both Indic and Latin
    scripts since we compare token sequences).
    """
    if not previous_text or not current_text:
        return current_text
    prev = previous_text.split()
    cur = current_text.split()
    if not prev or not cur:
        return current_text
    max_k = min(len(prev), len(cur), max(4, int(overlap_seconds * 4)))
    for k in range(max_k, 0, -1):
        if prev[-k:] == cur[:k]:
            return " ".join(cur[k:])
    # soft match: compare last few tokens ignoring punctuation/case
    def norm(tok: str) -> str:
        return tok.strip(".,!?;:।").lower()

    prev_n = [norm(t) for t in prev]
    cur_n = [norm(t) for t in cur]
    for k in range(max_k, 0, -1):
        if prev_n[-k:] == cur_n[:k]:
            return " ".join(cur[k:])
    return current_text
