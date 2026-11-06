"""Mock LLM provider — extractive, schema-valid notes and quiz.

Produces notes and exactly 5 MCQs *grounded in the provided transcript*
(heuristic extraction, no invented facts) so the full pipeline can be
demonstrated and tested without multi-GB weights. Always flagged is_mock=True.
"""
from __future__ import annotations

import logging
import random
import re
from typing import Dict, List, Tuple

from app.ai.llm.base import LLMProvider
from app.ai.types import GenerationContext, LLMResult, ProviderInfo

logger = logging.getLogger("lecturelens.llm.mock")

_SENT_SPLIT = re.compile(r"(?<=[.!?।!?])\s+|\n+")


def _sentences(text: str) -> List[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p and p.strip()]
    return parts


class MockLLM(LLMProvider):
    name = "llm"

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="llm", provider="mock", mode="mock", loaded=True,
            detail="Extractive demo notes/quiz (no LLM inference performed).",
        )

    # ----------------------------------------------------------------- notes
    def generate_notes(self, ctx: GenerationContext) -> LLMResult:
        rng = random.Random(f"notes:{ctx.lecture_id}")
        segs = list(zip(ctx.segment_indices, ctx.segment_texts))
        if not segs:
            segs = [(1, ctx.transcript_text or "No transcript available.")]

        # Sectioning: split into sentence-level units (carrying their segment
        # index), then pack them into contiguous groups of ~4 units each so a
        # single long segment still yields multiple sections.
        units: List[Tuple[int, str]] = []
        for idx, text in segs:
            ss = _sentences(text)
            if len(ss) >= 2:
                units.extend((idx, s) for s in ss)
            else:
                units.append((idx, text))
        if not units:
            units = [(1, ctx.transcript_text or "No transcript available.")]
        per = 4
        groups: List[List[Tuple[int, str]]] = [
            units[i:i + per] for i in range(0, len(units), per)
        ]
        groups = groups[:6]

        sections = []
        key_terms: List[Dict] = []
        examples: List[str] = []
        important: List[str] = []
        uncertain: List[str] = []

        for gi, group in enumerate(groups, start=1):
            if not group:
                continue
            indices = sorted({i for i, _ in group})
            body = " ".join(t for _, t in group)
            sents = [t for _, t in group]
            heading_src = sents[0] if sents else body
            heading = _shorten(heading_src, 70)
            content = sents[:6] if sents else [body]
            sections.append({
                "id": f"section-{gi}",
                "heading": heading,
                "content": content,
                "source_segments": indices,
            })
            for s in sents:
                # extractive "definition" pattern: X is/was/are Y
                m = re.match(r"^(.{3,60}?)\s+(?:is|are|was|were)\s+(.{10,})$", s)
                if m and len(key_terms) < 8:
                    key_terms.append({
                        "term": _shorten(m.group(1), 40),
                        "definition": s,
                        "source_segments": indices[:2],
                    })
                if re.search(r"\bexample|for example|instance of|let us now|look at\b",
                             s, re.I) and len(examples) < 5:
                    examples.append(s)
                if len(important) < 6:
                    important.append(s)
                if re.search(r"\bunclear|not sure|approximately\b", s, re.I):
                    uncertain.append(s)

        takeaways = []
        for sec in sections[:5]:
            if sec["content"]:
                takeaways.append(_shorten(sec["content"][0], 160))

        title = ctx.lecture_title or "Lecture Notes"
        overview_src = " ".join(t for _, t in segs[:2])
        overview = _shorten(_sentences(overview_src)[0] if _sentences(overview_src)
                            else overview_src, 320)

        payload = {
            "title": title,
            "overview": overview or "No overview available.",
            "sections": sections or [{
                "id": "section-1",
                "heading": title,
                "content": [ctx.transcript_text[:500] or "Empty transcript."],
                "source_segments": [i for i, _ in segs],
            }],
            "key_terms": key_terms,
            "key_takeaways": takeaways,
            "examples": examples,
            "important_points": important,
            "uncertain": uncertain,
        }
        return LLMResult(payload=payload, is_mock=True, provider="mock",
                         detail="Extractive mock notes.")

    # ------------------------------------------------------------------ quiz
    def generate_quiz(self, ctx: GenerationContext) -> LLMResult:
        rng = random.Random(f"quiz:{ctx.lecture_id}")
        segs = [(i, t) for i, t in zip(ctx.segment_indices, ctx.segment_texts) if t.strip()]
        sentences: List[Tuple[int, str]] = []
        for idx, text in segs:
            for s in _sentences(text):
                if len(s) >= 25:
                    sentences.append((idx, s))
        if not sentences:
            sentences = [(1, "The lecture content was too short to form questions.")]

        # Build definition-style QA pairs when possible
        qa_pairs: List[Dict] = []
        for idx, s in sentences:
            m = re.match(r"^(.{3,60}?)\s+(?:is|are|was|were)\s+(.{15,})$", s)
            if m:
                qa_pairs.append({
                    "question": f"What does the lecture say about {m.group(1).strip()}?",
                    "answer": s,
                    "source": idx,
                })

        pool = [s for _, s in sentences]
        questions: List[Dict] = []
        used: set = set()

        # 1) definition questions (English "X is Y" patterns)
        for qa in qa_pairs:
            if len(questions) >= 5:
                break
            if qa["question"] in used:
                continue
            used.add(qa["question"])
            distractors = _distractors(qa["answer"], pool, rng, count=3)
            if len(distractors) < 3:
                continue
            options = _build_options(qa["answer"], distractors, rng)
            questions.append({
                "id": f"question-{len(questions) + 1}",
                "question": qa["question"],
                "options": options,
                "correct_option": _correct_id(options, qa["answer"]),
                "explanation": f"According to the lecture: {qa['answer']}",
                "difficulty": "easy",
                "source_segments": [qa["source"]],
            })

        # 2) topic-focused coverage questions
        for pass_no in range(len(sentences)):
            if len(questions) >= 5:
                break
            idx, s = sentences[pass_no % len(sentences)]
            topic = _topic(s)
            qtext = (f"Which statement from the lecture matches this focus: "
                     f"“{topic}”?") if topic else (
                    f"Which statement appears in the lecture? "
                    f"(point {pass_no + 1})")
            if qtext in used:
                continue
            distractors = _distractors(s, pool, rng, count=3)
            if len(distractors) < 3:
                continue
            used.add(qtext)
            options = _build_options(s, distractors, rng)
            questions.append({
                "id": f"question-{len(questions) + 1}",
                "question": qtext,
                "options": options,
                "correct_option": _correct_id(options, s),
                "explanation": f"The lecture states: {s}",
                "difficulty": "medium" if len(questions) % 2 else "easy",
                "source_segments": [idx],
            })

        # 3) pad with generic-but-grounded fillers if still short
        filler_sources = [s for _, s in sentences]
        while len(questions) < 5 and filler_sources:
            s = filler_sources[len(questions) % len(filler_sources)]
            idx = sentences[len(questions) % len(sentences)][0]
            qtext = f"Identify the correct statement from the lecture (part {len(questions) + 1})."
            if qtext in used and len(used) > 20:
                break
            used.add(qtext)
            distractors = _distractors(s, pool, rng, count=3)
            while len(distractors) < 3:
                distractors.append(f"None of these statements appear in the lecture ({len(distractors) + 1}).")
            options = _build_options(s, distractors[:3], rng)
            questions.append({
                "id": f"question-{len(questions) + 1}",
                "question": qtext,
                "options": options,
                "correct_option": _correct_id(options, s),
                "explanation": f"The lecture mentions: {s}",
                "difficulty": "medium",
                "source_segments": [idx],
            })

        # enforce exactly 5
        questions = questions[:5]
        while len(questions) < 5:
            n = len(questions) + 1
            base = pool[(n - 1) % len(pool)]
            idx = sentences[(n - 1) % len(sentences)][0]
            options = _build_options(base, [
                f"This statement does not appear in the lecture (variant A).",
                f"This statement does not appear in the lecture (variant B).",
                f"This statement does not appear in the lecture (variant C).",
            ], rng)
            questions.append({
                "id": f"question-{n}",
                "question": f"Which statement is supported by the lecture? (Q{n})",
                "options": options,
                "correct_option": _correct_id(options, base),
                "explanation": f"The lecture states: {base}",
                "difficulty": "easy",
                "source_segments": [idx],
            })

        return LLMResult(payload={"questions": questions}, is_mock=True,
                         provider="mock", detail="Extractive mock quiz.")


