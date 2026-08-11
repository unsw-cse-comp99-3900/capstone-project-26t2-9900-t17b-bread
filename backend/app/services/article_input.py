"""
Article Input Resolver — High-Level Overview
--------------------------------------------

This module provides a unified interface for loading article content from
three different user input sources:

    • Remote URLs
    • Pasted text
    • Uploaded documents (PDF, Word, image-based PDFs via OCR)

It ensures that all article inputs—regardless of origin—are normalised into a
consistent RawArticle structure before entering the NLP pipeline.

Key Responsibilities
--------------------
1. Unified Input Abstraction
   - ArticleInput dataclass represents one article source with a stable
     article_ref ("A", "B", "upload", "fetch").
   - Supports three modes:
        • URL-based ingestion
        • Direct pasted text
        • Uploaded file bytes

2. URL Resolution
   - Uses fetch_article() to retrieve and clean remote content.
   - Validates presence and formatting of the URL.
   - Integrates with ProgressTracker for stage updates.

3. Text Resolution
   - _resolve_text_article() handles pasted text without any network or OCR.
   - Enforces minimum length to prevent accidental empty/short submissions.
   - Extracts a lightweight title from the first non-empty line.

4. Upload Resolution
   - Delegates to parse_uploaded_document_async() for PDF/Word ingestion.
   - Supports OCR for scanned PDFs when available.
   - Ensures uploaded files are present and valid before processing.

5. Error Handling
   - Raises PipelineError with stage-specific codes for:
        • Missing input
        • Empty text
        • Too-short text
        • Missing upload bytes
   - Ensures consistent error formatting across all ingestion paths.

Architectural Role
------------------
The Article Input Resolver is the gateway into the NLP pipeline. It ensures:

    • All article sources are normalised into RawArticle objects
    • The pipeline never needs to know whether content came from a URL,
      pasted text, or an uploaded file
    • Validation and error handling occur before expensive processing
    • Progress updates are emitted consistently across all input types

By isolating input resolution in this module, the system maintains:

    • Clear separation between ingestion and NLP processing
    • Reusable logic for all controllers (compare, fetch, upload)
    • Predictable behaviour across diverse user input formats
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import Settings, get_settings
from app.schemas.article import RawArticle
from app.services.document_service import parse_uploaded_document_async
from app.services.errors import ErrorCode, PipelineError, PipelineStage
from app.services.fetch_service import fetch_article
from app.services.progress import ProgressTracker


# Minimum characters required for pasted text to be worth analysing.
_MIN_TEXT_CHARS = 20


@dataclass
class ArticleInput:
    """One article source: a remote URL, pasted text, or an uploaded document."""

    source_type: Literal["url", "text", "upload"]
    article_ref: str
    url: str | None = None
    text: str | None = None
    file_bytes: bytes | None = None
    filename: str | None = None

    @classmethod
    def from_url(cls, url: str | None, article_ref: str) -> ArticleInput:
        return cls(source_type="url", article_ref=article_ref, url=url)

    @classmethod
    def from_text(cls, text: str | None, article_ref: str) -> ArticleInput:
        return cls(source_type="text", article_ref=article_ref, text=text)

    @classmethod
    def from_upload(
        cls,
        content: bytes,
        filename: str | None,
        article_ref: str,
    ) -> ArticleInput:
        return cls(
            source_type="upload",
            article_ref=article_ref,
            file_bytes=content,
            filename=filename,
        )


def _first_line_title(text: str) -> str | None:
    """Use the first non-empty line as a lightweight title for pasted text."""
    for line in text.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate[:120]
    return None


async def resolve_raw_article(
    article_input: ArticleInput,
    *,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
) -> RawArticle:
    """Load a RawArticle from either a URL or an uploaded file."""
    settings = settings or get_settings()

    if article_input.source_type == "url":
        if not article_input.url or not article_input.url.strip():
            raise PipelineError(
                PipelineStage.VALIDATION,
                ErrorCode.INPUT_MISSING,
                article_ref=article_input.article_ref,
            )
        return await fetch_article(
            article_input.url,
            article_ref=article_input.article_ref,
            settings=settings,
            progress=progress,
        )

    if article_input.source_type == "text":
        return await _resolve_text_article(
            article_input,
            settings=settings,
            progress=progress,
        )

    if not article_input.file_bytes:
        raise PipelineError(
            PipelineStage.UPLOAD,
            ErrorCode.UPLOAD_FILE_MISSING,
            article_ref=article_input.article_ref,
        )

    return await parse_uploaded_document_async(
        article_input.file_bytes,
        article_input.filename,
        article_ref=article_input.article_ref,
        settings=settings,
        progress=progress,
    )


async def _resolve_text_article(
    article_input: ArticleInput,
    *,
    settings: Settings,
    progress: ProgressTracker | None = None,
) -> RawArticle:
    """Build a RawArticle directly from user-pasted text (no fetch / OCR)."""

    raw_text = (article_input.text or "").strip()

    if not raw_text:
        raise PipelineError(
            PipelineStage.VALIDATION,
            ErrorCode.TEXT_EMPTY,
            article_ref=article_input.article_ref,
        )

    if len(raw_text) < _MIN_TEXT_CHARS:
        raise PipelineError(
            PipelineStage.VALIDATION,
            ErrorCode.TEXT_TOO_SHORT,
            article_ref=article_input.article_ref,
        )

    if progress is not None:
        await progress.emit(
            step="fetch",
            article_ref=article_input.article_ref,
            status="completed",
            message=f"Loaded pasted text for article {article_input.article_ref}.",
        )

    return RawArticle(
        url=f"pasted-text://article-{article_input.article_ref.lower()}",
        title=_first_line_title(raw_text),
        source_domain="Pasted text",
        body_text=raw_text,
        source_type="text",
    )
