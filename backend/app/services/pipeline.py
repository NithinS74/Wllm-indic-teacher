"""Full processing pipeline — executed ONLY inside the background worker.

Stages (actual work items drive the stage list):
  PREPROCESSING -> TRANSCRIBING -> [TRANSLATING_INPUT] -> [GENERATING_NOTES]
  -> [GENERATING_QUIZ] -> [TRANSLATING_OUTPUT] -> VALIDATING -> COMPLETED

Progress = completed stages / total stages. Failures always end as FAILED
with a user-readable message — never silently COMPLETED.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import (
    get_asr_provider,
    get_llm_provider,
    get_translation_provider,
)
from app.ai.types import GenerationContext
from app.core.config import settings
from app.core.errors import AppError, GenerationError, ModelLoadError
from app.core.languages import get_language
from app.db.session import new_session
from app.models.entities import (
    Job,
    JobKind,
    JobStatus,
    Lecture,
    LectureStatus,
    Note,
    QuizQuestion,
    TranscriptSegment,
)
from app.services import audio as audio_service
from app.services import notes as notes_service
from app.services import quiz as quiz_service
from app.services import translation as translation_service
from app.services.segmentation import build_segments, dedupe_overlap

logger = logging.getLogger("lecturelens.pipeline")

# Terminal stages never used as "current" progress anchors
_ALL_STAGES: List[JobStatus] = [
    JobStatus.QUEUED,
    JobStatus.PREPROCESSING,
    JobStatus.TRANSCRIBING,
    JobStatus.TRANSLATING_INPUT,
    JobStatus.GENERATING_NOTES,
    JobStatus.GENERATING_QUIZ,
    JobStatus.TRANSLATING_OUTPUT,
    JobStatus.VALIDATING,
    JobStatus.COMPLETED,
]


def plan_stages(lecture: Lecture) -> List[JobStatus]:
    """Actual stages for this job — progress reflects real work items."""
    stages: List[JobStatus] = [
        JobStatus.QUEUED,
        JobStatus.PREPROCESSING,
        JobStatus.TRANSCRIBING,
    ]
    needs_input_translation = (
        lecture.source_language != "en"  # canonical generation language is English
    )
    if needs_input_translation:
        stages.append(JobStatus.TRANSLATING_INPUT)
    if lecture.generate_notes:
        stages.append(JobStatus.GENERATING_NOTES)
    if lecture.generate_quiz:
        stages.append(JobStatus.GENERATING_QUIZ)
    if lecture.translate_content and lecture.target_language and \
            lecture.target_language != "en":
        stages.append(JobStatus.TRANSLATING_OUTPUT)
    stages.append(JobStatus.VALIDATING)
    stages.append(JobStatus.COMPLETED)
    return stages


def _progress(stages: List[JobStatus], current: JobStatus) -> float:
    """completed = number of stages strictly before `current`."""
    try:
        idx = stages.index(current)
    except ValueError:
        return 0.0
    total = max(1, len(stages) - 1)  # COMPLETED counts as full credit
    return round(min(1.0, idx / total), 4)


def _set_stage(db: Session, job: Job, stage: JobStatus) -> None:
    job.current_stage = stage
    job.status = stage if stage not in (JobStatus.COMPLETED, JobStatus.FAILED) else stage
    job.progress = _progress(_stages_of(job), stage)
    db.commit()
    logger.info("job=%s stage=%s progress=%.2f", job.id, stage.value, job.progress)


def _stages_of(job: Job) -> List[JobStatus]:
    if job.stages:
        return [JobStatus(s) for s in job.stages]
    return _ALL_STAGES


def run_processing_pipeline(lecture_id: str) -> None:
    """Entry point executed by the RQ worker (or inline in tests/demo)."""
    db = new_session()
    try:
        lecture = db.get(Lecture, lecture_id)
        if lecture is None:
            logger.error("Lecture %s not found", lecture_id)
            return
        job = db.execute(
            select(Job).where(Job.lecture_id == lecture_id,
                              Job.kind == JobKind.PROCESSING)
            .order_by(Job.created_at.desc())
        ).scalars().first()
        if job is None:
            job = Job(lecture_id=lecture_id, kind=JobKind.PROCESSING)
            db.add(job)
            db.commit()

        job.stages = [s.value for s in plan_stages(lecture)]
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        db.commit()
        lecture.status = LectureStatus.PROCESSING
        db.commit()

        try:
            _run_stages(db, lecture, job)
            job.status = JobStatus.COMPLETED
            job.current_stage = JobStatus.COMPLETED
            job.progress = 1.0
            job.completed_at = datetime.now(timezone.utc)
            lecture.status = LectureStatus.COMPLETED
            db.commit()
            logger.info("Lecture %s completed", lecture_id)
        except Exception as exc:  # noqa: BLE001 — convert to FAILED state
            db.rollback()
            message = _friendly_error(exc)
            job = db.get(Job, job.id)
            lecture = db.get(Lecture, lecture_id)
            if job is not None:
                job.status = JobStatus.FAILED
                job.error_message = message[:4000]
                job.completed_at = datetime.now(timezone.utc)
            if lecture is not None:
                lecture.status = LectureStatus.FAILED
            db.commit()
            logger.exception("Lecture %s failed: %s", lecture_id, message)
            raise
    finally:
        db.close()


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, (ModelLoadError, GenerationError, AppError)):
        return exc.message
    return f"{type(exc).__name__}: {exc}"


def _run_stages(db: Session, lecture: Lecture, job: Job) -> None:
    stages = _stages_of(job)

    # ---------------------------------------------------------- preprocess
    _set_stage(db, job, JobStatus.PREPROCESSING)
    src_path = _resolve_upload(lecture.audio_path)
    info = audio_service.validate_upload(src_path)
    lecture.duration = info.duration
    db.commit()
    processed = audio_service.preprocess(src_path)
    pcm = audio_service.extract_pcm(processed)
    segs = build_segments(pcm, settings.target_sample_rate, info.duration)
    chunk_times = [(s.start, s.end) for s in segs]
    logger.info("Audio %.1fs -> %d speech-aware chunks", info.duration, len(segs))

    # ------------------------------------------------------------ transcribe
    _set_stage(db, job, JobStatus.TRANSCRIBING)
    asr = get_asr_provider()
    asr_result = asr.transcribe(processed, lecture.source_language, chunk_times)

    # merge with overlap de-duplication
    merged: List[Tuple[float, float, str]] = []
    prev_text = ""
    for seg_res in asr_result.segments:
        text = seg_res.text.strip()
        if not text:
            continue
        text = dedupe_overlap(prev_text, text, settings.chunk_overlap_seconds)
        if not text.strip():
            continue
        prev_text = seg_res.text.strip()
        merged.append((seg_res.start, seg_res.end, text.strip()))

    if not merged:
        raise AppError(
            "Speech recognition produced no text. The recording may contain "
            "no audible speech.", code="empty_transcript")

    # clear old segments (idempotent re-runs)
    for old in db.execute(
            select(TranscriptSegment).where(
                TranscriptSegment.lecture_id == lecture.id)).scalars():
        db.delete(old)
    db.commit()
    for i, (start, end, text) in enumerate(merged, start=1):
        db.add(TranscriptSegment(
            lecture_id=lecture.id, segment_index=i, start_time=start,
            end_time=end, text=text, language=lecture.source_language,
            segment_order=i, is_mock=asr_result.is_mock,
        ))
    db.commit()

    segment_rows = db.execute(
        select(TranscriptSegment).where(TranscriptSegment.lecture_id == lecture.id)
        .order_by(TranscriptSegment.segment_order)).scalars().all()
    max_idx = len(segment_rows)
    segment_texts = [s.text for s in segment_rows]
    segment_indices = [s.segment_index for s in segment_rows]
    transcript_text = "\n".join(segment_texts)

    # ------------------------------------------------- input translation
    eng_texts = segment_texts
    if JobStatus.TRANSLATING_INPUT in stages:
        _set_stage(db, job, JobStatus.TRANSLATING_INPUT)
        translator = get_translation_provider()
        eng_texts = translator.translate_batch(
            segment_texts, lecture.source_language, "en")

    # ------------------------------------------------------- notes + quiz
    ctx = GenerationContext(
        lecture_id=lecture.id,
        lecture_title=lecture.title,
        source_language="en",
        transcript_text="\n".join(eng_texts),
        segment_texts=eng_texts,
        segment_indices=segment_indices,
    )
    llm = get_llm_provider()
    notes_payload = None
    quiz_questions = None
    notes_meta = None
    quiz_meta = None

    if JobStatus.GENERATING_NOTES in stages:
        _set_stage(db, job, JobStatus.GENERATING_NOTES)
        notes_payload, notes_meta = notes_service.generate_notes(
            llm, ctx, max_idx)
        _save_notes(db, lecture, "en", notes_payload.model_dump(),
                    notes_meta.is_mock)

    if JobStatus.GENERATING_QUIZ in stages:
        _set_stage(db, job, JobStatus.GENERATING_QUIZ)
        quiz_questions, quiz_meta = quiz_service.generate_quiz(
            llm, ctx, max_idx)
        _save_quiz(db, lecture, "en", quiz_questions,
                   quiz_meta.is_mock)

    # ------------------------------------------------- output translation
    if JobStatus.TRANSLATING_OUTPUT in stages:
        _set_stage(db, job, JobStatus.TRANSLATING_OUTPUT)
        target = lecture.target_language
        for ctype in ("transcript", "notes", "quiz"):
            try:
                translation_service.translate_content(
                    db, lecture, ctype, target)
            except Exception as exc:  # noqa: BLE001
                # A failed optional translation must fail the job (visible),
                # never silently produce partial results.
                raise

    # ------------------------------------------------------------ validate
    _set_stage(db, job, JobStatus.VALIDATING)
    _validate_persisted(db, lecture, generate_notes=lecture.generate_notes,
                        generate_quiz=lecture.generate_quiz)


def _resolve_upload(audio_path: str):
    from pathlib import Path
    p = Path(audio_path)
    if not p.is_absolute():
        p = settings.storage_root / p
    if not p.exists():
        from app.core.errors import NotFoundError
        raise NotFoundError("Uploaded audio file is missing from storage.")
    return p


def _save_notes(db: Session, lecture: Lecture, language: str, payload: dict,
                is_mock: bool) -> None:
    existing = db.execute(
        select(Note).where(Note.lecture_id == lecture.id,
                           Note.language == language)).scalar_one_or_none()
    if existing:
        existing.content = payload
        existing.is_mock = is_mock
    else:
        db.add(Note(lecture_id=lecture.id, language=language,
                    content=payload, is_mock=is_mock))
    db.commit()


def _save_quiz(db: Session, lecture: Lecture, language: str, questions,
               is_mock: bool) -> None:
    for old in db.execute(
            select(QuizQuestion).where(
                QuizQuestion.lecture_id == lecture.id)).scalars():
        db.delete(old)
    db.commit()
    for i, q in enumerate(questions, start=1):
        db.add(QuizQuestion(
            lecture_id=lecture.id,
            question_key=q.id,
            question=q.question,
            options=[o.model_dump() for o in q.options],
            correct_option=q.correct_option,
            explanation=q.explanation,
            difficulty=q.difficulty,
            source_segments=q.source_segments,
            language=language,
            is_mock=is_mock,
            sort_order=i,
        ))
    db.commit()


def _validate_persisted(db: Session, lecture: Lecture,
                        generate_notes: bool, generate_quiz: bool) -> None:
    seg_count = len(db.execute(
        select(TranscriptSegment).where(
            TranscriptSegment.lecture_id == lecture.id)).scalars().all())
    if seg_count == 0:
        raise AppError("Validation failed: transcript is empty.",
                       code="validation_error")
    if generate_notes:
        note = db.execute(
            select(Note).where(Note.lecture_id == lecture.id)).scalars().first()
        if note is None:
            raise AppError("Validation failed: notes missing after generation.",
                           code="validation_error")
        from app.schemas.api import NotesContent
        NotesContent.model_validate(note.content)
    if generate_quiz:
        qs = db.execute(
            select(QuizQuestion).where(
                QuizQuestion.lecture_id == lecture.id)).scalars().all()
        if len(qs) != 5:
            raise AppError(
                f"Validation failed: expected 5 questions, found {len(qs)}.",
                code="validation_error")
        for q in qs:
            if len(q.options) != 4:
                raise AppError("Validation failed: question options != 4.",
                               code="validation_error")
            if q.correct_option not in [o["id"] for o in q.options]:
                raise AppError("Validation failed: correct option mismatch.",
                               code="validation_error")
            if not (q.explanation or "").strip():
                raise AppError("Validation failed: empty explanation.",
                               code="validation_error")


def run_translation_pipeline(lecture_id: str, content_types: List[str],
                             language: str) -> None:
    """Background translation job (on-demand language switch)."""
    db = new_session()
    job = None
    try:
        lecture = db.get(Lecture, lecture_id)
        if lecture is None:
            logger.error("Lecture %s not found for translation", lecture_id)
            return
        job = db.execute(
            select(Job).where(Job.lecture_id == lecture_id,
                              Job.kind == JobKind.TRANSLATION)
            .order_by(Job.created_at.desc())
        ).scalars().first()
        if job is None:
            job = Job(lecture_id=lecture_id, kind=JobKind.TRANSLATION)
            db.add(job)
            db.commit()
        job.stages = [JobStatus.QUEUED.value, JobStatus.TRANSLATING_OUTPUT.value,
                      JobStatus.COMPLETED.value]
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        db.commit()

        _set_stage(db, job, JobStatus.TRANSLATING_OUTPUT)
        for ctype in content_types:
            translation_service.translate_content(db, lecture, ctype, language)
        job.status = JobStatus.COMPLETED
        job.current_stage = JobStatus.COMPLETED
        job.progress = 1.0
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if job is not None:
            job = db.get(Job, job.id)
            if job is not None:
                job.status = JobStatus.FAILED
                job.error_message = _friendly_error(exc)[:4000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        logger.exception("Translation job failed: %s", exc)
        raise
    finally:
        db.close()
