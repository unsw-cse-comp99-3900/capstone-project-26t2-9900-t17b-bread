"""Parse uploaded PDF and Word (.docx) documents into RawArticle objects."""

from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.config import Settings, get_settings
from app.schemas.article import RawArticle
from app.services.errors import ErrorCode, PipelineError, PipelineStage
from app.services.progress import ProgressTracker

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _extension_of(filename: str | None) -> str:
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def validate_upload_file(
    filename: str | None,
    content: bytes,
    *,
    settings: Settings | None = None,
    article_ref: str | None = None,
) -> str:
    """Validate upload size/type and return normalized extension."""
    settings = settings or get_settings()

    if not content:
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_FILE_MISSING,
            article_ref=article_ref,
        )

    if len(content) > settings.upload_max_bytes:
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_FILE_TOO_LARGE,
            article_ref=article_ref,
        )

    ext = _extension_of(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_UNSUPPORTED_TYPE,
            article_ref=article_ref,
        )
    return ext


def _parse_pdf(content: bytes) -> tuple[str | None, str]:
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        body = "\n\n".join(part.strip() for part in pages if part.strip()).strip()
        title = (reader.metadata.title or None) if reader.metadata else None
        return title, body
    except Exception as exc:  # noqa: BLE001 - surface as upload parse failure
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_PARSE_FAILED,
            article_ref=None,
        ) from exc


def _parse_docx(content: bytes) -> tuple[str | None, str]:
    try:
        document = Document(io.BytesIO(content))
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        body = "\n\n".join(paragraphs).strip()
        title = document.core_properties.title or None
        return title, body
    except Exception as exc:  # noqa: BLE001 - surface as upload parse failure
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_PARSE_FAILED,
            article_ref=None,
        ) from exc


def parse_uploaded_document(
    content: bytes,
    filename: str | None,
    *,
    article_ref: str | None = None,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
) -> RawArticle:
    """Convert an uploaded PDF or Word file into a RawArticle."""
    settings = settings or get_settings()
    ext = validate_upload_file(filename, content, settings=settings, article_ref=article_ref)

    display_name = Path(filename or "upload").name
    pseudo_url = f"upload://{display_name}"

    if progress is not None:
        # sync path; caller emits async events around this function
        pass

    if ext == ".pdf":
        title, body_text = _parse_pdf(content)
    else:
        title, body_text = _parse_docx(content)

    if not body_text.strip():
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_EMPTY_DOCUMENT,
            article_ref=article_ref,
            url=pseudo_url,
        )

    if not title:
        title = Path(display_name).stem.replace("_", " ").replace("-", " ").strip() or None

    return RawArticle(
        url=pseudo_url,
        title=title,
        source_domain="upload",
        body_text=body_text,
        source_type="upload",
    )


async def parse_uploaded_document_async(
    content: bytes,
    filename: str | None,
    *,
    article_ref: str | None = None,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
) -> RawArticle:
    """Async wrapper that emits English progress messages while parsing uploads."""
    settings = settings or get_settings()

    if progress is not None:
        await progress.emit(
            message=f"Validating uploaded file for article {article_ref or ''}...".strip(),
            step="validation",
            article_ref=article_ref,
            status="running",
        )

    ext = validate_upload_file(filename, content, settings=settings, article_ref=article_ref)

    if progress is not None:
        await progress.emit(
            message=f"Validated {ext} upload for article {article_ref or ''}.".strip(),
            step="validation",
            article_ref=article_ref,
            status="completed",
        )
        await progress.emit(
            message=f"Reading text from uploaded {ext} for article {article_ref or ''}...".strip(),
            step="upload",
            article_ref=article_ref,
            status="running",
        )

    article = parse_uploaded_document(
        content,
        filename,
        article_ref=article_ref,
        settings=settings,
    )

    if progress is not None:
        await progress.emit(
            message=f"Finished reading uploaded document for article {article_ref or ''}.".strip(),
            step="upload",
            article_ref=article_ref,
            status="completed",
        )

    return article
