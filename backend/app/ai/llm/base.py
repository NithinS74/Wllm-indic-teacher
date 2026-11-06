"""LLM provider interface (notes + quiz generation)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

from app.ai.types import GenerationContext, LLMResult, ProviderInfo


class LLMProvider(ABC):
    name = "llm"

    @abstractmethod
    def generate_notes(self, ctx: GenerationContext) -> LLMResult:
        """Return a dict matching the NotesContent schema."""

    @abstractmethod
    def generate_quiz(self, ctx: GenerationContext) -> LLMResult:
        """Return a dict {"questions": [...]} with exactly five questions."""

    @abstractmethod
    def info(self) -> ProviderInfo:
        ...

    @property
    def is_mock(self) -> bool:
        return self.info().mode == "mock"
