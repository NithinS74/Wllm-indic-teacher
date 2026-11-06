"""Health & provider-status endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.ai.factory import provider_statuses
from app.core.config import settings
from app.db.session import engine
from app.schemas.api import ProviderStatus, SettingsOut
from app.core.languages import LANGUAGES

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    redis_ok = True
    try:
        from redis import Redis
        Redis.from_url(settings.redis_url).ping()
    except Exception:  # noqa: BLE001
        redis_ok = False
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "app": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/settings/providers", response_model=list[ProviderStatus])
def providers() -> list[ProviderStatus]:
    """Mock vs real status for every AI provider (never loads weights)."""
    return [
        ProviderStatus(name=p.name, provider=p.provider, mode=p.mode,
                       loaded=p.loaded, detail=p.detail)
        for p in provider_statuses()
    ]


@router.get("/settings", response_model=SettingsOut)
def app_settings() -> SettingsOut:
    return SettingsOut(
        app_name=settings.app_name,
        providers=[
            ProviderStatus(name=p.name, provider=p.provider, mode=p.mode,
                           loaded=p.loaded, detail=p.detail)
            for p in provider_statuses()
        ],
        languages=[
            {"key": l.key, "label": l.label, "script": l.script,
             "indictrans": l.indictrans}
            for l in LANGUAGES
        ],
        limits={
            "max_upload_bytes": settings.max_upload_bytes,
            "max_audio_duration_seconds": settings.max_audio_duration_seconds,
            "min_audio_duration_seconds": settings.min_audio_duration_seconds,
            "allowed_extensions": sorted(settings.allowed_extensions_set),
            "chunk_duration_seconds": settings.chunk_duration_seconds,
        },
    )
