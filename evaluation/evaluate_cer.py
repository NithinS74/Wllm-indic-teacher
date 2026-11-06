"""
Character Error Rate (CER) evaluation.

    CER = (S + D + I) / N_chars

Standard for Indic scripts where word segmentation is ambiguous.

Usage:
    python evaluate_cer.py --manifest test_manifest.csv --refs references/
    python evaluate_cer.py --ref "reference" --hyp "hypothesis"
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import tokenize_chars  # noqa: E402
from evaluate_wer import edit_distance  # noqa: E402


def cer(ref_text: str, hyp_text: str) -> Dict[str, float]:
    ref = tokenize_chars(ref_text)
    hyp = tokenize_chars(hyp_text)
    if not ref:
        return {"cer": 0.0 if not hyp else 1.0, "S": 0, "D": 0, "I": 0, "N": 0}
    s, d, i, _ = edit_distance(ref, hyp)
    n = len(ref)
    return {
        "cer": round((s + d + i) / n, 4),
        "S": s, "D": d, "I": i, "N": n,
    }


def run_manifest(manifest: Path, refs_dir: Path) -> List[Dict]:
    rows: List[Dict] = []
    with manifest.open(newline="", encoding="utf-8") as fh:
        for idx, row in enumerate(csv.DictReader(fh), start=1):
            ref_field = row.get("reference", "")
            hyp_field = row.get("hypothesis", "")
            for field_name, value in (("reference", ref_field),
                                      ("hypothesis", hyp_field)):
                if value and not Path(value).exists() and refs_dir:
                    candidate = refs_dir / value
                    if candidate.exists():
                        if field_name == "reference":
                            ref_field = candidate.read_text(encoding="utf-8")
                        else:
                            hyp_field = candidate.read_text(encoding="utf-8")
            result = cer(ref_field, hyp_field)
            result["id"] = row.get("id", f"row-{idx}")
            result["language"] = row.get("language", "")
            rows.append(result)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute CER against references")
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--refs", type=Path, default=Path("references"))
    ap.add_argument("--ref", type=str)
    ap.add_argument("--hyp", type=str)
    ap.add_argument("--out", type=Path, default=Path("results/cer_results.csv"))
    args = ap.parse_args()

    if args.ref is not None and args.hyp is not None:
        print(json.dumps(cer(args.ref, args.hyp), indent=2, ensure_ascii=False))
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
            fh, fieldnames=["id", "language", "cer", "N", "S", "D", "I"])
        writer.writeheader()
        writer.writerows(rows)

    total_n = sum(r["N"] for r in rows)
    total_err = sum(r["S"] + r["D"] + r["I"] for r in rows)
    print(f"Utterances: {len(rows)}")
    print(f"Macro CER:  {round(sum(r['cer'] for r in rows) / len(rows), 4)}")
    print(f"Micro CER:  {round(total_err / total_n, 4) if total_n else 0.0}")
    print(f"Results -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
