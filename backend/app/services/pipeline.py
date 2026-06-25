"""Article Processing Pipeline (PROJ-3).

Connects content retrieval, extraction, cleaning and sentence preparation into
a single callable workflow with a consistent structured output (AC 3.1 / 3.2).
Failures are surfaced as structured ``PipelineError`` objects identifying the
failing stage (AC 3.3). The whole pipeline is invoked through one backend
endpoint (AC 3.4) — see ``app.api.routes.compare``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.schemas.article import ProcessedArticle
from app.services.errors import PipelineError
from app.services.fetch_service import fetch_article
from app.services.preprocessing_service import preprocess_article


@dataclass
class ArticleResult:
    """Outcome of running the pipeline for a single article."""

    article_ref: str
    url: str | None
    article: ProcessedArticle | None = None
    error: PipelineError | None = None

    @property
    def ok(self) -> bool:
        return self.article is not None and self.error is None


async def process_article(
    raw_url: str | None,
    article_ref: str,
    *,
    settings: Settings | None = None,
) -> ArticleResult:
    """Run fetch -> extract -> clean -> sentence-prep for one article.

    Never raises: pipeline failures are captured in ``ArticleResult.error`` so
    one failing article cannot abort processing of the other.
    """
    settings = settings or get_settings()
    try:
        raw = await fetch_article(raw_url, article_ref=article_ref, settings=settings)
        processed = preprocess_article(raw, article_ref, settings=settings)
        return ArticleResult(article_ref=article_ref, url=raw.url, article=processed)
    except PipelineError as exc:
        return ArticleResult(article_ref=article_ref, url=raw_url, error=exc)


async def process_pair(
    article_a_url: str | None,
    article_b_url: str | None,
    *,
    settings: Settings | None = None,
) -> list[ArticleResult]:
    """Process two articles concurrently and return both results in order."""
    settings = settings or get_settings()
    return list(
        await asyncio.gather(
            process_article(article_a_url, "A", settings=settings),
            process_article(article_b_url, "B", settings=settings),
        )
    )
