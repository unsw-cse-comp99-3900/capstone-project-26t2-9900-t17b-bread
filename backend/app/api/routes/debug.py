"""Debug and observability endpoints.

Protected by the DEBUG_ENABLED setting (disabled by default in production).
Provides runtime system info, recent log entries, and configuration snapshot
to help troubleshoot issues without external tooling.
"""

from __future__ import annotations

import os
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app import __version__
from app.config import get_settings
from app.db.base import is_db_enabled
from app.logging_config import get_recent_logs

router = APIRouter(prefix="/debug", tags=["debug"])

_STARTUP_TIME = time.time()


def _require_debug_enabled() -> None:
    settings = get_settings()
    if not settings.debug_enabled:
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints are disabled. Set DEBUG_ENABLED=true in .env",
        )


@router.get("/info", summary="Runtime system information")
async def debug_info() -> dict[str, Any]:
    """Return system, runtime, and configuration details for troubleshooting."""
    _require_debug_enabled()

    import importlib.metadata

    settings = get_settings()
    uptime_seconds = time.time() - _STARTUP_TIME

    key_packages = [
        "fastapi", "uvicorn", "sqlalchemy", "httpx", "trafilatura",
        "sentence-transformers", "torch", "pydantic", "pymupdf", "pytesseract",
    ]
    installed_versions: dict[str, str] = {}
    for pkg in key_packages:
        try:
            installed_versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            installed_versions[pkg] = "not installed"

    return {
        "app": {
            "version": __version__,
            "uptime_seconds": round(uptime_seconds, 1),
            "started_at": datetime.fromtimestamp(
                _STARTUP_TIME, tz=timezone.utc
            ).isoformat(),
        },
        "system": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "pid": os.getpid(),
            "cwd": os.getcwd(),
        },
        "config": {
            "log_level": settings.log_level,
            "log_format": settings.log_format,
            "cors_origins": settings.cors_origin_list,
            "database_enabled": is_db_enabled(),
            "database_url_set": bool(settings.database_url),
            "ocr_languages": settings.ocr_languages,
            "tesseract_cmd": settings.tesseract_cmd or "(PATH)",
            "fetch_timeout": settings.fetch_timeout_seconds,
            "upload_max_bytes": settings.upload_max_bytes,
        },
        "packages": installed_versions,
    }


@router.get("/logs", summary="Recent application log entries")
async def debug_logs(
    limit: int = Query(default=100, ge=1, le=500),
    level: str | None = Query(default=None, description="Filter by level: DEBUG, INFO, WARNING, ERROR"),
) -> dict[str, Any]:
    """Return the most recent log entries from the in-memory ring buffer."""
    _require_debug_enabled()

    entries = get_recent_logs(limit=limit, level=level)
    return {
        "count": len(entries),
        "limit": limit,
        "level_filter": level,
        "entries": entries,
    }


@router.get("/health/detailed", summary="Detailed health check with subsystem status")
async def health_detailed() -> dict[str, Any]:
    """Extended health check including uptime, memory, DB, and OCR availability."""
    _require_debug_enabled()

    uptime_seconds = time.time() - _STARTUP_TIME

    # Memory usage (cross-platform best-effort)
    memory_mb: float | None = None
    try:
        import psutil  # type: ignore[import-untyped]
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024 * 1024)
    except (ImportError, Exception):
        pass

    # Database probe
    db_status = "disabled"
    if is_db_enabled():
        try:
            from app.db.base import ping_db
            await ping_db()
            db_status = "ok"
        except Exception as exc:
            db_status = f"error: {exc}"

    # OCR probe
    ocr_status = "unavailable"
    try:
        from app.services.ocr_service import is_ocr_available
        if is_ocr_available():
            ocr_status = "available"
    except Exception:  # noqa: BLE001, S110
        pass

    return {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": round(uptime_seconds, 1),
        "memory_mb": round(memory_mb, 1) if memory_mb else None,
        "subsystems": {
            "database": db_status,
            "ocr": ocr_status,
        },
    }
