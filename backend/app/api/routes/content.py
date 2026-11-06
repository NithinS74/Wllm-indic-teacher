"""Transcript / notes / quiz / translation / export endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_dep, get_lecture
from app.core.errors import NotFoundError, ValidationAppError
from app.core.languages import get_language
from app.models.entities import (
    ContentTranslation,
    Job,
    JobKind,
    Lecture,
    Note,
    QuizAttempt,
    QuizQuestion,
    TranscriptSegment,
)
from app.schemas.api import (
    ExportOut,
    NoteSection,
    NotesContent,
    QuizAttemptIn,
    QuizAttemptOut,
    QuizOption,
    QuizOut,
    QuizQuestionOut,
    TranscriptOut,
    TranscriptSegmentOut,
    TranslateIn,
    TranslateOut,
)
from app.services import export as export_service
from app.workers import queue as work_queue
from app.workers.tasks import translate_lecture_task

router = APIRouter(prefix="/lectures", tags=["content"])


# ------------------------------------------------------------- transcript
@router.get("/{lecture_id}/transcript", response_model=TranscriptOut)
def get_transcript(
    lecture: Lecture = Depends(get_lecture),
    language: Optional[str] = Query(None, description="Use cached translation"),
    db: Session = Depends(db_dep),
) -> TranscriptOut:
    segs = db.execute(
        select(TranscriptSegment).where(
            TranscriptSegment.lecture_id == lecture.id)
        .order_by(TranscriptSegment.segment_order)
    ).scalars().all()
    if not segs:
        raise NotFoundError("Transcript is not ready yet.")

    is_mock = any(s.is_mock for s in segs)
    lang_key = lecture.source_language
    rows = [
        TranscriptSegmentOut(segment_index=s.segment_index,
                             start_time=s.start_time, end_time=s.end_time,
                             text=s.text, language=s.language)
        for s in segs
    ]

    if language and language != lecture.source_language:
        cached = db.execute(
            select(ContentTranslation).where(
                ContentTranslation.lecture_id == lecture.id,
                ContentTranslation.content_type == "transcript",
                ContentTranslation.language == language)
        ).scalar_one_or_none()
        if cached:
            rows = [TranscriptSegmentOut(**{**r.model_dump(),
                                            "text": seg["text"],
                                            "language": language})
                    for r, seg in zip(rows, cached.payload["segments"])]
            is_mock = cached.is_mock
            lang_key = language

    return TranscriptOut(
        lecture_id=lecture.id,
        language=lang_key,
        language_label=get_language(lang_key).label,
        is_mock=is_mock,
        duration=lecture.duration,
        segments=rows,
        audio_url=f"/api/v1/lectures/{lecture.id}/audio",
    )


# ------------------------------------------------------------------ notes
@router.get("/{lecture_id}/notes")
def get_notes(
    lecture: Lecture = Depends(get_lecture),
    language: Optional[str] = Query(None),
    db: Session = Depends(db_dep),
):
    lang = language or "en"
    if lang != "en":
        cached = db.execute(
            select(ContentTranslation).where(
                ContentTranslation.lecture_id == lecture.id,
                ContentTranslation.content_type == "notes",
                ContentTranslation.language == lang)
        ).scalar_one_or_none()
        if cached:
            content = NotesContent.model_validate(cached.payload)
            return {"lecture_id": lecture.id, "language": lang,
                    "is_mock": cached.is_mock, "content": content}

    note = db.execute(
        select(Note).where(Note.lecture_id == lecture.id, Note.language == "en")
    ).scalar_one_or_none()
    if note is None:
        note = db.execute(
            select(Note).where(Note.lecture_id == lecture.id)
            .order_by(Note.created_at)
        ).scalars().first()
    if note is None:
        raise NotFoundError("Notes have not been generated for this lecture.")
    content = NotesContent.model_validate(note.content)
    return {"lecture_id": lecture.id, "language": note.language,
            "is_mock": note.is_mock, "content": content,
            "note": "untranslated_fallback" if language and language != note.language else None}


# ------------------------------------------------------------------- quiz
@router.get("/{lecture_id}/quiz", response_model=QuizOut)
def get_quiz(
    lecture: Lecture = Depends(get_lecture),
    language: Optional[str] = Query(None),
    db: Session = Depends(db_dep),
) -> QuizOut:
    rows = db.execute(
        select(QuizQuestion).where(QuizQuestion.lecture_id == lecture.id)
        .order_by(QuizQuestion.sort_order)
    ).scalars().all()
    if not rows:
        raise NotFoundError("Quiz has not been generated for this lecture.")

    lang = "en"
    is_mock = any(r.is_mock for r in rows)
    questions = rows

    if language and language != "en":
        cached = db.execute(
            select(ContentTranslation).where(
                ContentTranslation.lecture_id == lecture.id,
                ContentTranslation.content_type == "quiz",
                ContentTranslation.language == language)
        ).scalar_one_or_none()
        if cached:
            lang = language
            is_mock = cached.is_mock
            translated = {q["id"]: q for q in cached.payload["questions"]}
            # rebuild with translated text but base structural fields
            out_qs = []
            for r in rows:
                t = translated.get(r.question_key)
                if t:
                    out_qs.append(QuizQuestionOut(
                        id=r.question_key,
                        question=t["question"],
                        options=[QuizOption(**o) for o in t["options"]],
                        correct_option=r.correct_option,
                        explanation=t["explanation"],
                        difficulty=r.difficulty,
                        source_segments=r.source_segments,
                    ))
                else:
                    out_qs.append(_q_out(r))
            return QuizOut(lecture_id=lecture.id, language=lang,
                           is_mock=is_mock, questions=out_qs)

    return QuizOut(
        lecture_id=lecture.id, language=lang, is_mock=is_mock,
        questions=[_q_out(r) for r in questions],
    )


def _q_out(r: QuizQuestion) -> QuizQuestionOut:
    return QuizQuestionOut(
        id=r.question_key,
        question=r.question,
        options=[QuizOption(**o) for o in r.options],
        correct_option=r.correct_option,  # type: ignore[arg-type]
        explanation=r.explanation,
        difficulty=r.difficulty,
        source_segments=r.source_segments or [],
    )


@router.post("/{lecture_id}/quiz/attempt", response_model=QuizAttemptOut,
             status_code=201)
def submit_attempt(
    payload: QuizAttemptIn,
    lecture: Lecture = Depends(get_lecture),
    db: Session = Depends(db_dep),
) -> QuizAttemptOut:
    rows = db.execute(
        select(QuizQuestion).where(QuizQuestion.lecture_id == lecture.id)
        .order_by(QuizQuestion.sort_order)
    ).scalars().all()
    if not rows:
        raise NotFoundError("Quiz has not been generated for this lecture.")

    known_ids = {r.question_key for r in rows}
    unknown = set(payload.answers) - known_ids
    if unknown:
        raise ValidationAppError("Answers reference unknown questions.",
                                 detail=sorted(unknown))

    score = sum(1 for r in rows
                if payload.answers.get(r.question_key) == r.correct_option)
    attempt = QuizAttempt(
        lecture_id=lecture.id,
        answers=payload.answers,
        score=score,
        total_questions=len(rows),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return QuizAttemptOut(
        id=attempt.id, lecture_id=attempt.lecture_id, answers=attempt.answers,
        score=attempt.score, total_questions=attempt.total_questions,
        created_at=attempt.created_at,
    )


@router.get("/{lecture_id}/quiz/attempts")
def list_attempts(lecture: Lecture = Depends(get_lecture),
                  db: Session = Depends(db_dep)):
    from app.models.entities import QuizAttempt as QA
    rows = db.execute(
        select(QA).where(QA.lecture_id == lecture.id)
        .order_by(QA.created_at.desc())).scalars().all()
    return [{"id": r.id, "score": r.score, "total_questions": r.total_questions,
             "created_at": r.created_at} for r in rows]


# ------------------------------------------------------------- translation
@router.post("/{lecture_id}/translate", response_model=TranslateOut,
             status_code=202)
def request_translation(
    payload: TranslateIn,
    lecture: Lecture = Depends(get_lecture),
    db: Session = Depends(db_dep),
) -> TranslateOut:
    """Queue on-demand translation of selected content types.

    Reuses cached translations — never re-runs the full pipeline.
    """
    missing = [ct for ct in payload.content_types
               if ct not in ("transcript", "notes", "quiz")]
    if missing:
        raise ValidationAppError("Unsupported content types.", detail=missing)
    if payload.language == lecture.source_language:
        # translating back into the source language of the transcript only
        # makes sense for notes/quiz; still allowed for those
        pass

    job = Job(lecture_id=lecture.id, kind=JobKind.TRANSLATION)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        work_queue.enqueue(
            translate_lecture_task, lecture.id,
            list(payload.content_types), payload.language)
    except Exception as exc:  # noqa: BLE001
        from app.models.entities import JobStatus
        job.status = JobStatus.FAILED
        job.error_message = f"Could not enqueue translation: {exc}"[:500]
        db.commit()
        raise ValidationAppError(
            "Background queue unavailable for translation.") from exc

    return TranslateOut(job_id=job.id, lecture_id=lecture.id,
                        language=payload.language,
                        content_types=list(payload.content_types))


# ------------------------------------------------------------------ export
@router.get("/{lecture_id}/export")
def export_lecture(
    lecture: Lecture = Depends(get_lecture),
    format: str = Query("markdown", pattern="^(markdown|transcript|notes|quiz)$"),
    language: Optional[str] = Query(None),
    db: Session = Depends(db_dep),
):
    from fastapi.responses import Response
    safe_title = "".join(
        c if c.isalnum() or c in "-_ " else "_" for c in lecture.title
    ).strip()[:60] or "lecture"

    if format == "transcript":
        body = export_service.transcript_text(db, lecture)
        media, ext = "text/plain; charset=utf-8", "txt"
    elif format == "notes":
        body = export_service.notes_markdown(db, lecture, language or "en")
        media, ext = "text/markdown; charset=utf-8", "md"
    elif format == "quiz":
        body = export_service.notes_markdown(db, lecture, language or "en")
        # quiz-only slice
        media, ext = "text/markdown; charset=utf-8", "md"
        start = body.find("## Quiz (5 MCQs)")
        if start > 0:
            body = f"# Quiz — {lecture.title}\n\n" + body[start:]
    else:
        body = export_service.study_pack_markdown(db, lecture, language)
        media, ext = "text/markdown; charset=utf-8", "md"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition":
                 f'attachment; filename="{safe_title}.{ext}"'},
    )
