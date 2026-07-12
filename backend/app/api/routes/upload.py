"""Upload Controller — ingest PDF and Word documents."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.article import RawArticle, UploadResponse
from app.schemas.progress import ProcessingSummary
from app.services.document_service import parse_uploaded_document_async
from app.services.errors import PipelineError
from app.services.preprocessing_service import preprocess_article
from app.services.progress import ProgressTracker
from app.services.streaming import streaming_response_from_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])


async def _process_upload(file: UploadFile) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    content = await file.read()
    progress = ProgressTracker(name="upload")

    try:
        raw = await parse_uploaded_document_async(
            content,
            file.filename,
            article_ref="upload",
            progress=progress,
        )
        await progress.emit(
            percent=90,
            message="Preparing uploaded document for display...",
            step="preprocessing",
            status="running",
        )
        processed = preprocess_article(raw, "upload")
        raw = RawArticle(
            url=processed.url,
            title=processed.title,
            source_domain=processed.source_domain,
            body_text="\n\n".join(processed.paragraphs),
            source_type="upload",
        )
        await progress.emit(
            percent=100,
            message=f"Upload processed in {progress.elapsed_seconds} seconds.",
            step="complete",
            status="completed",
        )
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict()) from exc

    return UploadResponse(
        article=raw,
        processing=ProcessingSummary(**progress.to_summary()),
    )


@router.post("", response_model=UploadResponse, summary="Upload and parse a PDF or Word file")
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    """Extract readable article text from an uploaded PDF (.pdf) or Word (.docx) file."""
    return await _process_upload(file)


@router.post("/stream", summary="Upload a document with live English progress (SSE)")
async def upload_document_stream(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename
    progress_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_progress(event: dict) -> None:
        await progress_queue.put(event)

    progress = ProgressTracker(name="upload").bind(on_progress)

    async def runner() -> dict:
        try:
            raw = await parse_uploaded_document_async(
                content,
                filename,
                article_ref="upload",
                progress=progress,
            )
            processed = preprocess_article(raw, "upload")
            article = RawArticle(
                url=processed.url,
                title=processed.title,
                source_domain=processed.source_domain,
                body_text="\n\n".join(processed.paragraphs),
                source_type="upload",
            )
            await progress.emit(
                percent=100,
                message=f"Upload processed in {progress.elapsed_seconds} seconds.",
                step="complete",
                status="completed",
            )
            response = UploadResponse(
                article=article,
                processing=ProcessingSummary(**progress.to_summary()),
            )
            return response.model_dump()
        except PipelineError as exc:
            return {"error": exc.to_dict(), "processing": progress.to_summary()}
        finally:
            await progress_queue.put(None)

    return streaming_response_from_progress(runner, progress_queue=progress_queue)
