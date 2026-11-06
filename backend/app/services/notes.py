"""Structured note generation with hierarchical summarization.

Param-1 has a bounded context window, so long transcripts are never sent in
one prompt:

    FULL TRANSCRIPT -> token-based chunking -> per-chunk summaries
                    -> merged structured notes -> de-duplication -> validate

The mock provider is extractive and handles the transcript in one pass (it
does not need a context window); the hierarchical path is used for the real
LLM and is unit-tested with a stub LLM.
"""
from __future__ import annotations

import logging
import re
from typing import Callable, List, Sequence, Tuple, TypeVar

from app.ai.llm.base import LLMProvider
from app.ai.types import GenerationContext, LLMResult
from app.core.config import settings
from app.core.errors import GenerationError
from app.schemas.api import NotesContent
from app.services.validation import validate_notes

logger = logging.getLogger("lecturelens.notes")

T = TypeVar("T")


def with_retries(fn: Callable[[], T], attempts: int, label: str) -> T:
    """Bounded retries for malformed LLM output."""
    last: Exception | None = None
    for i in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except GenerationError as exc:
            last = exc
            logger.warning("%s attempt %d/%d failed: %s", label, i, attempts,
                           exc.message)
    assert last is not None
    raise last


def _estimate_tokens(text: str) -> int:
    """Approximate token count (works without loading a tokenizer).

    ~4 chars/token for English/Latin; Indic scripts average more chars per
    token in SentencePiece models, so we use 3 to stay conservative.
    """
    if not text:
        return 0
    indic = any("ऀ" <= ch <= "௿" or "ಀ" <= ch <= "೿" for ch in text[:500])
    return max(1, len(text) // (3 if indic else 4))


def chunk_segments(segment_indices: Sequence[int], segment_texts: Sequence[str],
                   max_tokens: int) -> List[List[Tuple[int, str]]]:
    """Pack consecutive segments into chunks under max_tokens."""
    chunks: List[List[Tuple[int, str]]] = []
    current: List[Tuple[int, str]] = []
    size = 0
    for idx, text in zip(segment_indices, segment_texts):
        t = _estimate_tokens(text) + 4  # segment marker overhead
        if current and size + t > max_tokens:
            chunks.append(current)
            current, size = [], 0
        current.append((idx, text))
        size += t
    if current:
        chunks.append(current)
    return chunks


def _ctx_with(ctx: GenerationContext, pairs: List[Tuple[int, str]]) -> GenerationContext:
    return GenerationContext(
        lecture_id=ctx.lecture_id,
        lecture_title=ctx.lecture_title,
        source_language=ctx.source_language,
        transcript_text="\n".join(t for _, t in pairs),
        segment_texts=[t for _, t in pairs],
        segment_indices=[i for i, _ in pairs],
    )


def _dedupe_sections(sections: List[dict]) -> List[dict]:
    """Remove duplicate headings/content lines across merged chunk notes."""
    seen_headings: set[str] = set()
    seen_lines: set[str] = set()
    out: List[dict] = []
    for s in sections:
        heading = str(s.get("heading", "")).strip().lower()
        if heading and heading in seen_headings:
            # merge content into the existing section with the same heading
            for existing in out:
                if str(existing.get("heading", "")).strip().lower() == heading:
                    for line in s.get("content", []):
                        if line not in existing.setdefault("content", []):
                            existing["content"].append(line)
                    existing.setdefault("source_segments", [])
                    for seg in s.get("source_segments", []):
                        if seg not in existing["source_segments"]:
                            existing["source_segments"].append(seg)
                    break
            continue
        seen_headings.add(heading)
        cleaned_content = []
        for line in s.get("content", []):
            key = str(line).strip().lower()
            if key in seen_lines:
                continue
            seen_lines.add(key)
            cleaned_content.append(line)
        s = dict(s)
        s["content"] = cleaned_content or s.get("content", [])
        out.append(s)
    return out


def generate_notes(llm: LLMProvider, ctx: GenerationContext,
                   max_segment_index: int) -> Tuple[NotesContent, LLMResult]:
    """Generate validated structured notes (with retries)."""
    attempts = max(1, settings.quiz_retry_attempts + 1)
    holder: dict = {}

    if llm.is_mock:
        def _run() -> NotesContent:
            res = llm.generate_notes(ctx)
            holder["res"] = res
            return validate_notes(res.payload, max_segment_index)
        notes = with_retries(_run, attempts, "mock notes")
        return notes, holder["res"]

    # ---- real model: hierarchical summarization ----
    budget = max(512, settings.param1_max_input_tokens - 400)
    chunks = chunk_segments(ctx.segment_indices, ctx.segment_texts, budget)

    if len(chunks) <= 1:
        def _single() -> NotesContent:
            res = llm.generate_notes(ctx)
            holder["res"] = res
            return validate_notes(res.payload, max_segment_index)
        notes = with_retries(_single, attempts, "notes")
        return notes, holder["res"]

    # Step 1: partial notes per chunk
    partials: List[dict] = []
    for i, chunk in enumerate(chunks, start=1):
        sub = _ctx_with(ctx, chunk)
        res = llm.generate_notes(sub)
        payload = dict(res.payload)
        payload["_chunk"] = i
        partials.append(payload)
        logger.info("Chunk %d/%d summarized (%d segments)",
                    i, len(chunks), len(chunk))

    # Step 2: merge via the LLM with de-duplication applied locally as well
    merge_ctx = _ctx_with(
        ctx,
        [(i, _render_partial(p)) for i, p in enumerate(partials, start=1)],
    )
    merge_ctx.segment_indices = list(range(1, len(partials) + 1))

    def _merge() -> NotesContent:
        res = llm.generate_notes(merge_ctx)
        payload = dict(res.payload)
        payload["sections"] = _dedupe_sections(payload.get("sections", []))
        return validate_notes(payload, max_segment_index)

    notes = with_retries(_merge, attempts, "merged notes")
    meta = LLMResult(payload=notes.model_dump(), is_mock=res.is_mock,
                     provider=res.provider, raw_text=res.raw_text,
                     detail=f"hierarchical over {len(chunks)} chunks")
    return notes, meta


def _render_partial(partial: dict) -> str:
    lines = [f"## {partial.get('title', '')}", str(partial.get("overview", ""))]
    for s in partial.get("sections", []):
        lines.append(f"### {s.get('heading', '')}")
        for c in s.get("content", []):
            lines.append(f"- {c} (segments: {s.get('source_segments', [])})")
    return "\n".join(lines)
