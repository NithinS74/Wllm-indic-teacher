"""
Translation quality evaluation.

Metrics against human-verified parallel pairs:

1. BLEU  — corpus-level BLEU-4 (with brevity penalty), computed from scratch
           so no external dependencies are required.
2. chrF  — character n-gram F-score (n=1..6), robust for Indic scripts.
3. TER-like score — normalized token edit distance (lower is better).

Usage:
    python evaluate_translation.py --manifest test_manifest.csv --refs references/
    python evaluate_translation.py --ref "source" --tgt "target" --hyp "output"

Manifest columns: source, reference (human translation), hypothesis
(machine output). Fields may be inline text or relative file paths.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import tokenize_words  # noqa: E402
from evaluate_wer import edit_distance  # noqa: E402


def _ngrams(tokens: Sequence[str], n: int) -> List[Tuple[str, ...]]:
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _modified_precision(ref: List[List[str]], hyp: List[str],
                        n: int) -> Tuple[int, int]:
    """Clipped n-gram counts (corpus-level)."""
    from collections import Counter
    hyp_counts = Counter(_ngrams(hyp, n))
    max_ref = Counter()
    for r in ref:
        ref_counts = Counter(_ngrams(r, n))
        for gram, count in ref_counts.items():
            max_ref[gram] = max(max_ref[gram], count)
    overlap = sum(min(count, max_ref[gram])
                  for gram, count in hyp_counts.items() if gram in max_ref)
    total = max(sum(hyp_counts.values()), 0)
    return overlap, total


def corpus_bleu(refs: List[List[str]], hyps: List[List[str]],
                max_n: int = 4) -> float:
    """Corpus BLEU with uniform weights and brevity penalty."""
    if not hyps:
        return 0.0
    overlap_sum = [0] * max_n
    total_sum = [0] * max_n
    for ref, hyp in zip(refs, hyps):
        for n in range(1, max_n + 1):
            o, t = _modified_precision([ref], hyp, n)
            overlap_sum[n - 1] += o
            total_sum[n - 1] += t
    if any(t == 0 for t in total_sum):
        # fall back to lower n if higher orders unavailable (short sentences)
        usable = [i for i in range(max_n) if total_sum[i] > 0]
        if not usable:
            return 0.0
        log_precisions = [
            math.log(overlap_sum[i] / total_sum[i]) if overlap_sum[i] > 0
            else float("-inf")
            for i in usable
        ]
        if any(p == float("-inf") for p in log_precisions):
            return 0.0
        geo_mean = math.exp(sum(log_precisions) / len(log_precisions))
    else:
        log_precisions = []
        for i in range(max_n):
            if total_sum[i] == 0:
                continue
            if overlap_sum[i] == 0:
                return 0.0
            log_precisions.append(math.log(overlap_sum[i] / total_sum[i]))
        geo_mean = math.exp(sum(log_precisions) / len(log_precisions))

    ref_len = sum(len(r) for r in refs)
    hyp_len = sum(len(h) for h in hyps)
    if hyp_len > ref_len:
        bp = 1.0
    elif hyp_len == 0:
        bp = 0.0
    else:
        bp = math.exp(1 - ref_len / hyp_len)
    return round(bp * geo_mean, 4)


def chrf(refs: List[str], hyps: List[str], max_n: int = 6) -> float:
    """Character n-gram F-score averaged over sentences."""
    scores = []
    for ref, hyp in zip(refs, hyps):
        ref_chars = list(ref.replace(" ", ""))
        hyp_chars = list(hyp.replace(" ", ""))
        if not ref_chars or not hyp_chars:
            scores.append(0.0)
            continue
        f_sum, n_sum = 0.0, 0
        for n in range(1, max_n + 1):
            ref_counts = Counter(_ngrams(ref_chars, n))
            hyp_counts = Counter(_ngrams(hyp_chars, n))
            overlap = sum(min(c, ref_counts[g])
                          for g, c in hyp_counts.items() if g in ref_counts)
            p = overlap / max(sum(hyp_counts.values()), 1)
            r = overlap / max(sum(ref_counts.values()), 1)
            if p + r > 0:
                f_sum += 2 * p * r / (p + r)
            n_sum += 1
        scores.append(f_sum / n_sum)
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def ter(refs: List[str], hyps: List[str]) -> float:
    """Normalized token edit distance (translation error rate style)."""
    total_err, total_ref = 0, 0
    for ref, hyp in zip(refs, hyps):
        ref_t, hyp_t = tokenize_words(ref), tokenize_words(hyp)
        s, d, i, _ = edit_distance(ref_t, hyp_t)
        total_err += s + d + i
        total_ref += len(ref_t)
    return round(total_err / total_ref, 4) if total_ref else 0.0


def evaluate_pairs(pairs: List[Dict[str, str]]) -> Dict[str, float]:
    refs_tok = [tokenize_words(p["reference"]) for p in pairs]
    hyps_tok = [tokenize_words(p["hypothesis"]) for p in pairs]
    refs_raw = [p["reference"] for p in pairs]
    hyps_raw = [p["hypothesis"] for p in pairs]
    return {
        "bleu": corpus_bleu(refs_tok, hyps_tok),
        "chrf": chrf(refs_raw, hyps_raw),
        "ter": ter(refs_raw, hyps_raw),
        "n_pairs": len(pairs),
    }


def _resolve(value: str, refs_dir: Path) -> str:
    if value and not Path(value).exists() and refs_dir:
        candidate = refs_dir / value
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate translation quality")
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--refs", type=Path, default=Path("references"))
    ap.add_argument("--ref", type=str, help="Source text (inline)")
    ap.add_argument("--tgt", type=str, help="Reference translation (inline)")
    ap.add_argument("--hyp", type=str, help="Hypothesis translation (inline)")
    ap.add_argument("--out", type=Path,
                    default=Path("results/translation_results.csv"))
    args = ap.parse_args()

    if args.tgt is not None and args.hyp is not None:
        result = evaluate_pairs([{
            "source": args.ref or "", "reference": args.tgt,
            "hypothesis": args.hyp,
        }])
        print(json.dumps(result, indent=2))
        return 0

    if not args.manifest or not args.manifest.exists():
        print("Provide --manifest or --ref/--tgt/--hyp.", file=sys.stderr)
        return 2

    pairs: List[Dict[str, str]] = []
    meta: List[Dict[str, str]] = []
    with args.manifest.open(newline="", encoding="utf-8") as fh:
        for idx, row in enumerate(csv.DictReader(fh), 1):
            pairs.append({
                "source": _resolve(row.get("source", ""), args.refs),
                "reference": _resolve(row.get("reference", ""), args.refs),
                "hypothesis": _resolve(row.get("hypothesis", ""), args.refs),
            })
            meta.append({"id": row.get("id", f"row-{idx}"),
                         "language": row.get("language", "")})

    if not pairs:
        print("No pairs found.", file=sys.stderr)
        return 2

    result = evaluate_pairs(pairs)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["id", "language", "bleu", "chrf", "ter"])
        writer.writeheader()
        for m in meta:
            writer.writerow({**m, "bleu": result["bleu"],
                             "chrf": result["chrf"], "ter": result["ter"]})

    print(f"Pairs: {result['n_pairs']}")
    print(f"BLEU:  {result['bleu']}")
    print(f"chrF:  {result['chrf']}")
    print(f"TER:   {result['ter']}")
    print(f"Results -> {args.out}")
    return 0


if __name__ == "__main__":
    # Counter used in chrf/_modified_precision
    from collections import Counter  # noqa: F401
    raise SystemExit(main())
