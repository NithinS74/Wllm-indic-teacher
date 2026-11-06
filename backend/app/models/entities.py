"""SQLAlchemy models."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PREPROCESSING = "PREPROCESSING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING_INPUT = "TRANSLATING_INPUT"
    GENERATING_NOTES = "GENERATING_NOTES"
    GENERATING_QUIZ = "GENERATING_QUIZ"
    TRANSLATING_OUTPUT = "TRANSLATING_OUTPUT"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LectureStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobKind(str, enum.Enum):
    PROCESSING = "PROCESSING"       # full pipeline
    TRANSLATION = "TRANSLATION"     # on-demand content translation


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    audio_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    audio_original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    audio_mime: Mapped[Optional[str]] = mapped_column(String(120))
    source_language: Mapped[str] = mapped_column(String(16), nullable=False)
    target_language: Mapped[Optional[str]] = mapped_column(String(16))
    duration: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[LectureStatus] = mapped_column(
        Enum(LectureStatus, name="lecture_status"),
        default=LectureStatus.QUEUED, nullable=False, index=True,
    )
    generate_notes: Mapped[bool] = mapped_column(default=True)
    generate_quiz: Mapped[bool] = mapped_column(default=True)
    translate_content: Mapped[bool] = mapped_column(default=False)
    # Providers used for this lecture (mock/real) — surfaced to the UI.
    providers: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    jobs: Mapped[List["Job"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    segments: Mapped[List["TranscriptSegment"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan",
        order_by="TranscriptSegment.segment_order")
    notes: Mapped[List["Note"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    questions: Mapped[List["QuizQuestion"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan",
        order_by="QuizQuestion.sort_order")
    attempts: Mapped[List["QuizAttempt"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan")
    translations: Mapped[List["ContentTranslation"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_lectures_created_at", created_at.desc()),)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lectures.id", ondelete="CASCADE"),
        nullable=False, index=True)
    kind: Mapped[JobKind] = mapped_column(
        Enum(JobKind, name="job_kind"), default=JobKind.PROCESSING, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"),
        default=JobStatus.QUEUED, nullable=False, index=True)
    current_stage: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.QUEUED, nullable=False)
    stages: Mapped[Optional[List[Any]]] = mapped_column(JSON)   # ordered stage list
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    lecture: Mapped["Lecture"] = relationship(back_populates="jobs")

    __table_args__ = (Index("ix_jobs_lecture_created", lecture_id, created_at.desc()),)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lectures.id", ondelete="CASCADE"),
        nullable=False, index=True)
    # 1-based index used by notes/quiz source_segments references
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    segment_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_mock: Mapped[bool] = mapped_column(default=False)

    lecture: Mapped["Lecture"] = relationship(back_populates="segments")

    __table_args__ = (
        UniqueConstraint("lecture_id", "segment_index", name="uq_segment_index"),
        Index("ix_segments_lecture_order", lecture_id, segment_order),
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lectures.id", ondelete="CASCADE"),
        nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_mock: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    lecture: Mapped["Lecture"] = relationship(back_populates="notes")

    __table_args__ = (UniqueConstraint("lecture_id", "language", name="uq_note_lang"),)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lectures.id", ondelete="CASCADE"),
        nullable=False, index=True)
    question_key: Mapped[str] = mapped_column(String(32), nullable=False)  # question-1..5
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    correct_option: Mapped[str] = mapped_column(String(4), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")
    source_segments: Mapped[List[int]] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    is_mock: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    lecture: Mapped["Lecture"] = relationship(back_populates="questions")

    __table_args__ = (
        UniqueConstraint("lecture_id", "question_key", name="uq_quiz_qkey"),
        Index("ix_quiz_lecture_order", lecture_id, sort_order),
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lectures.id", ondelete="CASCADE"),
        nullable=False, index=True)
    answers: Mapped[Dict[str, str]] = mapped_column(JSON, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    lecture: Mapped["Lecture"] = relationship(back_populates="attempts")


class ContentTranslation(Base):
    """Cached translations of generated/original content, keyed by language."""

    __tablename__ = "content_translations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lectures.id", ondelete="CASCADE"),
        nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(24), nullable=False)  # transcript|notes|quiz
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_mock: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    lecture: Mapped["Lecture"] = relationship(back_populates="translations")

    __table_args__ = (
        UniqueConstraint("lecture_id", "content_type", "language",
                         name="uq_translation_cache"),
    )
