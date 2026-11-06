"""Lecture CRUD + processing endpoints."""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import db_dep, get_lecture
from app.core.config import settings
from app.core.errors import (
    FileTooLargeError,
    NotFoundError,
    UnsupportedMediaError,
    ValidationAppError,
)
from app.core.languages import get_language
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
from app.schemas.api import LectureCreate, LectureDetail, LectureSummary, JobOut
from app.services import storage
from app.workers import queue as work_queue
from app.workers.tasks import process_lecture_task

logger = logging.getLogger("lecturelens.api.lectures")
router = APIRouter(prefix="/lectures", tags=["lectures"])


def _latest_job(db: Session, lecture_id: str) -> Optional[Job]:
    return db.execute(
        select(Job).where(Job.lecture_id == lecture_id)
        .order_by(Job.created_at.desc())
    ).scalars().first()


def _summary(db: Session, lecture: Lecture) -> LectureSummary:
    job = _latest_job(db, lecture.id)
    return LectureSummary(
        id=lecture.id,
        title=lecture.title,
        source_language=lecture.source_language,
        target_language=lecture.target_language,
        duration=lecture.duration,
        status=lecture.status.value,
        generate_notes=lecture.generate_notes,
        generate_quiz=lecture.generate_quiz,
        translate_content=lecture.translate_content,
        providers=lecture.providers,
        created_at=lecture.created_at,
        updated_at=lecture.updated_at,
        job_id=job.id if job else None,
        job_status=job.status.value if job else None,
        current_stage=job.current_stage.value if job else None,
        progress=job.progress if job else None,
        error_message=job.error_message if job else None,
        audio_original_name=lecture.audio_original_name,
    )


@router.post("", response_model=LectureSummary, status_code=201)
def create_lecture(
    title: str = Form(..., min_length=1, max_length=300),
    source_language: str = Form(...),
    target_language: Optional[str] = Form(None),
    generate_notes: bool = Form(True),
    generate_quiz: bool = Form(True),
    translate_content: bool = Form(False),
    audio: UploadFile = File(...),
    db: Session = Depends(db_dep),
) -> LectureSummary:
    """Validate form + audio, store it, create job, enqueue processing."""
    # Validate the form fields through Pydantic
    try:
        form = LectureCreate(
            title=title,
            source_language=source_language,
            target_language=target_language or None,
            generate_notes=generate_notes,
            generate_quiz=generate_quiz,
            translate_content=translate_content,
        )
    except Exception as exc:  # pydantic ValidationError
        raise ValidationAppError("Invalid form data.",
                                 detail=str(exc)[:500]) from exc

    if form.translate_content and not form.target_language:
        raise ValidationAppError(
            "target_language is required when translate_content is enabled.")
    if form.target_language == form.source_language and form.translate_content:
        raise ValidationAppError(
            "Source and target languages must differ when translation is enabled.")

    # File validation
    original_name = storage.safe_original_filename(audio.filename or "audio")
    ext = Path(original_name).suffix.lower()
    if ext not in settings.allowed_extensions_set:
        raise UnsupportedMediaError(
            f"File type '{ext or original_name}' is not allowed.",
            detail={"allowed": sorted(settings.allowed_extensions_set)})

    dest = storage.build_upload_path(original_name)
    storage.save_stream(audio.file, dest, settings.max_upload_bytes)

    # Content sniffing: the file must actually decode as audio
    from app.services.audio import probe
    try:
        info = probe(dest)
    except Exception as exc:  # noqa: BLE001 — clean up rejected uploads
        storage.delete_quiet(dest)
        if isinstance(exc, (UnsupportedMediaError, ValidationAppError)):
            raise
        raise UnsupportedMediaError(
            "The uploaded file could not be read as audio.",
            detail=str(exc)[:400]) from exc

    lecture = Lecture(
        title=form.title,
        audio_path=str(dest.relative_to(settings.storage_root)),
        audio_original_name=original_name,
        audio_mime=audio.content_type or mimetypes.guess_type(original_name)[0],
        source_language=form.source_language,
        target_language=form.target_language,
        duration=info.duration,
        status=LectureStatus.QUEUED,
        generate_notes=form.generate_notes,
        generate_quiz=form.generate_quiz,
        translate_content=form.translate_content,
        providers={
            "asr": settings.asr_provider,
            "llm": settings.llm_provider,
            "translation": settings.translation_provider,
        },
    )
    db.add(lecture)
    db.flush()
    job = Job(lecture_id=lecture.id, kind=JobKind.PROCESSING,
              status=JobStatus.QUEUED, current_stage=JobStatus.QUEUED,
              progress=0.0)
    db.add(job)
    db.commit()
    db.refresh(lecture)

    try:
        work_queue.enqueue(process_lecture_task, lecture.id)
    except Exception as exc:  # noqa: BLE001 — Redis down etc.
        logger.exception("Failed to enqueue lecture %s", lecture.id)
        job.status = JobStatus.FAILED
        job.error_message = f"Could not enqueue processing job: {exc}"[:500]
        lecture.status = LectureStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Background queue is unavailable. Please retry later.") from exc

    logger.info("Lecture %s uploaded (%.1fs, %s)", lecture.id,
                info.duration, original_name)
    # In inline mode the pipeline already ran in another session — re-read so
    # the response reflects the real status (QUEUED when async).
    db.refresh(lecture)
    return _summary(db, lecture)


