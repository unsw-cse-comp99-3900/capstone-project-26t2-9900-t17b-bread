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
from app.services.contradiction_detection_service import (
    get_contradiction_detection_service,
)
from app.services.relationship_classification_service import (
    get_relationship_classification_service,
)
from app.services.summary_service import get_summary_service

logger = logging.getLogger(__name__)


VALID_FOCUS_VALUES = {
    "general",
    "political",
    "sentiment",
    "economic",
    "social",
}

SUMMARY_RELEVANCE_THRESHOLD = 0.60
SUMMARY_COSINE_WEIGHT = 0.70
SUMMARY_BM25_WEIGHT = 0.30


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
    analysed_mappings: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    comparison_summary: dict[str, Any]

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
                "nli_evaluated_count": sum(
                    1
                    for mapping in self.analysed_mappings
                    if mapping.get("nli_evaluated", False)
                ),
                "relationship_count": len(self.relationships),
                "aligned_count": sum(
                    1
                    for relationship in self.relationships
                    if relationship.get("label") == "aligned"
                ),
                "partially_aligned_count": sum(
                    1
                    for relationship in self.relationships
                    if relationship.get("label") == "partially_aligned"
                ),
                "divergent_count": sum(
                    1
                    for relationship in self.relationships
                    if relationship.get("label") == "divergent"
                ),
            },
            "cross_mappings": self.cross_mappings,
            "relationships": self.relationships,
            "comparison_summary": self.comparison_summary,
        }

        if include_debug:
            payload["debug"] = {
                "top_hybrid_pair_scores": self.hybrid_pair_scores[:debug_limit],
                "top_cross_mappings": self.cross_mappings[:debug_limit],
                "top_nli_analysed_mappings": self.analysed_mappings[:debug_limit],
            }

        return payload


@dataclass
class PairPipelineResult:
    """Full result for two processed articles and their comparison output."""

    articles: list[ArticleResult]
    comparison: ComparisonPipelineResult | None = None
    relevant: bool | None = None
    relevance_score: float | None = None
    cosine_relevance_score: float | None = None
    bm25_relevance_score: float | None = None
    relevance_threshold: float | None = None
    message: str | None = None


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


async def _prepare_article_for_comparison(
    result: ArticleResult,
    *,
    progress: ProgressTracker | None = None,
) -> ArticleResult:
    """
    Build paragraph chunks and embeddings only after
    the summary relevance check passes.
    """

    if result.article is None:
        return result

    article_ref = result.article_ref

    if progress is not None:
        await progress.emit(
            message=f"Building paragraph chunks for article {article_ref}...",
            step="chunking",
            article_ref=article_ref,
            status="running",
        )

    paragraph_chunks = await asyncio.to_thread(
        build_paragraph_chunks,
        result.article,
    )

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

    result.paragraph_chunks = paragraph_chunks
    result.chunk_embeddings = chunk_embeddings

    if progress is not None:
        await progress.emit(
            message=f"Embeddings ready for article {article_ref}.",
            step="embedding",
            article_ref=article_ref,
            status="completed",
        )

    return result


def _get_summary_sentences(result: ArticleResult) -> list[str]:
    """Extract clean text sentences from an article summary."""

    if result.article is None:
        return []

    summary = result.article.summary or []
    texts: list[str] = []

    for item in summary:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = item.get("text", "")
        else:
            text = getattr(item, "text", "")

        cleaned = " ".join(str(text).split()).strip()

        if cleaned:
            texts.append(cleaned)

    return texts


def _build_summary_chunks(
    result: ArticleResult,
) -> list[dict[str, Any]]:
    """Build one temporary chunk per summary sentence."""

    summary_sentences = _get_summary_sentences(result)
    chunks: list[dict[str, Any]] = []

    for index, text in enumerate(summary_sentences):
        chunks.append(
            {
                "chunk_id": f"{result.article_ref}-summary-{index}",
                "article_ref": result.article_ref,
                "chunk_type": "summary_sentence",
                "chunk_index": index,
                "paragraph_index": None,
                "text": text,
                "sentence_ids": [],
                "char_start": None,
                "char_end": None,
                "word_count": len(text.split()),
            }
        )

    return chunks


