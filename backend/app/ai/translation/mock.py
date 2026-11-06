"""Mock translation provider.

Deterministic structural pseudo-translation used only when
TRANSLATION_PROVIDER=mock. It preserves paragraph/line structure and any
identifier tokens (question-1, A/B/C/D, [S12], section-2) exactly, and marks
translated text with a visible language tag so it can never be mistaken for a
real IndicTrans2 output.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import List

from app.ai.translation.base import TranslationProvider
from app.ai.types import ProviderInfo, TranslationResult
from app.core.languages import get_language

logger = logging.getLogger("lecturelens.translation.mock")

# Tokens that must never be altered (structure / correctness identifiers)
_PROTECT = re.compile(
    r"(question-\d+|section-\d+|segment-\d+|\[S\d+\]|\b[ABCD]\b)"
)


class MockTranslation(TranslationProvider):
    name = "translation"

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="translation", provider="mock", mode="mock", loaded=True,
            detail="Structural demo translation (no NMT performed).",
        )

    def translate_batch(self, texts: List[str], source_lang: str,
                        target_lang: str) -> List[str]:
        src = get_language(source_lang).key
        tgt = get_language(target_lang).key
        if src == tgt:
            return list(texts)
        return [self._one(t, src, tgt) for t in texts]

    @staticmethod
    def _one(text: str, src: str, tgt: str) -> str:
        if not text:
            return text
        # protect structural tokens
        placeholders: List[str] = []

        def _stash(m: re.Match) -> str:
            placeholders.append(m.group(0))
            return f"\x00{len(placeholders) - 1}\x00"

        body = _PROTECT.sub(_stash, text)
        # deterministic per-line transform
        out_lines = []
        for line in body.split("\n"):
            if not line.strip():
                out_lines.append(line)
                continue
            digest = hashlib.md5(f"{src}>{tgt}>{line}".encode()).hexdigest()[:6]
            out_lines.append(f"[{tgt}:{digest}] {line.strip()}")
        result = "\n".join(out_lines)
        for i, ph in enumerate(placeholders):
            result = result.replace(f"\x00{i}\x00", ph)
        return result
