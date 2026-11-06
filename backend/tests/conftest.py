"""Pytest configuration.

Environment variables are set BEFORE any app import so that settings pick up
the test database, a temp storage root, inline job execution and mock AI
providers.
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_TMP = tempfile.mkdtemp(prefix="lecturelens-test-")

os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": "postgresql+psycopg2://lecturelens:lecturelens@localhost:5432/lecturelens_test",
    "REDIS_URL": "redis://localhost:6379/1",
    "STORAGE_ROOT": _TMP,
    "INLINE_JOBS": "true",
    "ASR_PROVIDER": "mock",
    "LLM_PROVIDER": "mock",
    "TRANSLATION_PROVIDER": "mock",
    "LOG_LEVEL": "WARNING",
    "MAX_AUDIO_DURATION_SECONDS": "600",
    "MIN_AUDIO_DURATION_SECONDS": "1.0",
})

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Recreate the test schema via Alembic migrations."""
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from sqlalchemy import text

    from app.db.session import engine

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    cfg = AlembicConfig(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")
    yield engine


@pytest.fixture()
def db(_database):
    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(_database):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.ai.factory import reset_providers
    from app.workers.queue import reset_queue

    reset_providers()
    reset_queue()
    with TestClient(app) as c:
        yield c
    reset_providers()
    reset_queue()


@pytest.fixture()
def demo_wav_bytes() -> bytes:
    """A ~6 s WAV (tone bursts + silence) written with the stdlib wave module."""
    import math
    import struct
    import io
    import wave

    sample_rate = 16000
    frames = bytearray()

    def tone(freq: float, seconds: float, amp: float = 0.4) -> None:
        n = int(sample_rate * seconds)
        for i in range(n):
            v = amp * math.sin(2 * math.pi * freq * i / sample_rate)
            frames.extend(struct.pack("<h", int(v * 32767)))

    def silence(seconds: float) -> None:
        frames.extend(b"\x00\x00" * int(sample_rate * seconds))

    tone(220, 2.0)
    silence(0.5)
    tone(440, 2.0)
    silence(0.5)
    tone(330, 1.0)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


@pytest.fixture()
def upload_lecture(client, demo_wav_bytes):
    """Helper: upload a demo lecture and return (lecture_json, job_json)."""

    def _upload(title: str = "Demo Lecture", source: str = "en",
                target: str | None = None, translate: bool = False,
                notes: bool = True, quiz: bool = True,
                filename: str = "lecture.wav",
                data: bytes | None = None) -> dict:
        resp = client.post(
            "/api/v1/lectures",
            data={
                "title": title,
                "source_language": source,
                "target_language": target or "",
                "generate_notes": str(notes).lower(),
                "generate_quiz": str(quiz).lower(),
                "translate_content": str(translate).lower(),
            },
            files={"audio": (filename, data or demo_wav_bytes, "audio/wav")},
        )
        assert resp.status_code == 201, resp.text
        lecture = resp.json()
        job = client.get(f"/api/v1/jobs/{lecture['job_id']}").json()
        return {"lecture": lecture, "job": job}

    return _upload
