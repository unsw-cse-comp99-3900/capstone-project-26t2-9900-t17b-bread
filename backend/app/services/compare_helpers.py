"""Shared helpers for building compare responses."""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ArticleRepository, UserSessionRepository
from app.schemas.article import ProcessedArticle
from app.schemas.compare import (
    ArticleNLPDebug,
    ChunkDebug,
    CompareResponse,
    EmbeddingDebug,
    StageError,
)
from app.schemas.progress import ProcessingSummary
from app.services.pipeline import ArticleResult
from app.services.progress import ProgressTracker

logger = logging.getLogger(__name__)


def build_nlp_debug(result: ArticleResult) -> ArticleNLPDebug:
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


def build_compare_response(
    *,
    focus,
    results: list[ArticleResult],
    progress: ProgressTracker | None = None,
    session_token: str | None = None,
) -> CompareResponse:
    articles: list[ProcessedArticle] = []
    errors: list[StageError] = []
    nlp_debug: list[ArticleNLPDebug] = []

    #sprint 2
    comparison = None

    if len(results) == 2 and all(r.ok for r in results):
        article_a = next(r for r in results if r.article_ref == "A")
        article_b = next(r for r in results if r.article_ref == "B")

        from app.services.comparison_service import compare_articles
        comparison = compare_articles(article_a, article_b)


    for result in results:
        if result.ok and result.article is not None:
            articles.append(result.article)
            nlp_debug.append(build_nlp_debug(result))
        elif result.error is not None:
            errors.append(StageError(**result.error.to_dict()))

    processing = None
    if progress is not None:
        processing = ProcessingSummary(**progress.to_summary())

    return CompareResponse(
        focus=focus,
        articles=articles,
        errors=errors,
        processing=processing,
        nlp_debug=nlp_debug,
        comparison=comparison,
        session_token=session_token,
    )


async def persist_compare_session(
    session: AsyncSession,
    articles: list[ProcessedArticle],
    article_a_ref: str,
    article_b_ref: str,
) -> str | None:
    try:
        article_repo = ArticleRepository(session)
        for article in articles:
            await article_repo.upsert_processed(article)

        session_token = uuid4().hex
        await UserSessionRepository(session).record(
            session_token,
            article_a_ref,
            article_b_ref,
        )
        await session.commit()
        return session_token
    except Exception:  # noqa: BLE001 - persistence must never break the response
        await session.rollback()
        logger.exception("Database persistence failed; returning result without it.")
        return None
