"""
Notes quality evaluation.

Metrics (all computed against a verified reference set — no fabricated scores):

1. keyword_recall — fraction of reference key terms covered by generated notes.
2. coverage        — fraction of reference sections that have a generated match
                     (title similarity >= threshold).
3. similarity      — token-level Jaccard overlap between note body and reference.

Usage:
    python evaluate_notes.py --manifest test_manifest.csv
    python evaluate_notes.py --notes notes.json --reference ref.json

JSON shapes:
    notes.json     [{"title": "...", "content": "..."}]
    reference.json [{"title": "...", "content": "...", "keywords": ["..."]}]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import tokenize_words  # noqa: E402

DEFAULT_KEYWORDS = {
    "en": [
        "lecture", "introduction", "summary", "definition", "example",
        "overview", "concept", "method", "result", "conclusion",
    ],
}


def _tokens(text: str) -> Set[str]:
    return set(tokenize_words(text))


def title_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def evaluate(generated: List[Dict], reference: List[Dict],
             threshold: float = 0.3) -> Dict[str, float]:
    """Compare generated notes structure against reference notes."""
    if not reference:
        raise ValueError("Reference notes are required for evaluation.")

    # keyword recall (union of reference keywords + fallback defaults)
    ref_keywords: Set[str] = set()
    for section in reference:
        ref_keywords |= {k.lower() for k in section.get("keywords", [])}
    if not ref_keywords:
        ref_keywords = set(DEFAULT_KEYWORDS["en"])

    gen_text = " ".join(
        f"{n.get('title', '')} {n.get('content', '')}" for n in generated
    ).lower()
    covered = {k for k in ref_keywords if k in gen_text}
    keyword_recall = round(len(covered) / len(ref_keywords), 4)

    # section coverage via title similarity
    matched = 0
    for ref_section in reference:
        best = max(
            (title_similarity(ref_section.get("title", ""),
                              gen.get("title", ""))
             for gen in generated),
            default=0.0,
        )
        if best >= threshold:
            matched += 1
    coverage = round(matched / len(reference), 4)

    # body similarity: best Jaccard per reference section
    sims = []
    for ref_section in reference:
        ref_tokens = _tokens(ref_section.get("content", ""))
        if not ref_tokens:
            continue
        best = 0.0
        for gen in generated:
            gen_tokens = _tokens(gen.get("content", ""))
            if not gen_tokens:
                continue
            best = max(best, len(ref_tokens & gen_tokens) / len(ref_tokens | gen_tokens))
        sims.append(best)
    similarity = round(sum(sims) / len(sims), 4) if sims else 0.0

    return {
        "keyword_recall": keyword_recall,
        "coverage": coverage,
        "similarity": similarity,
        "n_reference_sections": len(reference),
        "n_generated_sections": len(generated),
        "keywords_missing": sorted(ref_keywords - covered),
    }


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate generated notes quality")
    ap.add_argument("--notes", type=Path, help="Generated notes JSON")
    ap.add_argument("--reference", type=Path, help="Reference notes JSON")
    ap.add_argument("--manifest", type=Path,
                    help="CSV with columns: notes_path, reference_path")
    ap.add_argument("--threshold", type=float, default=0.3)
    ap.add_argument("--out", type=Path, default=Path("results/notes_results.csv"))
    args = ap.parse_args()

    pairs: List[Dict] = []
    if args.manifest:
        with args.manifest.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                pairs.append({
                    "id": row.get("id", ""),
                    "language": row.get("language", ""),
                    "notes": _load(Path(row["notes_path"])),
                    "reference": _load(Path(row["reference_path"])),
                })
    elif args.notes and args.reference:
        pairs.append({
            "id": "single", "language": "",
            "notes": _load(args.notes),
            "reference": _load(args.reference),
        })
    else:
        print("Provide --notes/--reference or --manifest.", file=sys.stderr)
        return 2

    rows = []
    for pair in pairs:
        metrics = evaluate(pair["notes"], pair["reference"], args.threshold)
        rows.append({"id": pair["id"], "language": pair["language"], **metrics})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["id", "language", "keyword_recall", "coverage",
                            "similarity", "n_reference_sections",
                            "n_generated_sections", "keywords_missing"])
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["keywords_missing"] = ";".join(row["keywords_missing"])
            writer.writerow(row)

    n = len(rows)
    print(f"Notes evaluated: {n}")
    for metric in ("keyword_recall", "coverage", "similarity"):
        print(f"{metric:>18}: "
              f"{round(sum(r[metric] for r in rows) / n, 4)}")
    print(f"Results -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
