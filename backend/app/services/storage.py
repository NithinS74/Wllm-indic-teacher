"""Safe filesystem storage for uploads/processed files."""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.errors import AppError, ValidationAppError

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def ensure_dirs() -> None:
    for d in (settings.uploads_dir, settings.processed_dir, settings.exports_dir):
        d.mkdir(parents=True, exist_ok=True)


def safe_original_filename(name: str) -> str:
    """Strip any path components and dangerous characters from a client filename."""
    name = Path(name.replace("\\", "/")).name  # also blocks traversal sequences
    name = _SAFE_NAME.sub("_", name).strip("._") or "audio"
    return name[:100]


def build_upload_path(original_name: str) -> Path:
    """Return a fresh UUID-based path inside the uploads directory."""
    ensure_dirs()
    ext = Path(safe_original_filename(original_name)).suffix.lower()
    if ext not in settings.allowed_extensions_set:
        raise ValidationAppError(
            f"File type '{ext or original_name}' is not allowed.",
            detail={"allowed": sorted(settings.allowed_extensions_set)},
        )
    return settings.uploads_dir / f"{uuid.uuid4().hex}{ext}"


def save_stream(stream: BinaryIO, dest: Path, max_bytes: int) -> int:
    """Stream upload to dest with a hard byte cap. Returns bytes written."""
    written = 0
    try:
        with dest.open("wb") as fh:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise_app_too_large(max_bytes)
                fh.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    if written == 0:
        dest.unlink(missing_ok=True)
        raise ValidationAppError("Uploaded file is empty.")
    return written


def raise_app_too_large(max_bytes: int) -> None:
    from app.core.errors import FileTooLargeError
    raise FileTooLargeError(
        f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
        detail={"max_bytes": max_bytes},
    )


def resolve_within(root: Path, relative: str) -> Path:
    """Resolve a stored relative path and guarantee it stays inside root."""
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if not str(candidate).startswith(str(root_resolved) + "/") and candidate != root_resolved:
        raise AppError("Invalid storage path.", status_code=400, code="path_error")
    return candidate


def delete_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
