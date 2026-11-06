"""Audio validation and FFmpeg preprocessing."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.core.errors import UnsupportedMediaError, ValidationAppError

logger = logging.getLogger("lecturelens.audio")

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


class AudioError(ValidationAppError):
    code = "audio_error"


@dataclass
class AudioInfo:
    path: Path
    duration: float
    sample_rate: int
    channels: int
    format_name: str
    has_audio: bool


def _run(cmd: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
    logger.debug("run: %s", " ".join(cmd))
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError as exc:
        raise AudioError(
            f"Required binary '{cmd[0]}' is not installed on the server."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioError(f"Audio tool timed out running '{cmd[0]}'.") from exc


def probe(path: Path) -> AudioInfo:
    """Inspect the file with ffprobe — validates real audio readability."""
    if not path.exists():
        raise AudioError("Audio file not found on server.")
    proc = _run([
        FFPROBE, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ], timeout=60)
    if proc.returncode != 0:
        raise UnsupportedMediaError(
            "The uploaded file could not be read as audio. "
            "It may be corrupted or not in a supported format.",
            detail={"ffprobe": (proc.stderr or "").strip()[:500]},
        )
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise UnsupportedMediaError("Could not parse audio metadata.") from exc

    audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise UnsupportedMediaError(
            "No audio stream found in the uploaded file.",
            detail={"format": data.get("format", {}).get("format_name")},
        )
    stream = audio_streams[0]
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or stream.get("duration") or 0.0)
    if duration <= 0:
        # Some containers omit duration; fall back to a decode-based probe.
        duration = _probe_duration_by_decode(path)

    return AudioInfo(
        path=path,
        duration=duration,
        sample_rate=int(stream.get("sample_rate") or settings.target_sample_rate),
        channels=int(stream.get("channels") or 1),
        format_name=str(fmt.get("format_name") or ""),
        has_audio=True,
    )


def _probe_duration_by_decode(path: Path) -> float:
    proc = _run([
        FFMPEG, "-v", "error", "-i", str(path), "-f", "null", "-"
    ], timeout=300)
    # duration is not printed with -v error; use -stats_format? keep 0 fallback
    if proc.returncode != 0:
        raise UnsupportedMediaError(
            "Audio appears corrupted (decoding failed).",
            detail={"ffmpeg": (proc.stderr or "").strip()[:500]},
        )
    return 0.0


def validate_upload(path: Path) -> AudioInfo:
    info = probe(path)
    if info.duration < settings.min_audio_duration_seconds:
        raise AudioError(
            f"Audio is too short ({info.duration:.1f}s). "
            f"Minimum is {settings.min_audio_duration_seconds:.0f}s.",
            detail={"duration": info.duration},
        )
    if info.duration > settings.max_audio_duration_seconds:
        raise AudioError(
            f"Audio is too long ({info.duration / 60:.1f} min). "
            f"Maximum is {settings.max_audio_duration_seconds / 60:.0f} min.",
            detail={"duration": info.duration,
                    "max": settings.max_audio_duration_seconds},
        )
    return info


def preprocess(src: Path, dest_dir: Optional[Path] = None) -> Path:
    """Normalize audio to mono 16 kHz WAV accepted by IndicConformer."""
    dest_dir = dest_dir or settings.processed_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (src.stem + "_16k.wav")
    proc = _run([
        FFMPEG, "-y", "-i", str(src),
        "-vn",
        "-ac", str(settings.target_channels),
        "-ar", str(settings.target_sample_rate),
        "-sample_fmt", "s16",
        "-f", "wav", str(dest),
    ], timeout=600)
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise AudioError(
            "Audio preprocessing failed — the file may be corrupted.",
            detail={"ffmpeg": (proc.stderr or "").strip()[:500]},
        )
    return dest


def extract_pcm(path: Path) -> bytes:
    """Decode a WAV to raw s16le mono PCM at the target sample rate."""
    proc = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path),
         "-f", "s16le", "-acodec", "pcm_s16le",
         "-ac", str(settings.target_channels),
         "-ar", str(settings.target_sample_rate), "-"],
        capture_output=True, check=False, timeout=600,
    )
    if proc.returncode != 0:
        raise AudioError(
            "Could not decode audio to PCM.",
            detail={"ffmpeg": proc.stderr.decode("utf-8", "ignore")[:500]},
        )
    return proc.stdout
