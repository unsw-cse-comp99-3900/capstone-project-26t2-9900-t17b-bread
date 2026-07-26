"""Resolve article inputs from URLs or uploaded files."""

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
