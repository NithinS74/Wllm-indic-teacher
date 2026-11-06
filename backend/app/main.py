"""LectureLens FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import content, health, jobs, lectures
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.services.storage import ensure_dirs

configure_logging(settings.log_level)
logger = logging.getLogger("lecturelens.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_dirs()
    logger.info(
        "LectureLens starting (env=%s, providers: asr=%s llm=%s translation=%s)",
        settings.app_env, settings.asr_provider, settings.llm_provider,
        settings.translation_provider,
    )
    yield
    logger.info("LectureLens shutting down.")


app = FastAPI(
    title="LectureLens API",
    version="1.0.0",
    description=(
        "Multilingual AI lecture-to-notes & quiz generator. "
        "Long-running inference runs in background RQ workers — poll "
        "`/api/v1/jobs/{job_id}` for progress."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

API = settings.api_prefix
app.include_router(health.router, prefix=API)
app.include_router(lectures.router, prefix=API)
app.include_router(jobs.router, prefix=API)
app.include_router(content.router, prefix=API)


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse({
        "name": settings.app_name,
        "api": API,
        "docs": "/docs",
        "health": f"{API}/health",
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000,
                reload=settings.debug)
