"""Fetch Controller (proposal p.20).

A lightweight controller that retrieves article text from a user-provided URL
and returns it for frontend preview. It is intentionally decoupled from the
heavier comparison pipeline so quick preview requests never trigger the full
analysis workflow.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.article import FetchRequest, RawArticle
from app.services.errors import PipelineError
from app.services.fetch_service import fetch_article

router = APIRouter(prefix="/api/fetch", tags=["fetch"])


@router.post("", response_model=RawArticle, summary="Fetch and clean a single article")
async def fetch_single(payload: FetchRequest) -> RawArticle:
    """Retrieve one article and return its cleaned title/domain/body."""
    try:
        return await fetch_article(payload.url)
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict()) from exc
