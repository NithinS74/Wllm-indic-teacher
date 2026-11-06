"""Shared API dependencies."""
from __future__ import annotations

from typing import Generator

from fastapi import Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models.entities import Lecture

DbSession = Generator[Session, None, None]


def db_dep() -> DbSession:
    yield from get_db()


def get_lecture(lecture_id: str = Path(..., description="Lecture UUID"),
                db: Session = Depends(db_dep)) -> Lecture:
    lecture = db.get(Lecture, lecture_id)
    if lecture is None:
        raise NotFoundError(f"Lecture '{lecture_id}' not found.")
    return lecture
