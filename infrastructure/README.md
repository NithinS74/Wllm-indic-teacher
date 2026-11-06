# Infrastructure

Deployment notes for LectureLens.

## Local (recommended for development)

No Docker required — see root `README.md`:

1. PostgreSQL 16 + Redis 7 (apt/system packages or any local install)
2. `backend/.venv` + `uvicorn app.main:app`
3. `rq worker --url $REDIS_URL lecturelens`
4. `npm run dev` in `frontend/`

## Docker Compose (full stack)

From the repository root:

```bash
cp .env.example .env
docker compose up --build
# API      → http://localhost:8000/docs
# Frontend → http://localhost:8080
```

Services: `db` (Postgres 16), `redis`, `api` (uvicorn + migrations on boot),
`worker` (RQ), `web` (nginx SPA + `/api` reverse proxy).

Set `INLINE_JOBS=true` in `.env` to skip the worker (jobs run in-process —
fine for demos, not for production).

## Real models (optional)

Default providers are `mock`. To enable real inference, install the optional
ML dependencies inside the backend image (see `backend/requirements.txt`
comments and `docs/model-selection.md`), mount model weights at `/models`,
and set:

```
ASR_PROVIDER=indicconformer
LLM_PROVIDER=param1
TRANSLATION_PROVIDER=indictrans2
ASR_MODEL_PATH=/models/indicconformer_asr_base.nemo
LLM_MODEL_PATH=/models/Param-1-2.9B-Instruct
TRANSLATION_MODEL_DIR=/models/indictrans2
```

Models are never downloaded at startup; providers lazy-load and fail with a
clear `ModelLoadError` if weights are missing.

## Production hardening checklist

- [ ] Change `POSTGRES_PASSWORD` and all secrets in `.env`
- [ ] Restrict `CORS_ORIGINS` to your real frontend origin
- [ ] Put TLS termination in front of `web` / `api`
- [ ] Set `INLINE_JOBS=false` and run ≥1 `worker` replica
- [ ] Persistent volumes for `pgdata` and `storage`
- [ ] Log shipping / metrics (uvicorn access logs → collector)
- [ ] Backup policy for Postgres + storage volume
