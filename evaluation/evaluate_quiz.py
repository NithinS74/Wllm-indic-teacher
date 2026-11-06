"""
Quiz quality evaluation.

Metrics against a verified reference quiz:

1. accuracy_score  — average normalized score of a baseline model answering
                     with a trivial strategy (first option / keyword overlap),
                     reported as a sanity floor. Real model accuracy is computed
                     from QuizAttempt rows exported by the app.
2. answer_balance  — distribution of correct options (A–D). Heavy skew
                     (e.g. >60% one letter) suggests answer-position bias.
3. option_integrity— fraction of questions with exactly 4 distinct options
                     and exactly 1 correct answer.
4. distractor_overlap — average token overlap between correct answer and
                     distractors (high overlap = easy to eliminate).

Usage:
    python evaluate_quiz.py --quiz quiz.json
    python evaluate_quiz.py --manifest test_manifest.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import tokenize_words  # noqa: E402


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(tokenize_words(a)), set(tokenize_words(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def evaluate(questions: List[Dict]) -> Dict:
    if not questions:
        raise ValueError("Quiz has no questions.")

    letter_counts: Counter = Counter()
    integrity_ok = 0
    overlap_scores: List[float] = []
    baseline_hits = 0

    for q in questions:
        options = q.get("options", [])
        # Accept both app schema ({"id": "A"}, correct_option at question
        # level) and generic schema ({"key": "A", "is_correct": true}).
        keys = [str(o.get("id") or o.get("key") or "") for o in options]
        texts = {
            str(o.get("id") or o.get("key") or ""): o.get("text", "")
            for o in options
        }
        if "correct_option" in q:
            correct = str(q.get("correct_option") or "")
        else:
            correct = next(
                (str(o.get("id") or o.get("key") or "")
                 for o in options if o.get("is_correct")), "")

        # integrity
        distinct_keys = len(set(keys))
        correct_count = (
            1 if correct in texts and "correct_option" in q
            else sum(1 for o in options if o.get("is_correct"))
        )
        if (distinct_keys == 4 and correct_count == 1 and
                correct in texts and len(texts) == 4):
            integrity_ok += 1
        if correct:
            letter_counts[correct] += 1

        # distractor overlap: mean Jaccard(correct, distractor)
        if correct in texts:
            others = [t for k, t in texts.items() if k != correct and t]
            if others:
                overlap_scores.append(
                    sum(_jaccard(texts[correct], d) for d in others) / len(others))

        # trivial baseline: always answer "A" (first option)
        if keys and keys[0] == correct:
            baseline_hits += 1

    n = len(questions)
    dist = {k: round(letter_counts.get(k, 0) / n, 4) for k in "ABCD"}
    max_share = max(dist.values())

    return {
        "n_questions": n,
        "option_integrity": round(integrity_ok / n, 4),
        "answer_balance": dist,
        "answer_skew": max_share,           # >0.60 → biased
        "distractor_overlap": round(
            sum(overlap_scores) / len(overlap_scores), 4) if overlap_scores else 0.0,
        "baseline_first_option_accuracy": round(baseline_hits / n, 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate quiz structure quality")
    ap.add_argument("--quiz", type=Path, help="Quiz JSON file")
    ap.add_argument("--manifest", type=Path,
                    help="CSV with columns: quiz_path, (optional) language")
    ap.add_argument("--out", type=Path, default=Path("results/quiz_results.csv"))
    args = ap.parse_args()

    quizzes: List[Dict] = []
    if args.manifest:
        with args.manifest.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                data = json.loads(Path(row["quiz_path"]).read_text(encoding="utf-8"))
                # accept {"questions": [...]} or bare list
                questions = data.get("questions", data) if isinstance(data, dict) else data
                quizzes.append({
                    "id": row.get("id", ""),
                    "language": row.get("language", ""),
                    "questions": questions,
                })
    elif args.quiz:
        data = json.loads(args.quiz.read_text(encoding="utf-8"))
        questions = data.get("questions", data) if isinstance(data, dict) else data
        quizzes.append({"id": "single", "language": "", "questions": questions})
    else:
        print("Provide --quiz or --manifest.", file=sys.stderr)
        return 2

    rows = []
    for quiz in quizzes:
        metrics = evaluate(quiz["questions"])
        row = {
            "id": quiz["id"], "language": quiz["language"],
            "n_questions": metrics["n_questions"],
            "option_integrity": metrics["option_integrity"],
            "answer_skew": metrics["answer_skew"],
            "answer_balance": json.dumps(metrics["answer_balance"]),
            "distractor_overlap": metrics["distractor_overlap"],
            "baseline_first_option_accuracy":
                metrics["baseline_first_option_accuracy"],
        }
        rows.append(row)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    n = len(rows)
    print(f"Quizzes evaluated: {n}")
    print(f"option_integrity: {round(sum(r['option_integrity'] for r in rows)/n, 4)}")
    print(f"answer_skew:      {round(sum(r['answer_skew'] for r in rows)/n, 4)}")
    print(f"distractor_overlap: {round(sum(r['distractor_overlap'] for r in rows)/n, 4)}")
    print(f"Results -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
