"""On-demand content translation with caching.

Translates transcript / notes / quiz into a target language WITHOUT re-running
the processing pipeline. Results are cached in `content_translations` keyed by
(lecture, content_type, language). Structural identifiers (question ids,
option ids A–D, correct_option, section ids, segment indices) are preserved
verbatim — only textual fields are translated.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_translation_provider
from app.core.errors import NotFoundError, ValidationAppError
from app.core.languages import get_language
from app.models.entities import (
    ContentTranslation,
    Lecture,
    Note,
    QuizQuestion,
    TranscriptSegment,
)
from app.schemas.api import NotesContent

logger = logging.getLogger("lecturelens.translation")


def get_cached(db: Session, lecture_id: str, content_type: str,
               language: str) -> ContentTranslation | None:
    return db.execute(
        select(ContentTranslation).where(
            ContentTranslation.lecture_id == lecture_id,
            ContentTranslation.content_type == content_type,
            ContentTranslation.language == language,
        )
    ).scalar_one_or_none()


def _base_transcript(db: Session, lecture: Lecture) -> Dict[str, Any]:
    segs = db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.lecture_id == lecture.id)
        .order_by(TranscriptSegment.segment_order)
    ).scalars().all()
    return {
        "segments": [
            {"segment_index": s.segment_index, "start_time": s.start_time,
             "end_time": s.end_time, "text": s.text}
            for s in segs
        ]
    }


def _base_notes(db: Session, lecture: Lecture, language: str = "en") -> Dict[str, Any]:
    note = db.execute(
        select(Note).where(Note.lecture_id == lecture.id,
                           Note.language == language)
    ).scalar_one_or_none()
    if note is None:
        note = db.execute(
            select(Note).where(Note.lecture_id == lecture.id)
            .order_by(Note.created_at)
        ).scalars().first()
    if note is None:
        raise NotFoundError("Notes have not been generated for this lecture yet.")
    return dict(note.content)


def _base_quiz(db: Session, lecture: Lecture) -> Dict[str, Any]:
    qs = db.execute(
        select(QuizQuestion).where(QuizQuestion.lecture_id == lecture.id)
        .order_by(QuizQuestion.sort_order)
    ).scalars().all()
    if not qs:
        raise NotFoundError("Quiz has not been generated for this lecture yet.")
    return {"questions": [
        {
            "id": q.question_key,
            "question": q.question,
            "options": q.options,
            "correct_option": q.correct_option,
            "explanation": q.explanation,
            "difficulty": q.difficulty,
            "source_segments": q.source_segments,
        }
        for q in qs
    ]}


def translate_content(db: Session, lecture: Lecture, content_type: str,
                      target_language: str) -> ContentTranslation:
    """Translate one content type into `target_language` and cache it."""
    provider = get_translation_provider()
    source_lang = lecture.source_language
    # Generated notes/quiz are stored in the canonical generation language (en);
    # the transcript lives in the source language.
    base_lang = "en" if content_type in ("notes", "quiz") else source_lang
    if target_language == base_lang:
        raise ValidationAppError("Target language equals the source content language.")

    cached = get_cached(db, lecture.id, content_type, target_language)
    if cached is not None:
        return cached

    if content_type == "transcript":
        payload = _base_transcript(db, lecture)
        texts = [s["text"] for s in payload["segments"]]
        translated = provider.translate_batch(texts, base_lang, target_language)
        for seg, t in zip(payload["segments"], translated):
            seg["text"] = t
        payload["language"] = target_language
    elif content_type == "notes":
        payload = _base_notes(db, lecture, base_lang)
        notes = NotesContent.model_validate(payload)
        # translate all textual fields in one batch to limit round-trips
        fields: List[tuple] = []  # (setter_path, text)
        texts: List[str] = []

        def add(path, text):
            fields.append(path)
            texts.append(text)

        add(("title",), notes.title)
        add(("overview",), notes.overview)
        for i, s in enumerate(notes.sections):
            add(("sections", i, "heading"), s.heading)
            for j, c in enumerate(s.content):
                add(("sections", i, "content", j), c)
        for i, t in enumerate(notes.key_terms):
            add(("key_terms", i, "term"), t.term)
            add(("key_terms", i, "definition"), t.definition)
        for i, t in enumerate(notes.key_takeaways):
            add(("key_takeaways", i), t)
        for i, t in enumerate(notes.examples):
            add(("examples", i), t)
        for i, t in enumerate(notes.important_points):
            add(("important_points", i), t)
        for i, t in enumerate(notes.uncertain):
            add(("uncertain", i), t)

        out_texts = provider.translate_batch(texts, base_lang, target_language)
        data = notes.model_dump()
        for path, text in zip(fields, out_texts):
            _set_path(data, path, text)
        payload = data
        payload["language"] = target_language
    elif content_type == "quiz":
        payload = _base_quiz(db, lecture)
        texts: List[str] = []
        fields: List[tuple] = []
        for qi, q in enumerate(payload["questions"]):
            fields.append(("questions", qi, "question"))
            texts.append(q["question"])
            fields.append(("questions", qi, "explanation"))
            texts.append(q["explanation"])
            for oi, opt in enumerate(q["options"]):
                fields.append(("questions", qi, "options", oi, "text"))
                texts.append(opt["text"])
        out_texts = provider.translate_batch(texts, base_lang, target_language)
        for path, text in zip(fields, out_texts):
            _set_path(payload, path, text)
        payload["language"] = target_language
    else:
        raise ValidationAppError(f"Unknown content type '{content_type}'.")

    existing = get_cached(db, lecture.id, content_type, target_language)
    if existing is not None:
        return existing
    row = ContentTranslation(
        lecture_id=lecture.id,
        content_type=content_type,
        language=target_language,
        payload=payload,
        is_mock=provider.is_mock,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("Cached %s translation to %s for lecture %s",
                content_type, target_language, lecture.id)
    return row


def _set_path(data: Any, path: tuple, value: Any) -> None:
    cur = data
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = value


def available_languages(db: Session, lecture: Lecture) -> List[str]:
    rows = db.execute(
        select(ContentTranslation.language).where(
            ContentTranslation.lecture_id == lecture.id).distinct()
    ).scalars().all()
    return sorted(set(rows))
