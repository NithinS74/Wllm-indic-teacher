"""Provider selection helpers (env-driven)."""
from __future__ import annotations

from app.core.config import settings


def asr_mode() -> str:
    return "mock" if settings.asr_provider == "mock" else "real"


def llm_mode() -> str:
    return "mock" if settings.llm_provider == "mock" else "real"


def translation_mode() -> str:
    return "mock" if settings.translation_provider == "mock" else "real"


def current_provider_names() -> dict:
    return {
        "asr": settings.asr_provider,
        "llm": settings.llm_provider,
        "translation": settings.translation_provider,
    }
