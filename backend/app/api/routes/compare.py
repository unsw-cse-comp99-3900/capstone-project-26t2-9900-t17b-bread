"""Compare Controller (proposal p.19-20)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.schemas.compare import CompareRequest, CompareResponse, ComparisonFocus
from app.services.article_input import ArticleInput
from app.services.compare_helpers import build_compare_response, persist_compare_session
from app.services.pipeline import process_pair, process_pair_inputs
from app.services.progress import ProgressTracker
from app.services.streaming import streaming_response_from_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compare", tags=["compare"])


def _article_reference(article_input: ArticleInput) -> str:
    if article_input.source_type == "url":
        return article_input.url or ""
    return f"upload://{article_input.filename or 'document'}"


async def _build_article_input(
    article_ref: str,
    url: str | None,
    upload: UploadFile | None,
) -> ArticleInput:
    url_value = (url or "").strip()
    has_file = upload is not None and upload.filename

    if url_value and has_file:
        raise ValueError(
            f"Provide either a URL or a file for article {article_ref}, not both."
        )
    if not url_value and not has_file:
        raise ValueError(
            f"Article {article_ref} is missing. Provide a URL or upload a PDF/Word file."
        )
    if has_file:
        content = await upload.read()
        return ArticleInput.from_upload(content, upload.filename, article_ref)
    return ArticleInput.from_url(url_value, article_ref)


async def _run_compare(
    payload: CompareRequest,
    *,
    session: AsyncSession | None,
    progress: ProgressTracker | None = None,
) -> CompareResponse:
    results = await process_pair(
        payload.article_a_url,
        payload.article_b_url,
        progress=progress,
    )

    session_token = None
    if session is not None and any(r.ok for r in results):
        session_token = await persist_compare_session(
            session,
            [r.article for r in results if r.article is not None],
            payload.article_a_url,
            payload.article_b_url,
        )

    return build_compare_response(
        focus=payload.focus,
        results=results,
        progress=progress,
        session_token=session_token,
    )


async def _run_compare_inputs(
    article_a: ArticleInput,
    article_b: ArticleInput,
    focus: ComparisonFocus,
    *,
    session: AsyncSession | None,
    progress: ProgressTracker | None = None,
) -> CompareResponse:
    results = await process_pair_inputs(article_a, article_b, progress=progress)

    session_token = None
    if session is not None and any(r.ok for r in results):
        session_token = await persist_compare_session(
            session,
            [r.article for r in results if r.article is not None],
            _article_reference(article_a),
            _article_reference(article_b),
        )

    return build_compare_response(
        focus=focus,
        results=results,
        progress=progress,
        session_token=session_token,
    )


@router.post("", response_model=CompareResponse, summary="Process a pair of article URLs")
async def compare(
    payload: CompareRequest,
    session: AsyncSession | None = Depends(get_session),
) -> CompareResponse:
    progress = ProgressTracker(name="compare")
    return await _run_compare(payload, session=session, progress=progress)


@router.post("/stream", summary="Process two URLs with live English progress (SSE)")
async def compare_stream(
    payload: CompareRequest,
    session: AsyncSession | None = Depends(get_session),
):
    progress_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_progress(event: dict) -> None:
        await progress_queue.put(event)

    progress = ProgressTracker(name="compare").bind(on_progress)

    async def runner() -> dict:
        try:
            response = await _run_compare(payload, session=session, progress=progress)
            return response.model_dump()
        finally:
            await progress_queue.put(None)

    return streaming_response_from_progress(runner, progress_queue=progress_queue)


@router.post(
    "/files",
    response_model=CompareResponse,
    summary="Compare two articles from URLs and/or uploaded PDF/Word files",
)
async def compare_files(
    article_a_url: str | None = Form(default=None),
    article_b_url: str | None = Form(default=None),
    article_a_file: UploadFile | None = File(default=None),
    article_b_file: UploadFile | None = File(default=None),
    focus: ComparisonFocus = Form(default=ComparisonFocus.GENERAL),
    session: AsyncSession | None = Depends(get_session),
) -> CompareResponse:
    try:
        article_a = await _build_article_input("A", article_a_url, article_a_file)
        article_b = await _build_article_input("B", article_b_url, article_b_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    progress = ProgressTracker(name="compare")
    return await _run_compare_inputs(
        article_a,
        article_b,
        focus,
        session=session,
        progress=progress,
    )


@router.post(
    "/files/stream",
    summary="Compare mixed URL/file inputs with live English progress (SSE)",
)
async def compare_files_stream(
    article_a_url: str | None = Form(default=None),
    article_b_url: str | None = Form(default=None),
    article_a_file: UploadFile | None = File(default=None),
    article_b_file: UploadFile | None = File(default=None),
    focus: ComparisonFocus = Form(default=ComparisonFocus.GENERAL),
    session: AsyncSession | None = Depends(get_session),
):
    try:
        article_a = await _build_article_input("A", article_a_url, article_a_file)
        article_b = await _build_article_input("B", article_b_url, article_b_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    progress_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_progress(event: dict) -> None:
        await progress_queue.put(event)

    progress = ProgressTracker(name="compare").bind(on_progress)

    async def runner() -> dict:
        try:
            response = await _run_compare_inputs(
                article_a,
                article_b,
                focus,
                session=session,
                progress=progress,
            )
            return response.model_dump()
        finally:
            await progress_queue.put(None)

    return streaming_response_from_progress(runner, progress_queue=progress_queue)
