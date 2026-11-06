"""RQ task entrypoints.

Run a worker with:
    cd backend && rq worker --url $REDIS_URL lecturelens
"""
from __future__ import annotations

import logging

logger = logging.getLogger("lecturelens.worker")


def process_lecture_task(lecture_id: str) -> None:
    from app.services.pipeline import run_processing_pipeline
    run_processing_pipeline(lecture_id)


def translate_lecture_task(lecture_id: str, content_types: list, language: str) -> None:
    from app.services.pipeline import run_translation_pipeline
    run_translation_pipeline(lecture_id, content_types, language)
