"""FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
Interactive API docs are then available at http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import compare, fetch
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Narrative Diff API",
    version=__version__,
    description=(
        "Backend for the T17B BREAD news narrative-comparison tool. "
        "Sprint 1 covers article ingestion, cleaning and sentence preparation."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fetch.router)
app.include_router(compare.router)


@app.get("/health", tags=["meta"], summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
