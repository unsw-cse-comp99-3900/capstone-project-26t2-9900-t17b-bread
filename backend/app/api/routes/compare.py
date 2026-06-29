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
from app.schemas.compare import (
    ArticleNLPDebug,
    ChunkDebug,
    CompareRequest,
    CompareResponse,
    EmbeddingDebug,
    StageError,
)
from app.services.pipeline import ArticleResult, process_pair

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


def _build_nlp_debug(result: ArticleResult) -> ArticleNLPDebug:
    """Build lightweight frontend-facing debug data for chunking and embedding.

    This function intentionally does not return full embedding vectors.
    It only returns vector length, dimension and a short preview so the frontend
    can verify that paragraph chunking and SBERT embedding have run successfully.
    """
    paragraph_chunks = result.paragraph_chunks or []
    chunk_embeddings = result.chunk_embeddings or []

    chunks: list[ChunkDebug] = []
    for chunk in paragraph_chunks:
        text = str(chunk.get("text") or "")

        chunks.append(
            ChunkDebug(
                chunk_id=str(chunk.get("chunk_id") or ""),
                article_ref=str(chunk.get("article_ref") or result.article_ref),
                chunk_type=str(chunk.get("chunk_type") or "paragraph"),
                chunk_index=chunk.get("chunk_index"),
                paragraph_index=chunk.get("paragraph_index"),
                text_preview=text[:200],
                word_count=chunk.get("word_count"),
                sentence_ids=chunk.get("sentence_ids") or [],
                char_start=chunk.get("char_start"),
                char_end=chunk.get("char_end"),
            )
        )

    embeddings: list[EmbeddingDebug] = []
    for item in chunk_embeddings:
        vector = item.get("embedding") or []

        if not isinstance(vector, list):
            vector = []

        dimension = item.get("dimension")
        vector_length = len(vector)

        embeddings.append(
            EmbeddingDebug(
                chunk_id=str(item.get("chunk_id") or ""),
                article_ref=str(item.get("article_ref") or result.article_ref),
                model_name=item.get("model_name") or item.get("embedding_model"),
                dimension=dimension,
                vector_length=vector_length,
                vector_preview=vector[:5],
                ok=vector_length > 0 and dimension == vector_length,
            )
        )

    embedding_ready = (
        len(paragraph_chunks) > 0
        and len(paragraph_chunks) == len(chunk_embeddings)
        and all(item.ok for item in embeddings)
    )

    return ArticleNLPDebug(
        article_ref=result.article_ref,
        chunk_count=len(paragraph_chunks),
        embedding_count=len(chunk_embeddings),
        embedding_ready=embedding_ready,
        chunks=chunks,
        embeddings=embeddings,
    )


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
    nlp_debug: list[ArticleNLPDebug] = []

    for result in results:
        if result.ok and result.article is not None:
            articles.append(result.article)
            nlp_debug.append(_build_nlp_debug(result))
        elif result.error is not None:
            errors.append(StageError(**result.error.to_dict()))

    session_token: str | None = None
    if session is not None and articles:
        session_token = await _persist(session, articles, payload)

    return CompareResponse(
        focus=payload.focus,
        articles=articles,
        errors=errors,
        nlp_debug=nlp_debug,
        session_token=session_token,
    )