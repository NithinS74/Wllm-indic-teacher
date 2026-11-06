"""API request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.languages import language_keys

LanguageKey = str  # validated against supported languages


def _validate_lang(v: str) -> str:
    if v not in language_keys():
        raise ValueError(f"Unsupported language '{v}'. Supported: {language_keys()}")
    return v


# ---------------------------------------------------------------- lectures


class LectureCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    source_language: str
    target_language: Optional[str] = None
    generate_notes: bool = True
    generate_quiz: bool = True
    translate_content: bool = False

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title must not be blank")
        return v

    @field_validator("source_language")
    @classmethod
    def _src(cls, v: str) -> str:
        return _validate_lang(v)

    @field_validator("target_language")
    @classmethod
    def _tgt(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return _validate_lang(v)


class LectureSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_language: str
    target_language: Optional[str]
    duration: Optional[float]
    status: str
    generate_notes: bool
    generate_quiz: bool
    translate_content: bool
    providers: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    job_id: Optional[str] = None
    job_status: Optional[str] = None
    current_stage: Optional[str] = None
    progress: Optional[float] = None
    error_message: Optional[str] = None
    audio_original_name: Optional[str] = None


class LectureDetail(LectureSummary):
    has_transcript: bool = False
    has_notes: bool = False
    has_quiz: bool = False
    available_note_languages: List[str] = Field(default_factory=list)
    available_translation_languages: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------- jobs


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lecture_id: str
    kind: str
    status: str
    current_stage: str
    stages: Optional[List[str]] = None
    progress: float
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


# ---------------------------------------------------------------- transcript


class TranscriptSegmentOut(BaseModel):
    segment_index: int
    start_time: float
    end_time: float
    text: str
    language: str


class TranscriptOut(BaseModel):
    lecture_id: str
    language: str
    language_label: str
    is_mock: bool
    duration: Optional[float]
    segments: List[TranscriptSegmentOut]
    audio_url: Optional[str] = None


# ---------------------------------------------------------------- notes


class NoteSection(BaseModel):
    id: str
    heading: str
    content: List[str] = Field(min_length=1)
    source_segments: List[int] = Field(default_factory=list)


class KeyTerm(BaseModel):
    term: str
    definition: str
    source_segments: List[int] = Field(default_factory=list)


class NotesContent(BaseModel):
    """Validated structured notes payload."""

    title: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    sections: List[NoteSection] = Field(min_length=1)
    key_terms: List[KeyTerm] = Field(default_factory=list)
    key_takeaways: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    important_points: List[str] = Field(default_factory=list)
    uncertain: List[str] = Field(default_factory=list)

    @field_validator("sections")
    @classmethod
    def _sections_nonempty(cls, v: List[NoteSection]) -> List[NoteSection]:
        if not v:
            raise ValueError("At least one section required")
        return v


class NotesOut(BaseModel):
    lecture_id: str
    language: str
    is_mock: bool
    content: NotesContent


# ---------------------------------------------------------------- quiz


class QuizOption(BaseModel):
    id: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1)


class QuizQuestionOut(BaseModel):
    id: str
    question: str
    options: List[QuizOption]
    correct_option: Literal["A", "B", "C", "D"]
    explanation: str
    difficulty: str
    source_segments: List[int]


class QuizOut(BaseModel):
    lecture_id: str
    language: str
    is_mock: bool
    questions: List[QuizQuestionOut]  # exactly 5


class QuizAttemptIn(BaseModel):
    answers: Dict[str, str]  # question_id -> option id

    @field_validator("answers")
    @classmethod
    def _opt_ids(cls, v: Dict[str, str]) -> Dict[str, str]:
        for k, val in v.items():
            if not k or val not in ("A", "B", "C", "D"):
                raise ValueError(f"Invalid answer entry: {k}={val}")
        return v


class QuizAttemptOut(BaseModel):
    id: str
    lecture_id: str
    answers: Dict[str, str]
    score: int
    total_questions: int
    created_at: datetime


# ---------------------------------------------------------------- translation


class TranslateIn(BaseModel):
    content_types: List[Literal["transcript", "notes", "quiz"]] = Field(
        min_length=1, default_factory=lambda: ["notes", "quiz", "transcript"])
    language: str

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        return _validate_lang(v)


class TranslateOut(BaseModel):
    job_id: str
    lecture_id: str
    language: str
    content_types: List[str]


# ---------------------------------------------------------------- export


class ExportOut(BaseModel):
    format: str
    filename: str
    content_type: str
    content: str


# ---------------------------------------------------------------- settings


class ProviderStatus(BaseModel):
    name: str            # asr | llm | translation
    provider: str        # mock | indicconformer | param1 | indictrans2
    mode: Literal["mock", "real"]
    loaded: bool
    detail: str


class SettingsOut(BaseModel):
    app_name: str
    providers: List[ProviderStatus]
    languages: List[Dict[str, Any]]
    limits: Dict[str, Any]
