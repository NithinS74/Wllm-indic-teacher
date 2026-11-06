"""Translation provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.ai.types import ProviderInfo, TranslationResult


class TranslationProvider(ABC):
    name = "translation"

    @abstractmethod
    def translate_batch(self, texts: List[str], source_lang: str,
                        target_lang: str) -> List[str]:
        """Translate a list of texts between language keys (en, hi, kn, ...)."""

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text:
            return text
        return self.translate_batch([text], source_lang, target_lang)[0]

    @abstractmethod
    def info(self) -> ProviderInfo:
        ...

    @property
    def is_mock(self) -> bool:
        return self.info().mode == "mock"
