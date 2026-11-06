"""Provider factory — selects mock/real implementations from configuration."""
from __future__ import annotations

import logging
from typing import List

from app.ai import config as ai_config
from app.ai.asr.base import ASRProvider
from app.ai.llm.base import LLMProvider
from app.ai.translation.base import TranslationProvider
from app.ai.types import ProviderInfo
from app.core.config import settings
from app.core.errors import ModelLoadError

logger = logging.getLogger("lecturelens.ai.factory")

_asr: ASRProvider | None = None
_llm: LLMProvider | None = None
_translation: TranslationProvider | None = None


def get_asr_provider() -> ASRProvider:
    global _asr
    if _asr is None:
        if settings.asr_provider == "mock":
            from app.ai.asr.mock import MockASR
            _asr = MockASR()
        else:
            from app.ai.asr.indicconformer import IndicConformerASR
            _asr = IndicConformerASR()
        logger.info("ASR provider: %s", _asr.info())
    return _asr


def get_llm_provider() -> LLMProvider:
    global _llm
    if _llm is None:
        if settings.llm_provider == "mock":
            from app.ai.llm.mock import MockLLM
            _llm = MockLLM()
        else:
            from app.ai.llm.param1 import Param1LLM
            _llm = Param1LLM()
        logger.info("LLM provider: %s", _llm.info())
    return _llm


def get_translation_provider() -> TranslationProvider:
    global _translation
    if _translation is None:
        if settings.translation_provider == "mock":
            from app.ai.translation.mock import MockTranslation
            _translation = MockTranslation()
        else:
            from app.ai.translation.indictrans2 import IndicTrans2
            _translation = IndicTrans2()
        logger.info("Translation provider: %s", _translation.info())
    return _translation


def provider_statuses() -> List[ProviderInfo]:
    """Status of all three providers (never triggers weight loading)."""
    return [
        get_asr_provider().info(),
        get_llm_provider().info(),
        get_translation_provider().info(),
    ]


def reset_providers() -> None:
    """Testing hook — drop cached provider instances."""
    global _asr, _llm, _translation
    _asr = _llm = _translation = None


def ensure_real_configured() -> None:
    """Fail fast with a clear message when a real provider is selected but
    unconfigured. Called at job start (not at app startup)."""
    problems: List[str] = []
    if settings.asr_provider != "mock" and not (
            settings.indicconformer_checkpoint or settings.asr_remote_url):
        problems.append(
            "ASR_PROVIDER=indicconformer requires INDICCONFORMER_CHECKPOINT "
            "(local .nemo path) or ASR_REMOTE_URL.")
    if settings.llm_provider != "mock" and not settings.llm_remote_url:
        # local weights are allowed (param1_model_id) — nothing to check here
        pass
    if problems:
        raise ModelLoadError("Provider configuration incomplete:",
                             detail="; ".join(problems))
