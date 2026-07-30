# backend/app/services/hybrid_scoring_service.py

from __future__ import annotations

import math
from typing import Any


DEFAULT_SEMANTIC_WEIGHT = 0.65
DEFAULT_LEXICAL_WEIGHT = 0.35


class HybridScoringService:
    """
    Combine SBERT cosine similarity and normalized BM25 similarity.

    This service runs after:

        1. CosineSimilarityService
        2. BM25SimilarityService

    It produces only the focus-independent base_hybrid_score required by
    CandidateCrossMappingService.

    This service intentionally does not:

        - apply focus scaling;
        - calculate focus relevance;
        - create a focus-adjusted hybrid_score;
        - filter candidates by a final threshold;
        - perform cross mapping;
        - run NLI;
        - classify relationships.

    Candidate filtering and mapping decisions belong to
    CandidateCrossMappingService.
    """

    def combine_pair_scores(
        self,
        *,
        cosine_pair_scores: list[dict[str, Any]],
        bm25_pair_scores: list[dict[str, Any]],
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
    ) -> list[dict[str, Any]]:
        """
        Combine cosine and BM25 scores into base_hybrid_score.

        Formula:

            base_hybrid_score = (
                semantic_weight * cosine_score
                + lexical_weight * bm25_score
            )

        The two weights are normalized to sum to 1.

        cosine_score and bm25_score are bounded to [0, 1] before combination.
        No score threshold is applied here, because CandidateCrossMappingService
        is responsible for permissive candidate filtering.
        """

        if not cosine_pair_scores:
            return []

        semantic_weight, lexical_weight = self._normalise_weights(
            semantic_weight,
            lexical_weight,
        )

        bm25_lookup = self._build_bm25_lookup(
            bm25_pair_scores
        )

        base_pair_scores: list[dict[str, Any]] = []

        for cosine_item in cosine_pair_scores:
            a_chunk_id = cosine_item.get("a_chunk_id")
            b_chunk_id = cosine_item.get("b_chunk_id")

            if not a_chunk_id or not b_chunk_id:
                continue

            key = (
                str(a_chunk_id),
                str(b_chunk_id),
            )

            bm25_item = bm25_lookup.get(
                key,
                {},
            )

            cosine_score = self._get_bounded_score(
                cosine_item.get("cosine_score"),
                field_name="cosine_score",
                default=0.0,
            )

            bm25_score = self._get_bounded_score(
                bm25_item.get("bm25_score"),
                field_name="bm25_score",
                default=0.0,
            )

            bm25_raw_score = self._safe_float(
                bm25_item.get("bm25_raw_score"),
                default=0.0,
            )

            base_hybrid_score = (
                semantic_weight * cosine_score
                + lexical_weight * bm25_score
            )

            # Floating-point arithmetic may produce a value such as
            # 1.0000000000000002, so clamp the final score to [0, 1].
            base_hybrid_score = self._clamp(
                base_hybrid_score
            )

            base_pair_scores.append(
                {
                    "a_chunk_id": a_chunk_id,
                    "b_chunk_id": b_chunk_id,

                    "a_chunk_index": cosine_item.get(
                        "a_chunk_index"
                    ),
                    "b_chunk_index": cosine_item.get(
                        "b_chunk_index"
                    ),

                    "a_paragraph_index": cosine_item.get(
                        "a_paragraph_index"
                    ),
                    "b_paragraph_index": cosine_item.get(
                        "b_paragraph_index"
                    ),

                    "a_article_ref": cosine_item.get(
                        "a_article_ref"
                    ),
                    "b_article_ref": cosine_item.get(
                        "b_article_ref"
                    ),

                    "cosine_score": cosine_score,
                    "bm25_score": bm25_score,
                    "bm25_raw_score": bm25_raw_score,

                    "semantic_weight": semantic_weight,
                    "lexical_weight": lexical_weight,

                    # The only hybrid score produced at this stage.
                    "base_hybrid_score": base_hybrid_score,
                }
            )

        # Sorting is only for deterministic output and easier inspection.
        # CandidateCrossMappingService still performs its own candidate logic.
        base_pair_scores.sort(
            key=lambda item: (
                -item["base_hybrid_score"],
                self._safe_int(
                    item.get("a_chunk_index")
                ),
                self._safe_int(
                    item.get("b_chunk_index")
                ),
            )
        )

        return base_pair_scores

    def _build_bm25_lookup(
        self,
        bm25_pair_scores: list[dict[str, Any]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """
        Build a BM25 lookup keyed by:

            (a_chunk_id, b_chunk_id)
        """

        lookup: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        for item in bm25_pair_scores:
            a_chunk_id = item.get("a_chunk_id")
            b_chunk_id = item.get("b_chunk_id")

            if not a_chunk_id or not b_chunk_id:
                continue

            key = (
                str(a_chunk_id),
                str(b_chunk_id),
            )

            lookup[key] = item

        return lookup

    def _normalise_weights(
        self,
        semantic_weight: float,
        lexical_weight: float,
    ) -> tuple[float, float]:
        """
        Validate and normalize semantic and lexical weights.

        Both weights must be finite and non-negative, and their sum must be
        greater than zero.
        """

        semantic_weight = self._required_finite_float(
            semantic_weight,
            field_name="semantic_weight",
        )

        lexical_weight = self._required_finite_float(
            lexical_weight,
            field_name="lexical_weight",
        )

        if semantic_weight < 0.0:
            raise ValueError(
                "semantic_weight must be greater than or equal to 0."
            )

        if lexical_weight < 0.0:
            raise ValueError(
                "lexical_weight must be greater than or equal to 0."
            )

        total = (
            semantic_weight
            + lexical_weight
        )

        if total <= 0.0:
            raise ValueError(
                "semantic_weight + lexical_weight must be greater than 0."
            )

        return (
            semantic_weight / total,
            lexical_weight / total,
        )

    def _get_bounded_score(
        self,
        value: Any,
        *,
        field_name: str,
        default: float,
    ) -> float:
        """
        Convert one normalized similarity score to a finite value in [0, 1].

        Missing or non-numeric values use the supplied default. Finite values
        outside [0, 1] are clamped because CandidateCrossMappingService expects
        normalized input scores.
        """

        numeric_value = self._safe_float(
            value,
            default=default,
        )

        return self._clamp(
            numeric_value
        )

    def _required_finite_float(
        self,
        value: Any,
        *,
        field_name: str,
    ) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be numeric."
            ) from exc

        if not math.isfinite(converted):
            raise ValueError(
                f"{field_name} must be finite."
            )

        return converted

    def _safe_float(
        self,
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        """
        Convert a value to a finite float.
        """

        try:
            converted = float(value)
        except (TypeError, ValueError):
            return default

        if not math.isfinite(converted):
            return default

        return converted

    def _safe_int(
        self,
        value: Any,
        *,
        default: int = 10**9,
    ) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _clamp(
        self,
        value: float,
        *,
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> float:
        return max(
            minimum,
            min(maximum, value),
        )


_hybrid_scoring_service = HybridScoringService()


def get_hybrid_scoring_service(
) -> HybridScoringService:
    return _hybrid_scoring_service