"""Domain exceptions and FastAPI error handlers."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("lecturelens.error")


class AppError(Exception):
    """Base application error with an HTTP status code."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, detail: Optional[Any] = None,
                 code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"error": {"code": self.code, "message": self.message}}
        if self.detail is not None:
            payload["error"]["detail"] = self.detail
        return payload


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class UnsupportedMediaError(AppError):
    status_code = 415
    code = "unsupported_media"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class ModelLoadError(AppError):
    """Raised when a real model provider cannot be loaded/initialized."""

    status_code = 503
    code = "model_unavailable"


class ProviderError(AppError):
    status_code = 502
    code = "provider_error"


class GenerationError(AppError):
    """LLM output could not be validated after bounded retries."""

    status_code = 502
    code = "generation_error"


class JobError(AppError):
    status_code = 500
    code = "job_error"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error",
                               "message": "An unexpected server error occurred."}},
        )