@router.get("", response_model=List[LectureSummary])
def list_lectures(limit: int = 50, db: Session = Depends(db_dep)) -> List[LectureSummary]:
    lectures = db.execute(
        select(Lecture).order_by(Lecture.created_at.desc())
        .limit(min(max(limit, 1), 200))
    ).scalars().all()
    return [_summary(db, lec) for lec in lectures]


@router.get("/{lecture_id}", response_model=LectureDetail)
def lecture_detail(lecture: Lecture = Depends(get_lecture),
                   db: Session = Depends(db_dep)) -> LectureDetail:
    base = _summary(db, lecture)
    seg_count = db.execute(
        select(func.count()).select_from(TranscriptSegment).where(
            TranscriptSegment.lecture_id == lecture.id)).scalar_one()
    notes = db.execute(
        select(Note.language).where(Note.lecture_id == lecture.id)).scalars().all()
    # Also surface cached on-demand translations of notes (ContentTranslation)
    from app.models.entities import ContentTranslation
    note_xlate = db.execute(
        select(ContentTranslation.language).where(
            ContentTranslation.lecture_id == lecture.id,
            ContentTranslation.content_type == "notes")
    ).scalars().all()
    quiz_count = db.execute(
        select(func.count()).select_from(QuizQuestion).where(
            QuizQuestion.lecture_id == lecture.id)).scalar_one()
    from app.services.translation import available_languages
    return LectureDetail(
        **base.model_dump(),
        has_transcript=seg_count > 0,
        has_notes=len(notes) > 0,
        has_quiz=quiz_count > 0,
        available_note_languages=sorted(set(notes) | set(note_xlate)),
        available_translation_languages=available_languages(db, lecture),
    )


@router.delete("/{lecture_id}", status_code=204)
def delete_lecture(lecture: Lecture = Depends(get_lecture),
                   db: Session = Depends(db_dep)) -> None:
    # remove uploaded + preprocessed audio files
    uploaded = settings.storage_root / lecture.audio_path
    storage.delete_quiet(uploaded)
    storage.delete_quiet(
        settings.processed_dir / f"{uploaded.stem}_16k.wav")
    db.delete(lecture)
    db.commit()


@router.get("/{lecture_id}/audio")
def lecture_audio(lecture: Lecture = Depends(get_lecture)):
    """Serve the original uploaded audio for in-browser playback."""
    path = settings.storage_root / lecture.audio_path
    if not path.exists():
        raise NotFoundError("Audio file not found.")
    media = lecture.audio_mime or mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    return FileResponse(path, media_type=media,
                        filename=lecture.audio_original_name)


@router.get("/{lecture_id}/jobs", response_model=List[JobOut])
def lecture_jobs(lecture: Lecture = Depends(get_lecture),
                 db: Session = Depends(db_dep)) -> List[JobOut]:
    jobs = db.execute(
        select(Job).where(Job.lecture_id == lecture.id)
        .order_by(Job.created_at.desc())).scalars().all()
    return [JobOut.model_validate(j, from_attributes=True) for j in jobs]
