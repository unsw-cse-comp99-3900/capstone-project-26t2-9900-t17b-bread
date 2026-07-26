"""Parse uploaded PDF and Word (.docx) documents into RawArticle objects."""

from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.config import Settings, get_settings
from app.schemas.article import RawArticle
from app.services.errors import ErrorCode, PipelineError, PipelineStage
from app.services.ocr_service import run_ocr
from app.services.pdf_analysis import analyze_pdf
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


def _pdf_metadata_title(content: bytes) -> str | None:
    try:
        reader = PdfReader(io.BytesIO(content))
        return (reader.metadata.title or None) if reader.metadata else None
    except Exception:  # noqa: BLE001 - title is best-effort only
        return None


def _parse_pdf(
    content: bytes,
    *,
    article_ref: str | None = None,
    settings: Settings | None = None,
) -> tuple[str | None, str]:
    """Extract text from a PDF, using OCR automatically for scanned/image PDFs."""
    settings = settings or get_settings()
    analysis = analyze_pdf(content, settings=settings, article_ref=article_ref)

    if analysis.is_image_based:
        # Scanned / image PDF -> OCR + noise cleaning.
        ocr = run_ocr(content, settings=settings, article_ref=article_ref)
        return _pdf_metadata_title(content), ocr.cleaned_text

    body = analysis.extracted_text
    if not body.strip():
        # Fallback to pypdf if PyMuPDF returned nothing for a "text" PDF.
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            body = "\n\n".join(part.strip() for part in pages if part.strip()).strip()
        except Exception as exc:  # noqa: BLE001 - surface as upload parse failure
            raise PipelineError(
                PipelineStage.UPLOAD,
                ErrorCode.UPLOAD_PARSE_FAILED,
                article_ref=article_ref,
            ) from exc

    return _pdf_metadata_title(content), body


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
        title, body_text = _parse_pdf(content, article_ref=article_ref, settings=settings)
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


def convert_image_pdf_to_word(
    content: bytes,
    filename: str | None,
    *,
    settings: Settings | None = None,
    article_ref: str | None = None,
    require_image_pdf: bool = True,
) -> tuple[bytes, str, str]:
    """Convert a (scanned) image PDF into a cleaned Word document.

    Returns ``(docx_bytes, download_filename, cleaned_text)``.

    OCR is used to read the scanned pages, noise is removed, and the key text
    is written into a .docx. When ``require_image_pdf`` is True, a text-based
    PDF is rejected (``PDF_NOT_IMAGE_BASED``) so the caller can point users at
    the faster direct-text upload path instead.
    """
    from app.services.ocr_service import run_ocr
    from app.services.word_export_service import build_docx, download_filename_for

    settings = settings or get_settings()
    validate_upload_file(filename, content, settings=settings, article_ref=article_ref)

    ext = _extension_of(filename)
    if ext != ".pdf":
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_UNSUPPORTED_TYPE,
            article_ref=article_ref,
        )

    analysis = analyze_pdf(content, settings=settings, article_ref=article_ref)
    if require_image_pdf and not analysis.is_image_based:
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.PDF_NOT_IMAGE_BASED,
            article_ref=article_ref,
        )

    if analysis.is_image_based:
        cleaned_text = run_ocr(content, settings=settings, article_ref=article_ref).cleaned_text
    else:
        cleaned_text = analysis.extracted_text

    if not cleaned_text.strip():
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.OCR_NO_TEXT_FOUND,
            article_ref=article_ref,
        )

    title = _pdf_metadata_title(content)
    if not title:
        title = Path(filename or "converted").stem.replace("_", " ").replace("-", " ").strip() or None

    docx_bytes = build_docx(cleaned_text, title=title)
    download_name = download_filename_for(filename, title)
    return docx_bytes, download_name, cleaned_text


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
