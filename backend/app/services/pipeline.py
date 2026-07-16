"""Article Processing Pipeline (PROJ-3 + Sprint 2 comparison pipeline)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.schemas.article import ProcessedArticle
from app.services.article_input import ArticleInput, resolve_raw_article
from app.services.bm25_similarity_service import get_bm25_similarity_service
from app.services.cosine_similarity_service import get_cosine_similarity_service
from app.services.cross_mapping_service import get_cross_mapping_service
from app.services.embedding_service import get_embedding_service
from app.services.errors import ErrorCode, PipelineError, PipelineStage
from app.services.hybrid_scoring_service import get_hybrid_scoring_service
from app.services.paragraph_chunking_service import build_paragraph_chunks
from app.services.preprocessing_service import preprocess_article
from app.services.progress import ProgressTracker
from app.services.relationship_classification_service import (
    get_relationship_classification_service,
)

logger = logging.getLogger(__name__)


VALID_FOCUS_VALUES = {
    "general",
    "political",
    "sentiment",
    "economic",
    "social",
}


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


@dataclass
class ComparisonPipelineResult:
    """Outcome of running the pair-level comparison pipeline."""

    focus: str
    cosine_pair_scores: list[dict[str, Any]]
    bm25_pair_scores: list[dict[str, Any]]
    hybrid_pair_scores: list[dict[str, Any]]
    cross_mappings: list[dict[str, Any]]
    relationships: list[dict[str, Any]]

    @property
    def ok(self) -> bool:
        return True

    def to_response_payload(
        self,
        *,
        include_debug: bool = True,
        debug_limit: int = 50,
    ) -> dict[str, Any]:
        """
        Convert internal comparison result into API-friendly response payload.

        The frontend mainly needs:
        - cross_mappings
        - relationships

        Debug data is useful in Sprint 2 for checking cosine/BM25/hybrid scores.
        """

        payload: dict[str, Any] = {
            "focus": self.focus,
            "summary": {
                "cosine_pair_count": len(self.cosine_pair_scores),
                "bm25_pair_count": len(self.bm25_pair_scores),
                "hybrid_pair_count": len(self.hybrid_pair_scores),
                "cross_mapping_count": len(self.cross_mappings),
                "relationship_count": len(self.relationships),
            },
            "cross_mappings": self.cross_mappings,
            "relationships": self.relationships,
        }

        if include_debug:
            payload["debug"] = {
                "top_hybrid_pair_scores": self.hybrid_pair_scores[:debug_limit],
                "top_cross_mappings": self.cross_mappings[:debug_limit],
            }

        return payload


@dataclass
class PairPipelineResult:
    """Full result for two processed articles and their comparison output."""

    articles: list[ArticleResult]
    comparison: ComparisonPipelineResult | None = None


def _normalise_focus(focus: Any) -> str:
    """Convert frontend focus enum/string into a plain lowercase string."""

    if focus is None:
        return "general"

    if hasattr(focus, "value"):
        focus = focus.value

    focus_value = str(focus).strip().lower()

    if focus_value not in VALID_FOCUS_VALUES:
        return "general"

    return focus_value


async def _run_post_fetch_pipeline(
    raw,
    article_ref: str,
    *,
    settings: Settings,
    progress: ProgressTracker | None = None,
) -> ArticleResult:
    """
    Run the single-article NLP pipeline after RawArticle is available.

    This stage only handles one article:
    RawArticle -> ProcessedArticle -> paragraph chunks -> SBERT embeddings
    """

    if progress is not None:
        await progress.emit(
            message=f"Cleaning and splitting sentences for article {article_ref}...",
            step="preprocessing",
            article_ref=article_ref,
            status="running",
        )

    processed = preprocess_article(
        raw,
        article_ref,
        settings=settings,
    )

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
            message=f"Paragraph chunks ready for article {article_ref}.",
            step="chunking",
            article_ref=article_ref,
            status="completed",
        )
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
    """Run the full single-article pipeline for one URL or uploaded document."""

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
        raw = await resolve_raw_article(
            article_input,
            settings=settings,
            progress=progress,
        )

        mid = percent_start + int((percent_end - percent_start) * 0.55)

        if progress is not None:
            await progress.emit(
                percent=mid,
                message=f"Article {article_ref} loaded. Running NLP pipeline...",
                step="pipeline",
                article_ref=article_ref,
                status="running",
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

        return ArticleResult(
            article_ref=article_ref,
            url=source,
            error=exc,
        )

    except Exception as exc:  # noqa: BLE001 - convert any unexpected failure
        # Any non-pipeline error (e.g. a missing ML dependency, model load
        # failure, or OOM) is turned into a per-article error so the other
        # article can still be processed and the stream terminates cleanly
        # instead of hanging.
        logger.exception(
            "Unexpected error while processing article %s", article_ref
        )

        wrapped = PipelineError(
            PipelineStage.EMBEDDING,
            ErrorCode.UNKNOWN,
            article_ref=article_ref,
            message=(
                f"An unexpected error occurred while processing article "
                f"{article_ref}: {exc}"
            ),
        )

        if progress is not None:
            await progress.emit(
                percent=percent_end,
                message=f"Article {article_ref} failed: {wrapped.message}",
                step="complete",
                article_ref=article_ref,
                status="failed",
            )

        source = article_input.url or (
            f"upload://{article_input.filename}" if article_input.filename else None
        )

        return ArticleResult(
            article_ref=article_ref,
            url=source,
            error=wrapped,
        )


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


async def _run_comparison_pipeline(
    article_a: ArticleResult,
    article_b: ArticleResult,
    *,
    focus: Any = "general",
    progress: ProgressTracker | None = None,
) -> ComparisonPipelineResult:
    """
    Run the pair-level comparison pipeline step by step.

    This async version emits progress after each comparison stage:
    1. cosine semantic scoring
    2. BM25 lexical scoring
    3. hybrid scoring with focus scaling
    4. cross mapping
    5. relationship classification
    """

    focus_value = _normalise_focus(focus)

    chunks_a = article_a.paragraph_chunks or []
    chunks_b = article_b.paragraph_chunks or []
    embeddings_a = article_a.chunk_embeddings or []
    embeddings_b = article_b.chunk_embeddings or []

    cosine_service = get_cosine_similarity_service()
    bm25_service = get_bm25_similarity_service()
    hybrid_service = get_hybrid_scoring_service()
    cross_mapping_service = get_cross_mapping_service()
    relationship_service = get_relationship_classification_service()

    if progress is not None:
        await progress.emit(
            percent=91,
            message="Computing cosine semantic similarity scores...",
            step="cosine_similarity",
            status="running",
        )

    cosine_pair_scores = await asyncio.to_thread(
        cosine_service.compute_pair_scores,
        embeddings_a,
        embeddings_b,
    )

    if progress is not None:
        await progress.emit(
            percent=93,
            message=f"Cosine similarity completed with {len(cosine_pair_scores)} candidate scores.",
            step="cosine_similarity",
            status="completed",
        )
        await progress.emit(
            percent=94,
            message="Computing BM25 lexical similarity scores...",
            step="bm25_scoring",
            status="running",
        )

    bm25_pair_scores = await asyncio.to_thread(
        bm25_service.compute_pair_scores,
        chunks_a,
        chunks_b,
    )

    if progress is not None:
        await progress.emit(
            percent=95,
            message=f"BM25 scoring completed with {len(bm25_pair_scores)} candidate scores.",
            step="bm25_scoring",
            status="completed",
        )
        await progress.emit(
            percent=96,
            message="Combining cosine and BM25 scores with focus scaling...",
            step="hybrid_scoring",
            status="running",
        )

    hybrid_pair_scores = await asyncio.to_thread(
        hybrid_service.combine_pair_scores,
        cosine_pair_scores=cosine_pair_scores,
        bm25_pair_scores=bm25_pair_scores,
        chunk_embeddings_a=embeddings_a,
        chunk_embeddings_b=embeddings_b,
        focus=focus_value,
    )

    if progress is not None:
        await progress.emit(
            percent=97,
            message=f"Hybrid scoring completed with {len(hybrid_pair_scores)} scored pairs.",
            step="hybrid_scoring",
            status="completed",
        )
        await progress.emit(
            percent=98,
            message="Building cross-article mappings...",
            step="cross_mapping",
            status="running",
        )

    cross_mappings = await asyncio.to_thread(
        cross_mapping_service.build_cross_mappings,
        hybrid_pair_scores,
        min_score=0.55,
    )

    if progress is not None:
        await progress.emit(
            percent=99,
            message=f"Cross mapping completed with {len(cross_mappings)} mappings.",
            step="cross_mapping",
            status="completed",
        )
        await progress.emit(
            percent=99,
            message="Classifying mapped relationship types...",
            step="relationship_classification",
            status="running",
        )

    relationships = await asyncio.to_thread(
        relationship_service.classify_mappings,
        cross_mappings,
        chunks_a=chunks_a,
        chunks_b=chunks_b,
    )

    if progress is not None:
        await progress.emit(
            percent=99,
            message=f"Relationship classification completed with {len(relationships)} results.",
            step="relationship_classification",
            status="completed",
        )

    return ComparisonPipelineResult(
        focus=focus_value,
        cosine_pair_scores=cosine_pair_scores,
        bm25_pair_scores=bm25_pair_scores,
        hybrid_pair_scores=hybrid_pair_scores,
        cross_mappings=cross_mappings,
        relationships=relationships,
    )


async def compare_pair_results(
    results: list[ArticleResult],
    *,
    focus: Any = "general",
    progress: ProgressTracker | None = None,
) -> ComparisonPipelineResult | None:
    """
    Run pair-level comparison after both ArticleResult objects are ready.

    Returns None if either article failed during the single-article pipeline.
    """

    if len(results) < 2:
        return None

    article_a, article_b = results[0], results[1]

    if not article_a.ok or not article_b.ok:
        if progress is not None:
            await progress.emit(
                percent=100,
                message="Comparison skipped because one or both articles failed.",
                step="comparison",
                status="skipped",
            )
        return None

    if progress is not None:
        await progress.emit(
            percent=90,
            message="Starting pair-level comparison pipeline...",
            step="comparison",
            status="running",
        )

    comparison = await _run_comparison_pipeline(
        article_a,
        article_b,
        focus=focus,
        progress=progress,
    )

    if progress is not None:
        await progress.emit(
            percent=100,
            message="Pair-level comparison pipeline completed.",
            step="comparison",
            status="completed",
        )

    return comparison

async def process_pair_inputs(
    article_a: ArticleInput,
    article_b: ArticleInput,
    *,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
    finalize_progress: bool = True,
) -> list[ArticleResult]:
    """
    Process two mixed URL/upload inputs concurrently.

    This function only processes the two articles.
    It does not run pair-level comparison unless called through
    process_pair_inputs_with_comparison().
    """

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
            message="Starting processing pipeline for both articles...",
            step="start",
            status="running",
        )

    results = list(await asyncio.gather(_run_a(), _run_b()))

    if progress is not None and finalize_progress:
        await progress.emit(
            percent=95,
            message="Finalizing article processing response...",
            step="finalize",
            status="running",
        )
        await progress.emit(
            percent=100,
            message=f"Article processing finished in {progress.elapsed_seconds} seconds.",
            step="finalize",
            status="completed",
        )

    return results


async def process_pair_inputs_with_comparison(
    article_a: ArticleInput,
    article_b: ArticleInput,
    *,
    focus: Any = "general",
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
) -> PairPipelineResult:
    """
    Process two mixed URL/upload inputs and then run pair-level comparison.

    This is the preferred Sprint 2 entry point.
    """

    settings = settings or get_settings()

    article_results = await process_pair_inputs(
        article_a,
        article_b,
        settings=settings,
        progress=progress,
        finalize_progress=False,
    )

    comparison = await compare_pair_results(
        article_results,
        focus=focus,
        progress=progress,
    )

    if progress is not None:
        await progress.emit(
            percent=100,
            message=f"Comparison finished in {progress.elapsed_seconds} seconds.",
            step="finalize",
            status="completed",
        )

    return PairPipelineResult(
        articles=article_results,
        comparison=comparison,
    )


async def process_pair(
    article_a_url: str | None,
    article_b_url: str | None,
    *,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
) -> list[ArticleResult]:
    """
    Backward-compatible URL-only entry point.

    This only processes articles and does not run Sprint 2 comparison.
    """

    return await process_pair_inputs(
        ArticleInput.from_url(article_a_url, "A"),
        ArticleInput.from_url(article_b_url, "B"),
        settings=settings,
        progress=progress,
    )


async def process_pair_with_comparison(
    article_a_url: str | None,
    article_b_url: str | None,
    *,
    focus: Any = "general",
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
) -> PairPipelineResult:
    """URL-only entry point with full Sprint 2 comparison."""

    return await process_pair_inputs_with_comparison(
        ArticleInput.from_url(article_a_url, "A"),
        ArticleInput.from_url(article_b_url, "B"),
        focus=focus,
        settings=settings,
        progress=progress,
    )