"""Quiz generation with strict validation and bounded retries."""
from __future__ import annotations

import logging
from typing import List, Tuple

from app.ai.llm.base import LLMProvider
from app.ai.types import GenerationContext, LLMResult
from app.core.config import settings
from app.schemas.api import QuizQuestionOut
from app.services.notes import with_retries
from app.services.validation import validate_quiz

logger = logging.getLogger("lecturelens.quiz")


def generate_quiz(llm: LLMProvider, ctx: GenerationContext,
                  max_segment_index: int) -> Tuple[List[QuizQuestionOut], LLMResult]:
    attempts = max(1, settings.quiz_retry_attempts + 1)
    last_error = None

    for i in range(1, attempts + 1):
        try:
            result = llm.generate_quiz(ctx)
            questions = validate_quiz(result.payload, max_segment_index)
            if len(questions) != 5:  # defensive — validate_quiz already checks
                raise ValueError("quiz length invariant violated")
            logger.info("Quiz generated on attempt %d/%d", i, attempts)
            return questions, result
        except Exception as exc:  # noqa: BLE001 — bounded retry on any bad output
            last_error = exc
            logger.warning("Quiz generation attempt %d/%d failed: %s",
                           i, attempts, exc)

    from app.core.errors import GenerationError
    if isinstance(last_error, GenerationError):
        raise last_error
    raise GenerationError(
        f"Quiz generation failed after {attempts} attempts: {last_error}")
