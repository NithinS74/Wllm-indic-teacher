# LectureLens

Multilingual AI lecture → notes & quiz generator.

Upload an audio/video lecture, get back a transcript, structured notes, and a
multiple-choice quiz — with on-demand translation between English, Hindi,
Kannada, Tamil, Telugu, and Malayalam.

**Stack:** React + TypeScript + Vite (frontend) · FastAPI + PostgreSQL + Redis/RQ
(backend) · IndicConformer ASR · Param-1 LLM · IndicTrans2 translation.

By default the app runs in **mock mode**: no model downloads, deterministic
demo output, clearly badged in the UI. Flip providers to real models when
weights are available (see [docs/model-selection.md](docs/model-selection.md)).

---

## Quick start (local, no Docker)

Prerequisites: Python 3.12+, Node 22+, PostgreSQL 16, Redis 7, ffmpeg.

```bash
# 1. Database
sudo -u postgres psql -c "CREATE USER lecturelens WITH PASSWORD 'lecturelens' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE lecturelens OWNER lecturelens;"
sudo -u postgres psql -c "CREATE DATABASE lecturelens_test OWNER lecturelens;"

# 2. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
INLINE_JOBS=true .venv/bin/uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs

# 3. Background worker (optional if INLINE_JOBS=true)
#    rq worker --url redis://localhost:6379/0 lecturelens

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

Then open http://localhost:5173, upload an audio file, and watch the pipeline.

### Docker Compose (full stack)

```bash
cp .env.example .env
docker compose up --build
# Frontend → http://localhost:8080
# API      → http://localhost:8000/docs
```

---

## How it works

```
audio upload → ffmpeg normalize → energy VAD segmentation
    → ASR (per segment, timestamps)
    → [translate to English if needed]
    → hierarchical notes (chunked LLM calls)
    → quiz generation (strict schema validation)
    → [cache translations on demand]
```

Job progress = completed stages / total stages (no fake timers). Failures mark
the job `FAILED` with a readable error. See [docs/architecture.md](docs/architecture.md).

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health` | liveness + provider info |
| GET | `/api/v1/settings/providers` | active providers (mock vs real) |
| POST | `/api/v1/lectures` | upload audio (multipart) |
| GET | `/api/v1/lectures` | list |
| GET | `/api/v1/lectures/{id}` | detail + available translations |
| DELETE | `/api/v1/lectures/{id}` | delete |
| GET | `/api/v1/lectures/{id}/audio` | stream original audio |
| GET | `/api/v1/lectures/{id}/jobs` | job history |
| GET | `/api/v1/jobs/{id}` | job status/progress |
| GET | `/api/v1/lectures/{id}/transcript` | segments |
| GET | `/api/v1/lectures/{id}/notes` | notes (`?language=`) |
| GET | `/api/v1/lectures/{id}/quiz` | quiz (`?language=`) |
| POST | `/api/v1/lectures/{id}/quiz/attempt` | submit answers → score |
| GET | `/api/v1/lectures/{id}/quiz/attempts` | attempt history |
| POST | `/api/v1/lectures/{id}/translate` | queue output translation |
| GET | `/api/v1/lectures/{id}/export` | `?format=markdown\|txt` |

Interactive docs: `http://localhost:8000/docs`.

## Tests

```bash
# Backend (42 tests, uses lecturelens_test DB, inline jobs)
cd backend
INLINE_JOBS=true .venv/bin/pytest tests/ -q

# Frontend gate
cd frontend
npm run build          # tsc --noEmit + vite build
```

## Evaluation

Human-referenced metrics (WER/CER/notes/quiz/translation) live in
[`evaluation/`](evaluation/README.md). Scripts only score against references
you provide — they never fabricate results.

```bash
cd evaluation
python evaluate_wer.py --manifest test_manifest.csv --refs references/
python evaluate_cer.py --manifest test_manifest.csv --refs references/
```

## Repository layout

```
backend/          FastAPI app, AI providers, workers, tests
frontend/         React SPA (Vite + Tailwind)
docs/             architecture, implementation plan, model selection
evaluation/       metric scripts, test manifest, references, results
infrastructure/   deployment notes
docker-compose.yml
.env.example
```

## Configuration

All knobs live in `.env` (copy from `.env.example`): database URL, storage
root, provider selection (`mock` / real), model paths, CORS, queue settings.
Auth is intentionally omitted (single-user MVP); PDF export is client-side
browser print.

## Further reading

- [docs/architecture.md](docs/architecture.md) — components & data flow
- [docs/implementation-plan.md](docs/implementation-plan.md) — phased plan
- [docs/model-selection.md](docs/model-selection.md) — why IndicConformer /
  Param-1 / IndicTrans2, with links to official repos
- [infrastructure/README.md](infrastructure/README.md) — Docker & production
