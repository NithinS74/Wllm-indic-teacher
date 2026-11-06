# LectureLens — Architecture

## 1. High-level overview

LectureLens is a three-tier application:

```
React SPA (Vite + TS + Tailwind)
        |  REST /api/v1 (JSON, polling job status)
FastAPI (uvicorn)
        |                 \
   PostgreSQL            Redis ── RQ job queue
   (lectures, jobs,         \
    transcript, notes,       RQ worker process
    quiz, attempts,          |
    translation cache)       audio preprocess (FFmpeg)
                             -> ASR (IndicConformer / mock)
                             -> input translation (IndicTrans2 / mock, when needed)
                             -> LLM notes + 5 MCQs (Param-1 / mock)
                             -> output translation (IndicTrans2 / mock, on demand)
                             -> validation -> persistence
```

Long-running inference never executes inside the HTTP request lifecycle.
`POST /api/v1/lectures` validates + stores the upload, creates a `Lecture` and a
`Job` row, enqueues an RQ task, and returns immediately. The frontend polls
`GET /api/v1/jobs/{job_id}` (the route shape is compatible with a later SSE upgrade).

## 2. Directory layout

```
lecturelens/
├── frontend/          React + TypeScript + Vite + Tailwind + shadcn-style UI
├── backend/           FastAPI app, AI providers, RQ worker, tests, Alembic
├── evaluation/        WER/CER/notes/quiz/translation harness + dataset manifest
├── infrastructure/    Nginx config (optional), helper scripts
├── docs/              architecture, plan, model selection
├── docker-compose.yml postgres + redis + api + worker + frontend
├── .env.example
└── README.md
```

## 3. Backend module map

```
backend/app/
├── main.py                FastAPI app factory, CORS, routers, health
├── core/
│   ├── config.py          pydantic-settings (env-driven, no secrets in code)
│   ├── errors.py          domain exceptions -> HTTP error handlers
│   └── logging.py
├── db/
│   ├── base.py            SQLAlchemy declarative base
│   └── session.py         engine + SessionLocal + get_db dependency
├── models/                Lecture, Job, TranscriptSegment, Note,
│                          QuizQuestion, QuizAttempt, ContentTranslation
├── schemas/               Pydantic request/response models (API contract)
├── api/routes/            health, lectures, jobs, transcript, notes, quiz,
│                          translate, export, settings
├── services/
│   ├── storage.py         safe server-side filenames, path-traversal guard
│   ├── audio.py           FFmpeg probe/normalize/validate
│   ├── segmentation.py    energy-VAD speech-aware chunking with overlap
│   ├── pipeline.py        stage orchestration (called by worker only)
│   ├── notes.py           hierarchical summarization -> structured notes
│   ├── quiz.py            5-MCQ generation + strict validation + retries
│   ├── validation.py      Pydantic schemas for notes/quiz JSON
│   ├── translation.py     on-demand content translation + caching
│   └── export.py          markdown / transcript text builders
├── ai/
│   ├── config.py          provider selection from env (mock vs real, device)
│   ├── asr/               base.py, indicconformer.py, mock.py
│   ├── llm/               base.py, param1.py, mock.py
│   └── translation/       base.py, indictrans2.py, mock.py
└── workers/
    ├── queue.py           Redis/RQ connection helpers
    └── tasks.py           process_lecture_task, translate_lecture_task
```

### Provider policy

* Every AI capability sits behind a small interface (`ASRProvider`,
  `LLMProvider`, `TranslationProvider`).
* Concrete providers are chosen by environment variables
  (`ASR_PROVIDER`, `LLM_PROVIDER`, `TRANSLATION_PROVIDER`) with values
  `mock` | `indicconformer` | `param1` | `indictrans2`.
* Real providers **lazy-load** weights on first use — never at startup.
  A load failure raises `ModelLoadError` with actionable configuration guidance
  and marks the job `FAILED` with that message.
* Mock results are always flagged (`is_mock=True`) and surfaced in the API
  (`/api/v1/settings/providers`) and in the UI so they are never mistaken for
  real inference.
* An optional remote HTTP mode (`*_REMOTE_URL`) calls a GPU inference server
  for each provider when local hardware is unavailable.

## 4. Data model

| Entity | Purpose |
|---|---|
| `lectures` | title, audio path, source/target language, duration, status |
| `jobs` | stage, progress (completed stages / total), error, timestamps |
| `transcript_segments` | ordered segments with `start_time`/`end_time`, language |
| `notes` | language + validated structured JSON (one row per language) |
| `quiz_questions` | 5 rows/lecture: question, options JSON, correct option, explanation |
| `quiz_attempts` | submitted answers JSON, score, total |
| `content_translations` | cache: (lecture, content_type, language) -> translated payload |

Relationships are indexed on `lecture_id`; `jobs.status` and
`lectures.status` are indexed for dashboard queries.

## 5. Job stages

```
QUEUED -> PREPROCESSING -> TRANSCRIBING -> [TRANSLATING_INPUT]
       -> [GENERATING_NOTES] -> [GENERATING_QUIZ] -> [TRANSLATING_OUTPUT]
       -> VALIDATING -> COMPLETED | FAILED
```

`progress = completed_stages / total_stages` where the stage list is derived
from the actual work items of that job (e.g. translation stages only exist when
requested). Progress is never faked with timers.

## 6. Multilingual flow

1. Original transcript stored in source language (never overwritten).
2. If source ∉ {English, Hindi} (Param-1 language envelope) or the user wants
   generation in English: IndicTrans2 source→`eng_Latn`.
3. Param-1 (English canonical) generates notes + exactly 5 MCQs.
4. Strict Pydantic validation with bounded retries (2) on malformed output.
5. On demand, IndicTrans2 translates transcript/notes/quiz into the selected
   target language; results are cached in `content_translations` and structural
   IDs (question id, option ids, correct answer) are preserved verbatim.

## 7. Security notes

* Uploads validated by extension **and** `ffprobe` content sniffing; stored
  under `STORAGE_ROOT/uploads/<uuid><ext>` outside any public dir; UUID
  filenames prevent path traversal.
* Configurable `MAX_UPLOAD_BYTES` and `MAX_AUDIO_DURATION_SECONDS`.
* CORS restricted via `CORS_ORIGINS`; no secrets in the frontend bundle.
* Failed jobs always end in `FAILED` with a user-readable message.

## 8. Scaling path

* API and worker are stateless → horizontally scalable.
* SSE endpoint can replace polling without changing the job model.
* Local FS storage can be swapped for object storage behind `storage.py`.
