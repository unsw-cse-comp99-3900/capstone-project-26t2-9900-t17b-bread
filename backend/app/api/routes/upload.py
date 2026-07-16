"""Upload Controller — ingest PDF and Word documents."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import get_settings
from app.schemas.article import PdfTypeResponse, RawArticle, UploadResponse
from app.schemas.progress import ProcessingSummary
from app.services.document_service import (
    convert_image_pdf_to_word,
    parse_uploaded_document_async,
    validate_upload_file,
)
from app.services.errors import ErrorCode, PipelineError, PipelineStage
from app.services.ocr_service import is_ocr_available
from app.services.pdf_analysis import analyze_pdf
from app.services.preprocessing_service import preprocess_article
from app.services.progress import ProgressTracker
from app.services.streaming import streaming_response_from_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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
    """Extract readable article text from an uploaded PDF (.pdf) or Word (.docx) file.

    Text PDFs are read directly; scanned/image PDFs are recognised with OCR
    automatically (Tesseract required on the server for image PDFs).
    """
    return await _process_upload(file)


@router.post(
    "/pdf-type",
    response_model=PdfTypeResponse,
    summary="Detect whether an uploaded PDF is text-based or a scanned image PDF",
)
async def detect_pdf_type(file: UploadFile = File(...)) -> PdfTypeResponse:
    """Classify a PDF as text-based or image-based (scanned) before processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    content = await file.read()
    settings = get_settings()

    try:
        validate_upload_file(file.filename, content, settings=settings, article_ref="upload")
        ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
        if ext != "pdf":
            raise PipelineError(
                PipelineStage.UPLOAD,
                ErrorCode.UPLOAD_UNSUPPORTED_TYPE,
                article_ref="upload",
            )
        analysis = analyze_pdf(content, settings=settings, article_ref="upload")
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict()) from exc

    ocr_ready = is_ocr_available(settings)
    return PdfTypeResponse(
        pdf_type=analysis.pdf_type,
        is_image_based=analysis.is_image_based,
        page_count=analysis.page_count,
        chars_per_page=analysis.chars_per_page,
        pages_with_images=analysis.pages_with_images,
        ocr_available=ocr_ready,
        recommended_endpoint=(
            "/api/upload/pdf-to-word" if analysis.is_image_based else "/api/upload"
        ),
    )


@router.post(
    "/pdf-to-word",
    summary="Convert a scanned/image PDF to a cleaned, downloadable Word (.docx) file",
)
async def pdf_to_word(file: UploadFile = File(...)) -> Response:
    """OCR an image PDF, remove noise, and return a downloadable .docx file.

    Also accepts text-based PDFs (their selectable text is exported directly).
    Response body is the .docx binary with a `Content-Disposition` attachment
    header; cleaned text is echoed in the `X-Extracted-Text-Preview` header.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    content = await file.read()

    try:
        docx_bytes, download_name, cleaned_text = await asyncio.to_thread(
            convert_image_pdf_to_word,
            content,
            file.filename,
            article_ref="upload",
            require_image_pdf=False,
        )
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict()) from exc

    quoted = urllib.parse.quote(download_name)
    preview = cleaned_text[:180].replace("\n", " ")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        "X-Extracted-Chars": str(len(cleaned_text)),
        "X-Extracted-Text-Preview": urllib.parse.quote(preview),
        "Access-Control-Expose-Headers": (
            "Content-Disposition, X-Extracted-Chars, X-Extracted-Text-Preview"
        ),
    }
    return Response(content=docx_bytes, media_type=_DOCX_MEDIA_TYPE, headers=headers)


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
