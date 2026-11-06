"""Structured output validation tests."""
from __future__ import annotations

import pytest

from app.core.errors import GenerationError
from app.services.validation import validate_notes, validate_quiz


def _notes_payload() -> dict:
    return {
        "title": "OS Lecture",
        "overview": "Overview of the operating systems lecture.",
        "sections": [
            {"id": "section-1", "heading": "Processes",
             "content": ["A process is a running program."],
             "source_segments": [1, 2]},
        ],
        "key_terms": [{"term": "Process", "definition": "A running instance.",
                       "source_segments": [1]}],
        "key_takeaways": ["Processes are scheduled by the OS."],
        "examples": [], "important_points": [], "uncertain": [],
    }


def _quiz_payload() -> dict:
    def q(n: int, correct: str = "A") -> dict:
        return {
            "id": f"question-{n}",
            "question": f"Question number {n} about the lecture?",
            "options": [
                {"id": "A", "text": f"Correct option {n}"},
                {"id": "B", "text": f"Wrong option {n}"},
                {"id": "C", "text": f"Another wrong {n}"},
                {"id": "D", "text": f"Third wrong {n}"},
            ],
            "correct_option": correct,
            "explanation": f"Because the lecture says so ({n}).",
            "difficulty": "easy",
            "source_segments": [1],
        }
    return {"questions": [q(i) for i in range(1, 6)]}


def test_valid_notes_pass():
    notes = validate_notes(_notes_payload(), max_segment_index=5)
    assert notes.title == "OS Lecture"
    assert notes.sections[0].source_segments == [1, 2]


def test_notes_missing_sections_rejected():
    payload = _notes_payload()
    payload["sections"] = []
    with pytest.raises(GenerationError):
        validate_notes(payload, 5)


def test_notes_invalid_segment_reference_rejected():
    payload = _notes_payload()
    payload["sections"][0]["source_segments"] = [99]
    with pytest.raises(GenerationError):
        validate_notes(payload, 5)


def test_quiz_exactly_five():
    qs = validate_quiz(_quiz_payload(), 3)
    assert len(qs) == 5


def test_quiz_wrong_count_rejected():
    payload = _quiz_payload()
    payload["questions"] = payload["questions"][:3]
    with pytest.raises(GenerationError, match="exactly 5"):
        validate_quiz(payload, 3)


def test_quiz_duplicate_options_rejected():
    payload = _quiz_payload()
    payload["questions"][0]["options"][1]["text"] = "Correct option 1"
    with pytest.raises(GenerationError, match="duplicate"):
        validate_quiz(payload, 3)


def test_quiz_invalid_correct_option_rejected():
    payload = _quiz_payload()
    payload["questions"][0]["correct_option"] = "Z"
    with pytest.raises(GenerationError, match="correct_option"):
        validate_quiz(payload, 3)


def test_quiz_duplicate_questions_rejected():
    payload = _quiz_payload()
    payload["questions"][1]["question"] = payload["questions"][0]["question"]
    with pytest.raises(GenerationError, match="Duplicate"):
        validate_quiz(payload, 3)


def test_quiz_empty_explanation_rejected():
    payload = _quiz_payload()
    payload["questions"][2]["explanation"] = "   "
    with pytest.raises(GenerationError, match="explanation"):
        validate_quiz(payload, 3)


def test_quiz_out_of_range_segments_rejected():
    payload = _quiz_payload()
    payload["questions"][0]["source_segments"] = [42]
    with pytest.raises(GenerationError, match="out of range"):
        validate_quiz(payload, 3)


def test_quiz_missing_source_segments_rejected():
    payload = _quiz_payload()
    payload["questions"][0]["source_segments"] = []
    with pytest.raises(GenerationError, match="source segment"):
        validate_quiz(payload, 3)


def test_option_ids_normalized():
    payload = _quiz_payload()
    for i, opt in enumerate(payload["questions"][0]["options"]):
        opt["id"] = "X"  # ids come back wrong — must be normalized to A-D
    qs = validate_quiz(payload, 3)
    assert [o.id for o in qs[0].options] == ["A", "B", "C", "D"]