def _shorten(text: str, n: int) -> str:
    text = " ".join(text.split())
    if n <= 0:
        return text
    if len(text) <= n:
        return text
    return text[: n - 1].rsplit(" ", 1)[0] + "…"


_WORD = re.compile(r"[0-9A-Za-zऀ-ॿಀ-೿]+")


def _topic(sentence: str) -> str:
    """Pick a short distinctive focus phrase from a sentence (any script)."""
    words = _WORD.findall(sentence)
    content = [w for w in words if len(w) >= 4] or words
    # prefer rarer-looking long tokens
    content = sorted(set(content), key=len, reverse=True)
    if not content:
        return ""
    return " ".join(content[:3])


def _distractors(correct: str, pool: List[str], rng: random.Random,
                 count: int = 3) -> List[str]:
    candidates = [s for s in pool if s != correct and len(s) >= 15]
    rng.shuffle(candidates)
    # Prefer semantically different sentences: differ in first 40 chars
    picked: List[str] = []
    for s in candidates:
        if s[:40] == correct[:40]:
            continue
        if s in picked:
            continue
        picked.append(s)
        if len(picked) >= count:
            break
    # Pad with clearly-wrong constructed distractors if the transcript is tiny
    n = 1
    while len(picked) < count:
        picked.append(f"None of the other options is discussed in this lecture (distractor {n}).")
        n += 1
    return picked


def _build_options(correct: str, distractors: List[str],
                   rng: random.Random) -> List[Dict[str, str]]:
    texts = [correct] + distractors[:3]
    rng.shuffle(texts)
    ids = ["A", "B", "C", "D"]
    return [{"id": i, "text": _shorten(t, 240)} for i, t in zip(ids, texts)]


def _correct_id(options: List[Dict[str, str]], correct_text: str) -> str:
    ct = _shorten(correct_text, 240)
    for opt in options:
        if opt["text"] == ct:
            return opt["id"]
    # fallback: first option (should not happen)
    return options[0]["id"]
