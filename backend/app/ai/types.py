"""Shared AI provider data types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ASRSegmentResult:
    """One recognized chunk.

    start/end are chunk-level offsets (IndicConformer/RNNT does not provide
    reliable word-level timestamps; we never claim otherwise).
    """
    start: float
    end: float
    text: str
    language: str


@dataclass
class ASRResult:
    segments: List[ASRSegmentResult]
    language: str
    is_mock: bool = False
    provider: str = ""
    detail: str = ""


@dataclass
class LLMResult:
    payload: Dict[str, Any]
    is_mock: bool = False
    provider: str = ""
    raw_text: str = ""
    detail: str = ""


@dataclass
class TranslationResult:
    text: str
    is_mock: bool = False
    provider: str = ""
    detail: str = ""


@dataclass
class ProviderInfo:
    name: str
    provider: str
    mode: str  # mock | real
    loaded: bool
    detail: str = ""


@dataclass
class GenerationContext:
    """Everything the LLM provider needs to ground its output."""
    lecture_id: str
    lecture_title: str
    source_language: str
    transcript_text: str
    segment_texts: List[str] = field(default_factory=list)
    segment_indices: List[int] = field(default_factory=list)
