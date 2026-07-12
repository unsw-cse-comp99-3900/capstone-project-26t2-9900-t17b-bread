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


@dataclass
class ArticleInput:
    """One article source: either a remote URL or an uploaded document."""

    source_type: Literal["url", "upload"]
    article_ref: str
    url: str | None = None
    file_bytes: bytes | None = None
    filename: str | None = None

    @classmethod
    def from_url(cls, url: str | None, article_ref: str) -> ArticleInput:
        return cls(source_type="url", article_ref=article_ref, url=url)

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
