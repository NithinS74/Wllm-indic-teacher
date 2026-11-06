# Evaluation Suite

Scripts for measuring LectureLens quality. Every metric is computed strictly
from human-verified references you supply — nothing here fabricates scores.

## Files

| File | Purpose |
|------|---------|
| `common.py` | Shared normalization (Indic + Latin scripts) |
| `evaluate_wer.py` | Word Error Rate for transcripts |
| `evaluate_cer.py` | Character Error Rate (better for Indic scripts) |
| `evaluate_notes.py` | Keyword recall / section coverage / similarity |
| `evaluate_quiz.py` | Option integrity, answer balance, distractor overlap |
| `evaluate_translation.py` | BLEU, chrF, TER for translation pairs |
| `test_manifest.csv` | 50 example cases across en/hi/kn/ta/te/ml |
| `references/` | Human-verified reference texts (add `.txt` files) |
| `results/` | Script outputs + `failure_analysis.md` template |

## Manifest format

`test_manifest.csv` columns (extra columns are ignored by each script):

```
id,language,source,reference,hypothesis,reference_path,notes_path,quiz_path
```

- **WER/CER/translation**: use `source`, `reference` (human transcript /
  translation), `hypothesis` (system output). Fields may be inline text or
  relative file paths resolved under `references/`.
- **Notes**: `notes_path` → generated notes JSON, `reference_path` → verified
  notes JSON (`[{"title","content","keywords"}]`).
- **Quiz**: `quiz_path` → quiz JSON (`{"questions":[...]}` or bare list).

## Usage

```bash
cd evaluation

# Transcript metrics (point at system output as --hyp or manifest hypothesis)
python evaluate_wer.py --manifest test_manifest.csv --refs references/
python evaluate_cer.py --manifest test_manifest.csv --refs references/

# Quick single-pair check
python evaluate_wer.py --ref "verified transcript" --hyp "asr output"

# Notes (requires notes_path/reference_path in manifest)
python evaluate_notes.py --manifest test_manifest.csv

# Quiz structure
python evaluate_quiz.py --manifest test_manifest.csv

# Translation (requires reference/hypothesis pairs)
python evaluate_translation.py --manifest test_manifest.csv --refs references/
```

Results land in `results/*.csv`. Summarize recurring problems in
`results/failure_analysis.md`.

## Populating references

1. Export a lecture's transcript/notes/quiz via the app UI or
   `GET /api/v1/lectures/{id}/export?format=markdown`.
2. Manually verify/correct it (native speaker review for Indic languages).
3. Save as `references/{lang}_{nnn}.txt` (or `.json` for notes/quiz) and add
   a manifest row pointing at the file.
4. Re-run the scripts; record metrics and failures.

Target sample size: 30–50 cases, ≥5 per supported language.
