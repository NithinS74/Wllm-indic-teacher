"""
Word Error Rate (WER) evaluation.

    WER = (S + D + I) / N

where S = substitutions, D = deletions, I = insertions, N = reference words.

Usage:
    python evaluate_wer.py --manifest test_manifest.csv --refs references/
    python evaluate_wer.py --ref "reference text" --hyp "hypothesis text"

Input formats:
  * per-row CSV/JSON manifest (see README.md) with `reference` and
    `hypothesis` columns or file paths,
  * direct --ref/--hyp strings for quick checks.

Reference transcripts must be manually verified. Results are written to
results/wer_results.csv — this script never fabricates scores: it only
computes them from the references you supply.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import tokenize_words  # noqa: E402


def edit_distance(ref: List[str], hyp: List[str]) -> Tuple[int, int, int, int]:
    """Return (S, D, I, hits) via Levenshtein alignment backtrace."""
    n, m = len(ref), len(hyp)
    # dp[i][j] = (cost, S, D, I, hits) — store cost matrix then backtrace ops
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
    for j in range(1, m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j - 1] + cost,      # substitution / match
                dp[i - 1][j] + 1,             # deletion
                dp[i][j - 1] + 1,             # insertion
            )
    # backtrace for operation counts
    i, j = n, m
    s = d = ins = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            if dp[i][j] == dp[i - 1][j - 1] + cost:
                if cost == 1:
                    s += 1
                i, j = i - 1, j - 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            d += 1
            i -= 1
            continue
        if j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            ins += 1
            j -= 1
            continue
        # fallback (shouldn't happen)
        i, j = max(i - 1, 0), max(j - 1, 0)
    return s, d, ins, n - s - d


def wer(ref_text: str, hyp_text: str) -> Dict[str, float]:
    ref = tokenize_words(ref_text)
    hyp = tokenize_words(hyp_text)
    if not ref:
        return {"wer": 0.0 if not hyp else 1.0, "hits": 0, "S": 0, "D": 0,
                "I": 0, "N": 0}
    s, d, i, _ = edit_distance(ref, hyp)
    n = len(ref)
    return {
        "wer": round((s + d + i) / n, 4),
        "hits": n - s - d, "S": s, "D": d, "I": i, "N": n,
    }


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_manifest(manifest: Path, refs_dir: Path) -> List[Dict]:
    rows: List[Dict] = []
    with manifest.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ref_field = row.get("reference", "")
            hyp_field = row.get("hypothesis", "")
            # allow file-relative references
            if ref_field and not Path(ref_field).exists() and refs_dir:
                candidate = refs_dir / ref_field
                if candidate.exists():
                    ref_field = _load_text(candidate)
            if hyp_field and not Path(hyp_field).exists() and refs_dir:
                candidate = refs_dir / hyp_field
                if candidate.exists():
                    hyp_field = _load_text(candidate)
            result = wer(ref_field, hyp_field)
            result["id"] = row.get("id", f"row-{len(rows) + 1}")
            result["language"] = row.get("language", "")
            rows.append(result)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute WER against references")
    ap.add_argument("--manifest", type=Path, help="CSV manifest with references")
    ap.add_argument("--refs", type=Path, default=Path("references"),
                    help="Directory containing reference text files")
    ap.add_argument("--ref", type=str, help="Inline reference text")
    ap.add_argument("--hyp", type=str, help="Inline hypothesis text")
    ap.add_argument("--out", type=Path, default=Path("results/wer_results.csv"))
    args = ap.parse_args()

    if args.ref is not None and args.hyp is not None:
        r = wer(args.ref, args.hyp)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0

    if not args.manifest or not args.manifest.exists():
        print("Provide --manifest CSV or --ref/--hyp pair.", file=sys.stderr)
        return 2

    rows = run_manifest(args.manifest, args.refs)
    if not rows:
        print("Manifest produced no rows.", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["id", "language", "wer", "N", "S", "D", "I", "hits"])
        writer.writeheader()
        writer.writerows(rows)

    total_n = sum(r["N"] for r in rows)
    total_err = sum(r["S"] + r["D"] + r["I"] for r in rows)
    micro = round(total_err / total_n, 4) if total_n else 0.0
    macro = round(sum(r["wer"] for r in rows) / len(rows), 4)
    print(f"Utterances: {len(rows)}")
    print(f"Macro WER:  {macro}")
    print(f"Micro WER:  {micro}")
    print(f"Results -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
