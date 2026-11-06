"""ASR provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from app.ai.types import ASRResult, ProviderInfo


class ASRProvider(ABC):
    name = "asr"

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str,
                   chunk_times: List[tuple]) -> ASRResult:
        """Transcribe a preprocessed WAV.

        `chunk_times` is a list of (start, end) absolute second offsets produced
        by the segmentation stage. Providers that support chunk-level timing
        return one ASRSegmentResult per chunk (text may be empty for silence).
        """

    @abstractmethod
    def info(self) -> ProviderInfo:
        ...

    @property
    def is_mock(self) -> bool:
        return self.info().mode == "mock"