def _average_top_scores(
    pair_scores: list[dict[str, Any]],
    *,
    score_key: str,
    top_k: int = 3,
) -> float:
    """Average the strongest pair scores."""

    scores: list[float] = []

    for pair in pair_scores:
        value = pair.get(score_key)

        if value is None:
            continue

        try:
            scores.append(float(value))
        except (TypeError, ValueError):
            continue

    if not scores:
        return 0.0

    scores.sort(reverse=True)
    selected = scores[:top_k]

    return sum(selected) / len(selected)


async def _compute_summary_relevance(
    article_a: ArticleResult,
    article_b: ArticleResult,
) -> tuple[float, float, float]:
    """
    Compare extractive-summary sentences using the existing
    cosine and normalized BM25 services.

    Returns:
        relevance_score, cosine_score, bm25_score
    """

    chunks_a = _build_summary_chunks(article_a)
    chunks_b = _build_summary_chunks(article_b)

    if not chunks_a or not chunks_b:
        return 0.0, 0.0, 0.0

    embedding_service = get_embedding_service()

    embeddings_a, embeddings_b = await asyncio.gather(
        asyncio.to_thread(
            embedding_service.encode_paragraph_chunks,
            chunks_a,
        ),
        asyncio.to_thread(
            embedding_service.encode_paragraph_chunks,
            chunks_b,
        ),
    )

    cosine_service = get_cosine_similarity_service()
    bm25_service = get_bm25_similarity_service()

    cosine_pairs, bm25_pairs = await asyncio.gather(
        asyncio.to_thread(
            cosine_service.compute_pair_scores,
            embeddings_a,
            embeddings_b,
        ),
        asyncio.to_thread(
            bm25_service.compute_pair_scores,
            chunks_a,
            chunks_b,
        ),
    )

    cosine_score = _average_top_scores(
        cosine_pairs,
        score_key="cosine_score",
        top_k=3,
    )

    bm25_score = _average_top_scores(
        bm25_pairs,
        score_key="bm25_score",
        top_k=3,
    )

    cosine_score = max(0.0, min(1.0, cosine_score))
    bm25_score = max(0.0, min(1.0, bm25_score))

    relevance_score = (
        SUMMARY_COSINE_WEIGHT * cosine_score
        + SUMMARY_BM25_WEIGHT * bm25_score
    )

    return relevance_score, cosine_score, bm25_score


