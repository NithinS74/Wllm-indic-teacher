"""Job status endpoints (polling; SSE-ready shape)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db_dep
from app.core.errors import NotFoundError
from app.models.entities import Job
from app.schemas.api import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(db_dep)) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFoundError(f"Job '{job_id}' not found.")
    return JobOut.model_validate(job, from_attributes=True)
