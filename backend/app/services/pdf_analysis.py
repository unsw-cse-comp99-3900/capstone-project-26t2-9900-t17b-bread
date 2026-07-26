"""Detect whether a PDF is text-based or image-based (scanned).

A "text" PDF has selectable text that can be extracted directly (fast, no OCR).
An "image" PDF (a scan or a photo saved as PDF) has little or no selectable
text; its content lives inside page images and must be read with OCR.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal

import fitz  # PyMuPDF

from app.config import Settings, get_settings
from app.services.errors import ErrorCode, PipelineError, PipelineStage

PdfType = Literal["text", "image"]


@dataclass
class PdfAnalysis:
    """Result of inspecting a PDF's structure."""

    pdf_type: PdfType
    page_count: int
    total_text_chars: int
    chars_per_page: float
    pages_with_images: int
    extracted_text: str  # directly-extractable text (may be empty for scans)

    @property
    def is_image_based(self) -> bool:
        return self.pdf_type == "image"


def analyze_pdf(
    content: bytes,
    *,
    settings: Settings | None = None,
    article_ref: str | None = None,
) -> PdfAnalysis:
    """Inspect a PDF and classify it as text-based or image-based."""
    settings = settings or get_settings()

    try:
        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - unreadable/corrupted PDF
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_PARSE_FAILED,
            article_ref=article_ref,
        ) from exc

    try:
        page_count = doc.page_count
        if page_count == 0:
            raise PipelineError(
                PipelineStage.UPLOAD,
                ErrorCode.UPLOAD_EMPTY_DOCUMENT,
                article_ref=article_ref,
            )

        text_parts: list[str] = []
        total_chars = 0
        pages_with_images = 0

        for page in doc:
            page_text = (page.get_text("text") or "").strip()
            if page_text:
                text_parts.append(page_text)
                total_chars += len(page_text)
            if page.get_images(full=True):
                pages_with_images += 1

        chars_per_page = total_chars / page_count if page_count else 0.0

        # Image-based when the average selectable text per page is below the
        # threshold. Requiring page images avoids misclassifying genuinely
        # short (but text) documents as scans.
        is_image = (
            chars_per_page < settings.pdf_image_char_threshold
            and pages_with_images > 0
        )

        return PdfAnalysis(
            pdf_type="image" if is_image else "text",
            page_count=page_count,
            total_text_chars=total_chars,
            chars_per_page=round(chars_per_page, 2),
            pages_with_images=pages_with_images,
            extracted_text="\n\n".join(text_parts).strip(),
        )
    finally:
        doc.close()
