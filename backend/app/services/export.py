"""Export builders: Markdown study pack and plain-text transcript."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.languages import get_language
from app.models.entities import Lecture, Note, QuizQuestion, TranscriptSegment
from app.schemas.api import NotesContent


def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def transcript_text(db: Session, lecture: Lecture) -> str:
    segs = db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.lecture_id == lecture.id)
        .order_by(TranscriptSegment.segment_order)
    ).scalars().all()
    lines = [
        f"# Transcript — {lecture.title}",
        "",
        f"Source language: {get_language(lecture.source_language).label} "
        f"({lecture.source_language})",
        f"Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
    ]
    for s in segs:
        lines.append(f"[{_fmt_ts(s.start_time)} – {_fmt_ts(s.end_time)}] {s.text}")
    lines.append("")
    return "\n".join(lines)


def notes_markdown(db: Session, lecture: Lecture, language: str = "en") -> str:
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
        raise ValueError("No notes available for export.")

    content = NotesContent.model_validate(note.content)
    lang_label = get_language(language).label if _is_supported(language) else language

    out = [
        f"# {content.title}",
        "",
        f"> Lecture: **{lecture.title}**  ",
        f"> Source language: {get_language(lecture.source_language).label}  ",
        f"> Notes language: {lang_label}  ",
        f"> Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## Overview",
        "",
        content.overview,
        "",
    ]
    for section in content.sections:
        out.append(f"## {section.heading}")
        out.append("")
        for line in section.content:
            out.append(f"- {line}")
        if section.source_segments:
            segs = ", ".join(str(s) for s in section.source_segments)
            out.append(f"\n*Source segments: {segs}*")
        out.append("")

    if content.key_terms:
        out.append("## Key Concepts & Definitions")
        out.append("")
        for t in content.key_terms:
            out.append(f"- **{t.term}**: {t.definition}")
        out.append("")

    if content.examples:
        out.append("## Examples from the Lecture")
        out.append("")
        for e in content.examples:
            out.append(f"- {e}")
        out.append("")

    if content.important_points:
        out.append("## Important Points")
        out.append("")
        for p in content.important_points:
            out.append(f"- {p}")
        out.append("")

    if content.key_takeaways:
        out.append("## Key Takeaways")
        out.append("")
        for k in content.key_takeaways:
            out.append(f"- {k}")
        out.append("")

    if content.uncertain:
        out.append("## Uncertain / Needs Review")
        out.append("")
        for u in content.uncertain:
            out.append(f"- {u}")
        out.append("")

    # Quiz appendix
    qs = db.execute(
        select(QuizQuestion).where(QuizQuestion.lecture_id == lecture.id)
        .order_by(QuizQuestion.sort_order)
    ).scalars().all()
    if qs:
        out.append("## Quiz (5 MCQs)")
        out.append("")
        for q in qs:
            out.append(f"### {q.question}")
            out.append("")
            for opt in q.options:
                mark = "✅" if opt["id"] == q.correct_option else "  "
                out.append(f"{mark} **{opt['id']}.** {opt['text']}")
            out.append("")
            out.append(f"*Answer: {q.correct_option} — {q.explanation}*")
            out.append("")

    return "\n".join(out)


def _is_supported(lang: str) -> bool:
    from app.core.languages import language_keys
    return lang in language_keys()


def study_pack_markdown(db: Session, lecture: Lecture,
                        notes_language: Optional[str] = None) -> str:
    """Combined export: transcript + notes + quiz."""
    parts = [notes_markdown(db, lecture, notes_language or "en"), "",
             "---", "", transcript_text(db, lecture)]
    return "\n".join(parts)
