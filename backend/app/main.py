"""FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
Interactive API docs are then available at http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import auth, compare, fetch, history, upload
from app.api.routes import debug as debug_routes
from app.config import get_settings
from app.db.base import dispose_engine, is_db_enabled, ping_db
from app.logging_config import setup_logging
from app.middleware.request_logging import RequestLoggingMiddleware

settings = get_settings()

setup_logging(log_level=settings.log_level, log_format=settings.log_format)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify the database connection on startup (best-effort) and dispose on exit."""
    if is_db_enabled():
        try:
            await ping_db()
            logger.info("Database connection established.")
        except Exception:  # noqa: BLE001 - never block startup on DB issues
            logger.warning(
                "DATABASE_URL is set but the database is unreachable; "
                "the API will run with persistence disabled at runtime."
            )
    else:
        logger.info("No DATABASE_URL configured; persistence is disabled.")
    yield
    await dispose_engine()


app = FastAPI(
    title="Narrative Diff API",
    version=__version__,
    description=(
        "Backend for the T17B BREAD news narrative-comparison tool. "
        "Sprint 1 covers article ingestion, cleaning and sentence preparation."
    ),
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fetch.router)
app.include_router(compare.router)
app.include_router(upload.router)
app.include_router(debug_routes.router)
app.include_router(auth.router)
app.include_router(history.router)


@app.get("/health", tags=["meta"], summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/health/db", tags=["meta"], summary="Database connectivity check")
async def health_db() -> dict[str, str]:
    """Report database status: disabled, ok, or error."""
    if not is_db_enabled():
        return {"database": "disabled"}
    try:
        await ping_db()
        return {"database": "ok"}
    except Exception as exc:  # noqa: BLE001 - surface as status, not a 500
        logger.warning("Database health check failed: %s", exc)
        return {"database": "error"}
