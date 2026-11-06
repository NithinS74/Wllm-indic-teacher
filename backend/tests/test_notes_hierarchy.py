"""Hierarchical summarization tests (stub real LLM, no weights needed)."""
from __future__ import annotations

from typing import List

from app.ai.llm.base import LLMProvider
from app.ai.types import GenerationContext, LLMResult, ProviderInfo
from app.services.notes import chunk_segments, generate_notes


def _ctx(n_segments: int) -> GenerationContext:
    texts = [
        f"Segment {i} discusses an important concept with substantial "
        f"explanatory text so that token budgeting has something to work "
        f"with for chunking purposes. " * 10
        for i in range(1, n_segments + 1)
    ]
    return GenerationContext(
        lecture_id="lec-h",
        lecture_title="Long Lecture",
        source_language="en",
        transcript_text="\n".join(texts),
        segment_texts=texts,
        segment_indices=list(range(1, n_segments + 1)),
    )


def test_chunk_segments_respects_token_budget():
    ctx = _ctx(10)
    chunks = chunk_segments(ctx.segment_indices, ctx.segment_texts, max_tokens=120)
    assert len(chunks) > 1
    # all segments preserved in order
    flat = [i for c in chunks for i, _ in c]
    assert flat == list(range(1, 11))
    # each chunk stays under budget (single oversized segment excepted)
    for c in chunks:
        est = sum(len(t) // 4 + 4 for _, t in c)
        assert est <= 120 or len(c) == 1


class StubLLM(LLMProvider):
    """Fake 'real' LLM that records how many times it was called."""

    def __init__(self, fail_first: int = 0):
        self.calls: List[str] = []
        self.fail_first = fail_first

    def info(self) -> ProviderInfo:
        return ProviderInfo(name="llm", provider="stub", mode="real",
                            loaded=True, detail="test stub")

    def _payload(self, ctx: GenerationContext) -> dict:
        sections = []
        # one section per 2 segments, grounded in provided indices
        for n, i in enumerate(ctx.segment_indices[:6], start=1):
            sections.append({
                "id": f"section-{n}",
                "heading": f"Concept {i}",
                "content": [f"Key point drawn from segment {i}."],
                "source_segments": [i],
            })
        return {
            "title": ctx.lecture_title,
            "overview": "An overview derived from the transcript chunks.",
            "sections": sections,
            "key_terms": [],
            "key_takeaways": ["Takeaway one.", "Takeaway two."],
            "examples": [], "important_points": [], "uncertain": [],
        }

    def generate_notes(self, ctx: GenerationContext) -> LLMResult:
        self.calls.append(ctx.transcript_text[:40])
        if self.fail_first > 0:
            self.fail_first -= 1
            from app.core.errors import GenerationError
            raise GenerationError("stub failure for retry test")
        return LLMResult(payload=self._payload(ctx), is_mock=False,
                         provider="stub")

    def generate_quiz(self, ctx: GenerationContext) -> LLMResult:
        raise NotImplementedError


def test_hierarchical_path_uses_multiple_llm_calls():
    ctx = _ctx(12)
    stub = StubLLM()
    notes, meta = generate_notes(stub, ctx, max_segment_index=12)
    # hierarchical: several chunk calls + at least one merge call
    assert len(stub.calls) >= 2
    assert notes.title == "Long Lecture"
    assert meta.detail and "hierarchical" in meta.detail


def test_single_chunk_path_makes_one_call():
    ctx = _ctx(2)
    stub = StubLLM()
    notes, meta = generate_notes(stub, ctx, max_segment_index=2)
    assert len(stub.calls) == 1
    assert notes.sections


def test_retries_on_malformed_output():
    ctx = _ctx(4)
    stub = StubLLM(fail_first=1)
    notes, _ = generate_notes(stub, ctx, max_segment_index=4)
    assert notes.sections  # succeeded on retry
