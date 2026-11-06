# LectureLens — Implementation Plan

## Phase 1 — Inspection & planning ✅
- Repo was empty; environment probed (Python 3.12, Node 22, FFmpeg 6.1 installed,
  PostgreSQL 16 + Redis 7 started locally, no Docker daemon, no GPU).
- Official model docs verified → `docs/model-selection.md`.
- Architecture fixed → `docs/architecture.md`.

## Phase 2 — Scaffolding ✅
- `backend/` FastAPI app, `frontend/` Vite React TS, `docker-compose.yml`, `.env.example`.
- Health endpoints (`/api/v1/health`, `/health`).

## Phase 3 — Backend MVP ✅
- Audio upload + validation (extension + ffprobe) + safe storage.
- `Lecture`, `Job` models + Alembic migration.
- Redis/RQ queue + worker process + job status API.
- Mock ASR provider to exercise the full pipeline.

## Phase 4 — AI pipeline ✅
- Provider interfaces: `backend/app/ai/{asr,llm,translation}/base.py`.
- Real providers: `indicconformer.py` (NeMo lazy load), `param1.py`
  (HF transformers lazy load, chat template), `indictrans2.py`
  (direction-aware HF checkpoints, chunked).
- FFmpeg preprocessing + energy-VAD segmentation with overlap & offset mapping.
- Hierarchical summarization (token-based chunking → chunk summaries → merge).
- Quiz: exactly 5 MCQs, strict validation, bounded retries.
- On-demand output translation with cache table.
- Persistence of transcript/notes/quiz/attempts/translations.

## Phase 5 — Frontend ✅
- App shell: sidebar nav (Dashboard, New Lecture, My Lectures, Settings, About).
- Pages: Dashboard, New Lecture (drag-drop upload), Processing (real stages),
  Lecture Workspace (Transcript / Notes / Quiz tabs), My Lectures, Settings.
- TanStack Query polling for jobs; toast + confirm dialogs; responsive.

## Phase 6 — Testing ✅
- `backend/tests/`: validation, audio, segmentation, quiz pipeline, API flow,
  mock providers, translation cache, export.
- Frontend: `tsc --noEmit` + production build as the gate.
- Evaluation harness with unit-testable WER/CER/BLEU/chrF.

## Phase 7 — Docs & delivery ✅
- README with exact run commands (local + Docker), model configuration,
  evaluation methodology, limitations.

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| No GPU / multi-GB weights in demo env | Explicit mock providers, visible in UI |
| Param-1 not multilingual | Translate-to-English canonical flow |
| IndicConformer repo is README-only (code in NeMo) | Lazy NeMo import inside provider, clear error if missing |
| Long transcripts exceed LLM context | Hierarchical chunked summarization |
| Malformed LLM JSON | Pydantic validation + bounded retries + mock fallback of schema repair |
| Docker unavailable in dev env | Native services for dev; Compose files provided & documented |

## Assumptions (documented, per instructions)
1. No authentication for MVP (single-user student demo).
2. PDF export is client-side via browser print of the printable notes view;
   backend exports Markdown + plain-text transcript.
3. English is the canonical generation language for Param-1.
4. `progress` = completed stages / total stages for that job.
5. Python 3.12 used (3.11-compatible code; ML extras pin ranges accordingly).
