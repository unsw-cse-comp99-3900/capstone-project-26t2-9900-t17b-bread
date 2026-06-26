"""Compare Controller (proposal p.19-20).

Single backend endpoint that drives the article-processing pipeline for a pair
of articles (PROJ-3 AC 3.4). In Sprint 1 it returns both articles processed
into comparison-ready form (sentences + structure). Sprint 2 will extend the
response with matched segments, relationship labels, explanations and a
high-level summary.

When a database is configured, successfully processed articles are persisted
to the ``articles`` table and the comparison request is recorded in
``user_sessions``. Persistence is best-effort: a database failure is logged and
never breaks the API response.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.repositories import ArticleRepository, UserSessionRepository
from app.schemas.article import ProcessedArticle
from app.schemas.compare import CompareRequest, CompareResponse, StageError
from app.services.pipeline import process_pair

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compare", tags=["compare"])


async def _persist(
    session: AsyncSession,
    articles: list[ProcessedArticle],
    payload: CompareRequest,
) -> str | None:
    """Persist articles + session row. Returns a session token, or None on failure."""
    try:
        article_repo = ArticleRepository(session)
        for article in articles:
            await article_repo.upsert_processed(article)

        session_token = uuid4().hex
        await UserSessionRepository(session).record(
            session_token, payload.article_a_url, payload.article_b_url
        )
        await session.commit()
        return session_token
    except Exception:  # noqa: BLE001 - persistence must never break the response
        await session.rollback()
        logger.exception("Database persistence failed; returning result without it.")
        return None


@router.post("", response_model=CompareResponse, summary="Process a pair of articles")
async def compare(
    payload: CompareRequest,
    session: AsyncSession | None = Depends(get_session),
) -> CompareResponse:
    """Run the processing pipeline on both URLs and return structured output.

    Per-article failures are reported in ``errors`` (identifying the failing
    stage and article) while any successfully processed article is still
    returned, so the frontend can render partial results gracefully.
    """
    results = await process_pair(payload.article_a_url, payload.article_b_url)

    articles: list[ProcessedArticle] = []
    errors: list[StageError] = []
    for result in results:
        if result.ok and result.article is not None:
            articles.append(result.article)
        elif result.error is not None:
            errors.append(StageError(**result.error.to_dict()))

    session_token: str | None = None
    if session is not None and articles:
        session_token = await _persist(session, articles, payload)

    return CompareResponse(
        focus=payload.focus,
        articles=articles,
        errors=errors,
        session_token=session_token,
    )
