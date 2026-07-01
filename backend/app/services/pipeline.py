"""Article Processing Pipeline (PROJ-3)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.schemas.article import ProcessedArticle
from app.services.article_input import ArticleInput, resolve_raw_article
from app.services.embedding_service import get_embedding_service
from app.services.errors import PipelineError
from app.services.paragraph_chunking_service import build_paragraph_chunks
from app.services.preprocessing_service import preprocess_article
from app.services.progress import ProgressTracker


@dataclass
class ArticleResult:
    """Outcome of running the pipeline for a single article."""

    article_ref: str
    url: str | None
    article: ProcessedArticle | None = None
    paragraph_chunks: list[dict[str, Any]] | None = None
    chunk_embeddings: list[dict[str, Any]] | None = None
    error: PipelineError | None = None

    @property
    def ok(self) -> bool:
        return self.article is not None and self.error is None


async def _run_post_fetch_pipeline(
    raw,
    article_ref: str,
    *,
    settings: Settings,
    progress: ProgressTracker | None = None,
) -> ArticleResult:
    if progress is not None:
        await progress.emit(
            message=f"Cleaning and splitting sentences for article {article_ref}...",
            step="preprocessing",
            article_ref=article_ref,
            status="running",
        )

    processed = preprocess_article(raw, article_ref, settings=settings)

    if progress is not None:
        await progress.emit(
            message=f"Sentence preparation completed for article {article_ref}.",
            step="preprocessing",
            article_ref=article_ref,
            status="completed",
        )
        await progress.emit(
            message=f"Building paragraph chunks for article {article_ref}...",
            step="chunking",
            article_ref=article_ref,
            status="running",
        )

    paragraph_chunks = build_paragraph_chunks(processed)

    if progress is not None:
        await progress.emit(
            message=f"Generating semantic embeddings for article {article_ref}...",
            step="embedding",
            article_ref=article_ref,
            status="running",
        )

    embedding_service = get_embedding_service()
    chunk_embeddings = await asyncio.to_thread(
        embedding_service.encode_paragraph_chunks,
        paragraph_chunks,
    )

    if progress is not None:
        await progress.emit(
            message=f"Embeddings ready for article {article_ref}.",
            step="embedding",
            article_ref=article_ref,
            status="completed",
        )

    return ArticleResult(
        article_ref=article_ref,
        url=raw.url,
        article=processed,
        paragraph_chunks=paragraph_chunks,
        chunk_embeddings=chunk_embeddings,
    )


async def process_article_input(
    article_input: ArticleInput,
    *,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
    percent_start: int = 0,
    percent_end: int = 100,
) -> ArticleResult:
    """Run the full pipeline for one URL or uploaded document."""
    settings = settings or get_settings()
    article_ref = article_input.article_ref

    if progress is not None:
        await progress.emit(
            percent=percent_start,
            message=f"Starting processing for article {article_ref}...",
            step="start",
            article_ref=article_ref,
            status="running",
        )

    try:
        raw = await resolve_raw_article(article_input, settings=settings, progress=progress)
        mid = percent_start + int((percent_end - percent_start) * 0.55)
        if progress is not None:
            await progress.emit(
                percent=mid,
                message=f"Article {article_ref} loaded. Running NLP pipeline...",
            )

        result = await _run_post_fetch_pipeline(
            raw,
            article_ref,
            settings=settings,
            progress=progress,
        )

        if progress is not None:
            await progress.emit(
                percent=percent_end,
                message=f"Article {article_ref} processed successfully.",
                step="complete",
                article_ref=article_ref,
                status="completed",
            )
        return result
    except PipelineError as exc:
        if progress is not None:
            await progress.emit(
                percent=percent_end,
                message=f"Article {article_ref} failed: {exc.message}",
                step="complete",
                article_ref=article_ref,
                status="failed",
            )
        source = article_input.url or (
            f"upload://{article_input.filename}" if article_input.filename else None
        )
        return ArticleResult(article_ref=article_ref, url=source, error=exc)


async def process_article(
    raw_url: str | None,
    article_ref: str,
    *,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
    percent_start: int = 0,
    percent_end: int = 100,
) -> ArticleResult:
    """Backward-compatible URL-only entry point."""
    return await process_article_input(
        ArticleInput.from_url(raw_url, article_ref),
        settings=settings,
        progress=progress,
        percent_start=percent_start,
        percent_end=percent_end,
    )


async def process_pair_inputs(
    article_a: ArticleInput,
    article_b: ArticleInput,
    *,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
) -> list[ArticleResult]:
    """Process two mixed URL/upload inputs concurrently with shared progress."""
    settings = settings or get_settings()

    async def _run_a() -> ArticleResult:
        return await process_article_input(
            article_a,
            settings=settings,
            progress=progress,
            percent_start=5,
            percent_end=45,
        )

    async def _run_b() -> ArticleResult:
        return await process_article_input(
            article_b,
            settings=settings,
            progress=progress,
            percent_start=50,
            percent_end=90,
        )

    if progress is not None:
        await progress.emit(
            percent=1,
            message="Starting comparison pipeline for both articles...",
            step="start",
            status="running",
        )

    results = list(await asyncio.gather(_run_a(), _run_b()))

    if progress is not None:
        await progress.emit(
            percent=95,
            message="Finalizing comparison response...",
            step="finalize",
            status="running",
        )
        await progress.emit(
            percent=100,
            message=f"Comparison finished in {progress.elapsed_seconds} seconds.",
            step="finalize",
            status="completed",
        )

    return results


async def process_pair(
    article_a_url: str | None,
    article_b_url: str | None,
    *,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
) -> list[ArticleResult]:
    """Process two URL articles concurrently and return both results in order."""
    return await process_pair_inputs(
        ArticleInput.from_url(article_a_url, "A"),
        ArticleInput.from_url(article_b_url, "B"),
        settings=settings,
        progress=progress,
    )
