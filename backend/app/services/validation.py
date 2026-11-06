"""Strict validation for generated structured content.

Nothing from the LLM is trusted: every payload is parsed into Pydantic models
with cross-checks (exactly 5 questions, unique options, valid correct option,
non-empty explanations, no duplicate questions, segment references within
range). Validation failures raise GenerationError so the pipeline can retry
with a bounded number of attempts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from pydantic import ValidationError

from app.core.errors import GenerationError
from app.schemas.api import NotesContent, QuizOption, QuizQuestionOut

MAX_QUESTION_LENGTH = 500
MAX_OPTION_LENGTH = 300


def validate_notes(payload: Any, max_segment_index: int) -> NotesContent:
    try:
        notes = NotesContent.model_validate(payload)
    except ValidationError as exc:
        raise GenerationError(
            "Generated notes failed schema validation.",
            detail={"errors": exc.errors()[:8]},
        ) from exc

    # segment references must exist in the transcript
    valid = set(range(1, max_segment_index + 1))
    for section in notes.sections:
        bad = [s for s in section.source_segments if s not in valid]
        if bad:
            section.source_segments = [s for s in section.source_segments if s in valid]
        if not section.source_segments:
            raise GenerationError(
                f"Section '{section.heading}' has no valid source segment references.",
                detail={"invalid": bad, "max_segment_index": max_segment_index},
            )
        if not section.content or not any(c.strip() for c in section.content):
            raise GenerationError(f"Section '{section.heading}' has empty content.")
    for term in notes.key_terms:
        term.source_segments = [s for s in term.source_segments if s in valid]
    return notes


def validate_quiz(payload: Any, max_segment_index: int) -> List[QuizQuestionOut]:
    if not isinstance(payload, dict) or "questions" not in payload:
        raise GenerationError("Quiz payload must be an object with 'questions'.",
                              detail={"keys": list(payload)[:5] if isinstance(payload, dict) else type(payload).__name__})
    raw = payload["questions"]
    if not isinstance(raw, list) or len(raw) != 5:
        raise GenerationError(
            f"Quiz must contain exactly 5 questions (got "
            f"{len(raw) if isinstance(raw, list) else 'non-list'}).",
        )

    questions: List[QuizQuestionOut] = []
    seen_texts: Set[str] = set()
    valid_segments = set(range(1, max_segment_index + 1))

    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise GenerationError(f"Question {i} is not an object.")
        # normalize option ids defensively
        opts = item.get("options")
        if not isinstance(opts, list) or len(opts) != 4:
            raise GenerationError(
                f"Question {i} must have exactly 4 options "
                f"(got {len(opts) if isinstance(opts, list) else 'invalid'}).")
        normalized_opts = []
        for j, o in enumerate(opts):
            if not isinstance(o, dict):
                raise GenerationError(f"Question {i} option {j} is not an object.")
            text = str(o.get("text", "")).strip()
            if not text:
                raise GenerationError(f"Question {i} option {j} has empty text.")
            if len(text) > MAX_OPTION_LENGTH:
                text = text[:MAX_OPTION_LENGTH]
            normalized_opts.append({"id": "ABCD"[j], "text": text})
        texts = [o["text"].lower() for o in normalized_opts]
        if len(set(texts)) != 4:
            raise GenerationError(
                f"Question {i} has duplicate option texts.",
                detail={"options": [o['text'][:40] for o in normalized_opts]})

        correct = str(item.get("correct_option", "")).strip().upper()
        if correct not in ("A", "B", "C", "D"):
            raise GenerationError(
                f"Question {i} has invalid correct_option '{correct}'.")
        # correct option must correspond to a non-empty text (already checked)
        question_text = str(item.get("question", "")).strip()
        if not question_text:
            raise GenerationError(f"Question {i} has empty question text.")
        if len(question_text) > MAX_QUESTION_LENGTH:
            question_text = question_text[:MAX_QUESTION_LENGTH]
        explanation = str(item.get("explanation", "")).strip()
        if not explanation:
            raise GenerationError(f"Question {i} has empty explanation.")
        qkey = question_text.lower()
        if qkey in seen_texts:
            raise GenerationError(f"Duplicate question detected: '{question_text[:60]}...'")
        seen_texts.add(qkey)

        difficulty = str(item.get("difficulty", "medium")).lower()
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        src = item.get("source_segments", [])
        if not isinstance(src, list) or not src:
            raise GenerationError(
                f"Question {i} must reference at least one source segment.")
        src_clean = []
        for s in src:
            try:
                si = int(s)
            except (TypeError, ValueError):
                continue
            if si in valid_segments:
                src_clean.append(si)
        if not src_clean:
            raise GenerationError(
                f"Question {i} source_segments are out of range.",
                detail={"given": src, "max": max_segment_index})

        questions.append(QuizQuestionOut(
            id=str(item.get("id") or f"question-{i}"),
            question=question_text,
            options=[QuizOption(**o) for o in normalized_opts],
            correct_option=correct,  # type: ignore[arg-type]
            explanation=explanation,
            difficulty=difficulty,
            source_segments=sorted(set(src_clean)),
        ))

    # ensure unique ids
    ids = [q.id for q in questions]
    if len(set(ids)) != 5:
        for n, q in enumerate(questions, start=1):
            q.id = f"question-{n}"
    return questions