async def _run_post_fetch_pipeline(
    raw,
    article_ref: str,
    *,
    settings: Settings,
    progress: ProgressTracker | None = None,
    prepare_comparison: bool = True,
) -> ArticleResult:
    """
    Run the single-article NLP pipeline after RawArticle is available.

    Always performs:
    RawArticle -> ProcessedArticle -> extractive summary

    When prepare_comparison is True, also performs:
    paragraph chunks -> SBERT embeddings
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
            message=f"Generating extractive summary for article {article_ref}...",
            step="summarization",
            article_ref=article_ref,
            status="running",
        )

    summary_service = get_summary_service()

    processed.summary = await asyncio.to_thread(
        summary_service.summarize_article,
        processed,
    )

    if progress is not None:
        await progress.emit(
            message=f"Extractive summary ready for article {article_ref}.",
            step="summarization",
            article_ref=article_ref,
            status="completed",
        )

    result = ArticleResult(
        article_ref=article_ref,
        url=raw.url,
        article=processed,
    )

    if prepare_comparison:
        await _prepare_article_for_comparison(
            result,
            progress=progress,
        )

    return result


async def process_article_input(
    article_input: ArticleInput,
    *,
    settings: Settings | None = None,
    progress: ProgressTracker | None = None,
    percent_start: int = 0,
    percent_end: int = 100,
    prepare_comparison: bool = True,
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
            prepare_comparison=prepare_comparison,
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
    5. contradiction/NLI detection
    6. relationship classification
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
    contradiction_service = get_contradiction_detection_service()
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
    )

    if progress is not None:
        await progress.emit(
            percent=98,
            message=f"Cross mapping completed with {len(cross_mappings)} mappings.",
            step="cross_mapping",
            status="completed",
        )
        await progress.emit(
            percent=98,
            message="Running contradiction and NLI analysis...",
            step="contradiction_detection",
            status="running",
        )

    analysed_mappings = await asyncio.to_thread(
        contradiction_service.analyse_mappings,
        cross_mappings,
        chunks_a=chunks_a,
        chunks_b=chunks_b,
    )

    if progress is not None:
        evaluated_count = sum(
            1
            for mapping in analysed_mappings
            if mapping.get("nli_evaluated", False)
        )

        await progress.emit(
            percent=99,
            message=(
                "Contradiction analysis completed with "
                f"{evaluated_count} NLI-evaluated mappings."
            ),
            step="contradiction_detection",
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
        analysed_mappings,
        chunks_a=chunks_a,
        chunks_b=chunks_b,
    )

    summary_service = get_summary_service()

    comparison_summary = await asyncio.to_thread(
        summary_service.summarize_comparison,
        relationships,
    )

    if progress is not None:
        await progress.emit(
            percent=99,
            message=(
                "Relationship classification completed with "
                f"{len(relationships)} visible results."
            ),
            step="relationship_classification",
            status="completed",
        )

    return ComparisonPipelineResult(
        focus=focus_value,
        cosine_pair_scores=cosine_pair_scores,
        bm25_pair_scores=bm25_pair_scores,
        hybrid_pair_scores=hybrid_pair_scores,
        cross_mappings=cross_mappings,
        analysed_mappings=analysed_mappings,
        relationships=relationships,
        comparison_summary=comparison_summary,
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
    prepare_comparison: bool = True,
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
            percent_end=40,
            prepare_comparison=prepare_comparison,
        )

    async def _run_b() -> ArticleResult:
        return await process_article_input(
            article_b,
            settings=settings,
            progress=progress,
            percent_start=45,
            percent_end=80,
            prepare_comparison=prepare_comparison,
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
    Generate summaries first and check their relevance.

    The full paragraph-level comparison pipeline only runs when
    the summaries pass the relevance threshold.
    """

    settings = settings or get_settings()

    # Phase 1:
    # Resolve, preprocess, and summarize both articles.
    # Do not build original paragraph chunks or embeddings yet.
    article_results = await process_pair_inputs(
        article_a,
        article_b,
        settings=settings,
        progress=progress,
        finalize_progress=False,
        prepare_comparison=False,
    )

    # Stop when either article failed.
    if (
        len(article_results) < 2
        or not article_results[0].ok
        or not article_results[1].ok
    ):
        message = (
            "Relevance check skipped because one or both articles failed."
        )

        if progress is not None:
            await progress.emit(
                percent=100,
                message=message,
                step="summary_relevance",
                status="skipped",
            )

        return PairPipelineResult(
            articles=article_results,
            comparison=None,
            relevant=None,
            relevance_threshold=SUMMARY_RELEVANCE_THRESHOLD,
            message=message,
        )

    if progress is not None:
        await progress.emit(
            percent=82,
            message="Checking relevance between the article summaries...",
            step="summary_relevance",
            status="running",
        )

    (
        relevance_score,
        cosine_relevance_score,
        bm25_relevance_score,
    ) = await _compute_summary_relevance(
        article_results[0],
        article_results[1],
    )

    # Phase 2A:
    # Summaries are not relevant enough, so stop here.
    if relevance_score < SUMMARY_RELEVANCE_THRESHOLD:
        message = (
            "The articles are not relevant enough for detailed comparison."
        )

        if progress is not None:
            await progress.emit(
                percent=100,
                message=message,
                step="summary_relevance",
                status="completed",
            )

        return PairPipelineResult(
            articles=article_results,
            comparison=None,
            relevant=False,
            relevance_score=relevance_score,
            cosine_relevance_score=cosine_relevance_score,
            bm25_relevance_score=bm25_relevance_score,
            relevance_threshold=SUMMARY_RELEVANCE_THRESHOLD,
            message=message,
        )

    if progress is not None:
        await progress.emit(
            percent=84,
            message=(
                "The summaries passed the relevance check. "
                "Preparing detailed comparison..."
            ),
            step="summary_relevance",
            status="completed",
        )

    # Phase 2B:
    # Only now create paragraph chunks and embeddings from the full articles.
    await asyncio.gather(
        _prepare_article_for_comparison(
            article_results[0],
            progress=progress,
        ),
        _prepare_article_for_comparison(
            article_results[1],
            progress=progress,
        ),
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
        relevant=True,
        relevance_score=relevance_score,
        cosine_relevance_score=cosine_relevance_score,
        bm25_relevance_score=bm25_relevance_score,
        relevance_threshold=SUMMARY_RELEVANCE_THRESHOLD,
        message="The articles passed the summary relevance check.",
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