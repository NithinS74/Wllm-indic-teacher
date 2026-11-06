"""AI provider tests (mock providers + interface contracts)."""
from __future__ import annotations

from pathlib import Path

from app.ai.asr.mock import MockASR
from app.ai.factory import (
    get_asr_provider,
    get_llm_provider,
    get_translation_provider,
    provider_statuses,
)
from app.ai.llm.mock import MockLLM
from app.ai.translation.mock import MockTranslation
from app.ai.types import GenerationContext
from app.services.validation import validate_notes, validate_quiz


def _ctx() -> GenerationContext:
    texts = [
        "A process is an instance of a program in execution.",
        "The scheduler decides which process runs next on the CPU.",
        "Memory management allocates RAM to each process.",
        "Deadlock happens when processes wait for each other.",
    ]
    return GenerationContext(
        lecture_id="lec-1",
        lecture_title="Operating Systems",
        source_language="en",
        transcript_text="\n".join(texts),
        segment_texts=texts,
        segment_indices=[1, 2, 3, 4],
    )


def test_mock_asr_flags_mock_and_fills_chunks(tmp_path: Path):
    asr = MockASR()
    audio = tmp_path / "x.wav"
    audio.write_bytes(b"RIFF")
    result = asr.transcribe(audio, "kn", [(0.0, 5.0), (5.0, 9.0)])
    assert result.is_mock is True
    assert result.provider == "mock"
    assert len(result.segments) == 2
    assert all(s.text for s in result.segments)
    assert all(s.language == "kn" for s in result.segments)
    assert result.segments[0].start == 0.0
    assert result.segments[1].end == 9.0


def test_mock_llm_notes_are_schema_valid():
    llm = MockLLM()
    res = llm.generate_notes(_ctx())
    assert res.is_mock is True
    notes = validate_notes(res.payload, max_segment_index=4)
    assert notes.sections
    assert notes.key_takeaways
    for s in notes.sections:
        assert all(1 <= i <= 4 for i in s.source_segments)


def test_mock_llm_quiz_is_exactly_five_valid_questions():
    llm = MockLLM()
    res = llm.generate_quiz(_ctx())
    questions = validate_quiz(res.payload, max_segment_index=4)
    assert len(questions) == 5
    texts = {q.question.lower() for q in questions}
    assert len(texts) == 5
    for q in questions:
        assert len(q.options) == 4
        assert q.correct_option in {o.id for o in q.options}
        assert q.explanation.strip()
        assert q.source_segments


def test_mock_translation_preserves_structure_and_ids():
    tr = MockTranslation()
    original = ("question-1 section-2 A B C D\n"
                "A process is an instance of a program.")
    out = tr.translate(original, "en", "kn")
    assert "question-1" in out
    assert "section-2" in out
    # standalone option ids preserved
    for token in ("A", "B", "C", "D"):
        assert token in out
    assert out != original
    # identity translation returns input unchanged
    assert tr.translate(original, "en", "en") == original


def test_factory_returns_configured_providers():
    assert isinstance(get_asr_provider(), MockASR)
    assert isinstance(get_llm_provider(), MockLLM)
    assert isinstance(get_translation_provider(), MockTranslation)
    statuses = {p.name: p for p in provider_statuses()}
    assert statuses["asr"].mode == "mock"
    assert statuses["llm"].mode == "mock"
    assert statuses["translation"].mode == "mock"


def test_mock_llm_deterministic():
    a = MockLLM().generate_quiz(_ctx()).payload
    b = MockLLM().generate_quiz(_ctx()).payload
    assert a == b
