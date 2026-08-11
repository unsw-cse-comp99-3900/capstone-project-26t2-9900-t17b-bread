"""Fetch Controller (proposal p.20)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.schemas.article import FetchRequest, RawArticle
from app.schemas.progress import ProcessingSummary
from app.services.errors import PipelineError
from app.services.fetch_service import fetch_article
from app.services.progress import ProgressTracker
from app.services.streaming import streaming_response_from_progress

router = APIRouter(prefix="/api/fetch", tags=["fetch"])

"""
Fetch Controller — High-Level Overview
--------------------------------------

This module provides the API endpoints responsible for fetching and cleaning
a single article from a user-supplied URL. It acts as the entry point for
article ingestion before any comparison or NLP processing occurs.

Key Responsibilities
--------------------
1. URL-Based Article Retrieval
   - Accepts a FetchRequest containing a URL.
   - Delegates the actual retrieval and cleaning to fetch_article(), which
     extracts the main content, title, domain, and cleaned body text.

2. Progress Tracking
   - Uses ProgressTracker to record timing, stage updates, and completion status.
   - Supports both standard responses and streaming Server-Sent Events (SSE)
     for real-time progress updates in the frontend.

3. Error Handling
   - Converts PipelineError exceptions into structured HTTP 422 responses.
   - Ensures consistent error formatting for frontend consumption.

4. Streaming Mode (SSE)
   - Provides a streaming endpoint that emits progress events as the article
     is fetched and cleaned.
   - Allows the frontend to display live progress for slow or large URLs.

Architectural Role
------------------
The Fetch Controller is intentionally lightweight. It does not perform any NLP
or comparison logic. Instead, it serves as a clean boundary between:

    • The FastAPI HTTP layer
    • The article-fetching service
    • The progress-tracking and streaming infrastructure

Its output (RawArticle + ProcessingSummary) is used by:
    • The Compare Controller (for full article-to-article comparison)
    • Any frontend components that need to preview or validate article content

By isolating article retrieval in its own controller, the system maintains:
    • Clear separation of concerns
    • Reusable article-fetching logic
    • Consistent progress reporting across all ingestion workflows
"""


class FetchResponse(RawArticle):
    processing: ProcessingSummary | None = None


@router.post("", summary="Fetch and clean a single article URL")
async def fetch_single(payload: FetchRequest) -> dict:
    """Retrieve one article and return its cleaned title/domain/body with timing info."""
    progress = ProgressTracker(name="fetch")
    try:
        article = await fetch_article(payload.url, article_ref="fetch", progress=progress)
        await progress.emit(
            percent=100,
            message=f"Article fetched in {progress.elapsed_seconds} seconds.",
            step="complete",
            status="completed",
        )
        data = article.model_dump()
        data["processing"] = progress.to_summary()
        return data
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict()) from exc


@router.post("/stream", summary="Fetch one URL with live English progress (SSE)")
async def fetch_single_stream(payload: FetchRequest):
    progress_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_progress(event: dict) -> None:
        await progress_queue.put(event)

    progress = ProgressTracker(name="fetch").bind(on_progress)

    async def runner() -> dict:
        try:
            article = await fetch_article(payload.url, article_ref="fetch", progress=progress)
            await progress.emit(
                percent=100,
                message=f"Article fetched in {progress.elapsed_seconds} seconds.",
                step="complete",
                status="completed",
            )
            data = article.model_dump()
            data["processing"] = progress.to_summary()
            return data
        except PipelineError as exc:
            return {"error": exc.to_dict(), "processing": progress.to_summary()}
        finally:
            await progress_queue.put(None)

    return streaming_response_from_progress(runner, progress_queue=progress_queue)
