"""OCR for image-based (scanned) PDFs.

Pages are rendered to images with PyMuPDF and read with Tesseract (via
``pytesseract``). Tesseract is an external engine; if it is not installed the
service degrades gracefully and raises a clear ``OCR_UNAVAILABLE`` error rather
than crashing, so the rest of the backend keeps working.
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass

import fitz  # PyMuPDF

from app.config import Settings, get_settings
from app.services.errors import ErrorCode, PipelineError, PipelineStage
from app.services.ocr_cleaning import clean_ocr_pages


@dataclass
class OcrResult:
    """Outcome of running OCR over an image-based PDF."""

    raw_pages: list[str]
    cleaned_text: str
    page_count: int
    engine: str


def _resolve_tesseract(settings: Settings) -> str | None:
    """Return the tesseract executable path, or None if unavailable."""
    try:
        import pytesseract
    except ImportError:
        return None

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        return settings.tesseract_cmd

    configured = pytesseract.pytesseract.tesseract_cmd
    # pytesseract defaults to the bare name "tesseract"; resolve via PATH.
    found = shutil.which(configured) or shutil.which("tesseract")
    return found


def is_ocr_available(settings: Settings | None = None) -> bool:
    """True when both pytesseract and the Tesseract binary are present."""
    settings = settings or get_settings()
    return _resolve_tesseract(settings) is not None


def _render_pages_to_images(content: bytes, dpi: int, article_ref: str | None):
    try:
        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_PARSE_FAILED,
            article_ref=article_ref,
        ) from exc

    from PIL import Image  # local import; Pillow ships with PyMuPDF stacks

    images = []
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for page in doc:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            images.append(image)
    finally:
        doc.close()
    return images


def run_ocr(
    content: bytes,
    *,
    settings: Settings | None = None,
    article_ref: str | None = None,
) -> OcrResult:
    """Render an image PDF to images, OCR each page, and clean the result."""
    settings = settings or get_settings()

    tesseract_path = _resolve_tesseract(settings)
    if tesseract_path is None:
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.OCR_UNAVAILABLE,
            article_ref=article_ref,
        )

    import pytesseract

    try:
        images = _render_pages_to_images(content, settings.ocr_dpi, article_ref)
        raw_pages: list[str] = []
        for image in images:
            page_text = pytesseract.image_to_string(image, lang=settings.ocr_languages)
            raw_pages.append(page_text or "")
    except PipelineError:
        raise
    except Exception as exc:  # noqa: BLE001 - any OCR/render failure
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.OCR_FAILED,
            article_ref=article_ref,
        ) from exc

    cleaned = clean_ocr_pages(raw_pages)

    if not cleaned.strip():
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.OCR_NO_TEXT_FOUND,
            article_ref=article_ref,
        )

    return OcrResult(
        raw_pages=raw_pages,
        cleaned_text=cleaned,
        page_count=len(raw_pages),
        engine=f"tesseract ({settings.ocr_languages})",
    )
