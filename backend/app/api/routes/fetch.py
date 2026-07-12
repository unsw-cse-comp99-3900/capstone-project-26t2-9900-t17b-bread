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
