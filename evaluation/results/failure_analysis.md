# Failure Analysis Template

Fill one row per failed or degraded case after running the evaluation suite.
Keep this file in `results/failure_analysis.md`.

## Summary

| Date | Model / Config | Cases run | Failures | WER (micro) | CER (micro) | Notes |
|------|----------------|-----------|----------|-------------|-------------|-------|
| YYYY-MM-DD | indicconformer-asr-base / param-1-2.9b | | | | | |

## Failure Categories

| ID | Category | Description |
|----|----------|-------------|
| F1 | ASR misrecognition | Wrong word/phrase decoded by ASR |
| F2 | Segmentation error | Sentence boundary split/merge error |
| F3 | Code-switching | Mixed-language span handled poorly |
| F4 | Numbers/units | Numerals, dates, units misread |
| F5 | Notes hallucination | Note content not grounded in transcript |
| F6 | Notes omission | Key reference concept missing |
| F7 | Quiz invalid | Malformed question, >1 correct, missing options |
| F8 | Quiz trivial | Question answerable without the lecture |
| F9 | Translation drift | Meaning altered or entities mistranslated |
| F10 | Translation structure loss | IDs/ordering A–D or question ids corrupted |
| F11 | Long-form truncation | Input exceeded context; content cut off |
| F12 | Provider failure | Timeout, OOM, model load error |

## Per-Case Log

| Case ID | Language | Category | Severity (1–5) | Transcript excerpt | Expected | Actual | Root cause | Mitigation |
|---------|----------|----------|----------------|--------------------|----------|--------|------------|------------|
| | | | | | | | | |

## Action Items

- [ ]
- [ ]
