"""Article processing and staged cross-article comparison pipeline."""

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
from app.services.candidate_cross_mapping_service import (
    get_candidate_cross_mapping_service,
)
from app.services.embedding_service import get_embedding_service
from app.services.errors import ErrorCode, PipelineError, PipelineStage
from app.services.final_cross_mapping_service import (
    get_final_cross_mapping_service,
)
from app.services.focus_scaling_service import get_focus_scaling_service
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
    base_pair_scores: list[dict[str, Any]]
    candidate_mappings: list[dict[str, Any]]
    analysed_candidates: list[dict[str, Any]]
    final_mappings: list[dict[str, Any]]
    classified_relationships: list[dict[str, Any]]
    relationships: list[dict[str, Any]]

    @property
    def ok(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Backward-compatible aliases for callers that still use old names.
    # ------------------------------------------------------------------

    @property
    def hybrid_pair_scores(self) -> list[dict[str, Any]]:
        """
        Backward-compatible alias.

        HybridScoringService now produces only base_hybrid_score, so this
        property returns base_pair_scores.
        """

        return self.base_pair_scores

    @property
    def cross_mappings(self) -> list[dict[str, Any]]:
        """
        Backward-compatible alias for the finally accepted one-to-one mappings.
        """

        return self.final_mappings

    @property
    def analysed_mappings(self) -> list[dict[str, Any]]:
        """
        Backward-compatible alias for NLI-analysed candidate mappings.
        """

        return self.analysed_candidates

    def to_response_payload(
        self,
        *,
        include_debug: bool = True,
        debug_limit: int = 50,
    ) -> dict[str, Any]:
        """
        Convert the internal comparison result into an API response.

        The main frontend fields are:

            - final_mappings;
            - relationships.

        ``cross_mappings`` remains as a temporary compatibility alias for
        ``final_mappings``.
        """

        payload: dict[str, Any] = {
            "focus": self.focus,
            "summary": {
                "cosine_pair_count": len(
                    self.cosine_pair_scores
                ),
                "bm25_pair_count": len(
                    self.bm25_pair_scores
                ),
                "base_pair_count": len(
                    self.base_pair_scores
                ),
                "candidate_mapping_count": len(
                    self.candidate_mappings
                ),
                "nli_evaluated_count": sum(
                    1
                    for mapping in self.analysed_candidates
                    if mapping.get(
                        "nli_evaluated",
                        False,
                    )
                ),
                "final_mapping_count": len(
                    self.final_mappings
                ),
                "normal_mapping_count": sum(
                    1
                    for mapping in self.final_mappings
                    if mapping.get(
                        "normal_mapping",
                        False,
                    )
                ),
                "contradiction_rescue_count": sum(
                    1
                    for mapping in self.final_mappings
                    if mapping.get(
                        "contradiction_rescue",
                        False,
                    )
                ),
                "relationship_count": len(
                    self.relationships
                ),
                "aligned_count": sum(
                    1
                    for relationship in self.relationships
                    if relationship.get("label") == "aligned"
                ),
                "partially_aligned_count": sum(
                    1
                    for relationship in self.relationships
                    if relationship.get("label")
                    == "partially_aligned"
                ),
                "divergent_count": sum(
                    1
                    for relationship in self.relationships
                    if relationship.get("label") == "divergent"
                ),
            },

            # Canonical final output.
            "final_mappings": self.final_mappings,
            "relationships": self.relationships,

            # Temporary backward-compatible alias.
            "cross_mappings": self.final_mappings,
        }

        if include_debug:
            payload["debug"] = {
                "top_base_pair_scores": (
                    self.base_pair_scores[
                        :debug_limit
                    ]
                ),
                "top_candidate_mappings": (
                    self.candidate_mappings[
                        :debug_limit
                    ]
                ),
                "top_nli_analysed_candidates": (
                    self.analysed_candidates[
                        :debug_limit
                    ]
                ),
                "top_final_mappings": (
                    self.final_mappings[
                        :debug_limit
                    ]
                ),
                "top_classified_relationships": (
                    self.classified_relationships[
                        :debug_limit
                    ]
                ),
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
    Run the pair-level comparison pipeline.

    Current stage order:

        1. cosine semantic scoring;
        2. BM25 lexical scoring;
        3. base hybrid scoring;
        4. candidate cross mapping;
        5. bidirectional NLI;
        6. final strict one-to-one mapping;
        7. relationship classification;
        8. focus scaling and factor-relevance ranking.

    Factor scaling runs only after relationship classification. It never
    affects candidate generation, NLI eligibility, final mapping, or labels.
    """

    focus_value = _normalise_focus(focus)

    chunks_a = article_a.paragraph_chunks or []
    chunks_b = article_b.paragraph_chunks or []
    embeddings_a = article_a.chunk_embeddings or []
    embeddings_b = article_b.chunk_embeddings or []

    cosine_service = get_cosine_similarity_service()
    bm25_service = get_bm25_similarity_service()
    hybrid_service = get_hybrid_scoring_service()
    candidate_mapping_service = (
        get_candidate_cross_mapping_service()
    )
    contradiction_service = (
        get_contradiction_detection_service()
    )
    final_mapping_service = (
        get_final_cross_mapping_service()
    )
    relationship_service = (
        get_relationship_classification_service()
    )
    focus_scaling_service = (
        get_focus_scaling_service()
    )

    # ------------------------------------------------------------------
    # 1. Cosine semantic similarity
    # ------------------------------------------------------------------

    if progress is not None:
        await progress.emit(
            percent=91,
            message=(
                "Computing cosine semantic similarity scores..."
            ),
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
            percent=92,
            message=(
                "Cosine similarity completed with "
                f"{len(cosine_pair_scores)} pair scores."
            ),
            step="cosine_similarity",
            status="completed",
        )

    # ------------------------------------------------------------------
    # 2. BM25 lexical similarity
    # ------------------------------------------------------------------

    if progress is not None:
        await progress.emit(
            percent=92,
            message=(
                "Computing BM25 lexical similarity scores..."
            ),
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
            percent=93,
            message=(
                "BM25 scoring completed with "
                f"{len(bm25_pair_scores)} pair scores."
            ),
            step="bm25_scoring",
            status="completed",
        )

    # ------------------------------------------------------------------
    # 3. Base hybrid scoring
    # ------------------------------------------------------------------

    if progress is not None:
        await progress.emit(
            percent=94,
            message=(
                "Combining cosine and BM25 into "
                "base hybrid scores..."
            ),
            step="base_hybrid_scoring",
            status="running",
        )

    base_pair_scores = await asyncio.to_thread(
        hybrid_service.combine_pair_scores,
        cosine_pair_scores=cosine_pair_scores,
        bm25_pair_scores=bm25_pair_scores,
    )

    if progress is not None:
        await progress.emit(
            percent=95,
            message=(
                "Base hybrid scoring completed with "
                f"{len(base_pair_scores)} scored pairs."
            ),
            step="base_hybrid_scoring",
            status="completed",
        )

    # ------------------------------------------------------------------
    # 4. Candidate cross mapping
    # ------------------------------------------------------------------

    if progress is not None:
        await progress.emit(
            percent=95,
            message=(
                "Building high-recall candidate mappings..."
            ),
            step="candidate_cross_mapping",
            status="running",
        )

    candidate_mappings = await asyncio.to_thread(
        candidate_mapping_service.build_candidate_mappings,
        base_pair_scores,
    )

    if progress is not None:
        await progress.emit(
            percent=96,
            message=(
                "Candidate cross mapping completed with "
                f"{len(candidate_mappings)} candidates."
            ),
            step="candidate_cross_mapping",
            status="completed",
        )

    # ------------------------------------------------------------------
    # 5. Bidirectional NLI
    # ------------------------------------------------------------------

    if progress is not None:
        await progress.emit(
            percent=96,
            message=(
                "Running bidirectional contradiction and "
                "NLI analysis..."
            ),
            step="contradiction_detection",
            status="running",
        )

    analysed_candidates = await asyncio.to_thread(
        contradiction_service.analyse_mappings,
        candidate_mappings,
        chunks_a=chunks_a,
        chunks_b=chunks_b,
    )

    evaluated_count = sum(
        1
        for mapping in analysed_candidates
        if mapping.get(
            "nli_evaluated",
            False,
        )
    )

    if progress is not None:
        await progress.emit(
            percent=97,
            message=(
                "Contradiction analysis completed with "
                f"{evaluated_count} NLI-evaluated candidates."
            ),
            step="contradiction_detection",
            status="completed",
        )

    # ------------------------------------------------------------------
    # 6. Final strict one-to-one mapping
    # ------------------------------------------------------------------

    if progress is not None:
        await progress.emit(
            percent=97,
            message=(
                "Selecting final strict one-to-one mappings..."
            ),
            step="final_cross_mapping",
            status="running",
        )

    final_mappings = await asyncio.to_thread(
        final_mapping_service.build_final_mappings,
        analysed_candidates,
    )

    if progress is not None:
        await progress.emit(
            percent=98,
            message=(
                "Final cross mapping completed with "
                f"{len(final_mappings)} one-to-one mappings."
            ),
            step="final_cross_mapping",
            status="completed",
        )

    # ------------------------------------------------------------------
    # 7. Relationship classification
    # ------------------------------------------------------------------

    if progress is not None:
        await progress.emit(
            percent=98,
            message=(
                "Classifying final mapping relationship types..."
            ),
            step="relationship_classification",
            status="running",
        )

    classified_relationships = await asyncio.to_thread(
        relationship_service.classify_mappings,
        final_mappings,
        chunks_a=chunks_a,
        chunks_b=chunks_b,
    )

    if progress is not None:
        await progress.emit(
            percent=99,
            message=(
                "Relationship classification completed with "
                f"{len(classified_relationships)} results."
            ),
            step="relationship_classification",
            status="completed",
        )

    # ------------------------------------------------------------------
    # 8. Focus scaling and factor relevance ranking
    # ------------------------------------------------------------------

    if progress is not None:
        await progress.emit(
            percent=99,
            message=(
                "Applying focus relevance and display ranking..."
            ),
            step="focus_scaling",
            status="running",
        )

    relationships = await asyncio.to_thread(
        focus_scaling_service.enrich_relationships,
        classified_relationships,
        embeddings_a=embeddings_a,
        embeddings_b=embeddings_b,
        focus=focus_value,

        # General mode preserves relationship/article order. A selected
        # factor returns results ordered by factor_relevance_score.
        sort_by_factor_relevance=(
            focus_value != "general"
        ),
    )

    if progress is not None:
        await progress.emit(
            percent=99,
            message=(
                "Focus scaling completed with "
                f"{len(relationships)} ranked relationships."
            ),
            step="focus_scaling",
            status="completed",
        )

    return ComparisonPipelineResult(
        focus=focus_value,
        cosine_pair_scores=cosine_pair_scores,
        bm25_pair_scores=bm25_pair_scores,
        base_pair_scores=base_pair_scores,
        candidate_mappings=candidate_mappings,
        analysed_candidates=analysed_candidates,
        final_mappings=final_mappings,
        classified_relationships=(
            classified_relationships
        ),
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