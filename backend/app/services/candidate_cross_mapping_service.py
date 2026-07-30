# backend/app/services/candidate_cross_mapping_service.py

from __future__ import annotations

import math
from typing import Any


# Ordinary candidate threshold based on the unscaled content score.
DEFAULT_MIN_BASE_HYBRID_SCORE = 0.38

# Looser base-score floor for pairs with a strong semantic or lexical signal.
# These pairs are retained for NLI instead of being rejected before
# contradiction analysis.
DEFAULT_OVERRIDE_MIN_BASE_HYBRID_SCORE = 0.30

# Reject ordinary candidates when both semantic and lexical evidence are weak.
DEFAULT_MIN_COSINE_SCORE = 0.30
DEFAULT_MIN_BM25_SCORE = 0.12

# A strong signal from either channel can retain a lower-base-score pair as a
# potential contradiction candidate.
DEFAULT_STRONG_COSINE_OVERRIDE = 0.58
DEFAULT_STRONG_BM25_OVERRIDE = 0.42

# Context provides only a small, content-based ranking adjustment.
DEFAULT_CONTEXT_WEIGHT = 0.04

# Only sufficiently strong neighbouring candidate pairs can provide context.
DEFAULT_MIN_CONTEXT_SUPPORT_SCORE = 0.50


class CandidateCrossMappingService:
    """
    Build high-recall candidate mappings for downstream bidirectional NLI.

    Input comes from HybridScoringService and contains only:

        - cosine_score;
        - bm25_score;
        - base_hybrid_score;
        - pair identifiers and article-position metadata.

    This service:

        1. applies a relatively permissive relevance filter;
        2. retains lower-base-score pairs when semantic or lexical evidence is
           strong enough to justify contradiction analysis;
        3. computes contextual support from neighbouring base_hybrid_score
           values;
        4. computes mapping_score from base_hybrid_score and context_boost;
        5. returns every eligible candidate for NLI.

    This service intentionally does not:

        - calculate or use focus/factor relevance;
        - calculate or use a focus-adjusted score;
        - preserve focus/factor-scaling metadata;
        - apply the final mapping_score threshold;
        - perform final one-to-one selection;
        - classify relationships;
        - confirm that a candidate is contradictory.

    Every candidate decision is based only on content evidence generated before
    factor scaling.
    """

    def build_candidate_mappings(
        self,
        base_pair_scores: list[dict[str, Any]],
        *,
        min_base_hybrid_score: float = (
            DEFAULT_MIN_BASE_HYBRID_SCORE
        ),
        override_min_base_hybrid_score: float = (
            DEFAULT_OVERRIDE_MIN_BASE_HYBRID_SCORE
        ),
        min_cosine_score: float = DEFAULT_MIN_COSINE_SCORE,
        min_bm25_score: float = DEFAULT_MIN_BM25_SCORE,
        strong_cosine_override: float = (
            DEFAULT_STRONG_COSINE_OVERRIDE
        ),
        strong_bm25_override: float = (
            DEFAULT_STRONG_BM25_OVERRIDE
        ),
        context_weight: float = DEFAULT_CONTEXT_WEIGHT,
        min_context_support_score: float = (
            DEFAULT_MIN_CONTEXT_SUPPORT_SCORE
        ),
    ) -> list[dict[str, Any]]:
        """
        Build candidate cross-article mappings for downstream NLI.

        Ordinary candidate rule:

            base_hybrid_score >= min_base_hybrid_score
            and
            (
                cosine_score >= min_cosine_score
                or bm25_score >= min_bm25_score
            )

        Strong-signal candidate rule:

            base_hybrid_score >= override_min_base_hybrid_score
            and
            (
                cosine_score >= strong_cosine_override
                or bm25_score >= strong_bm25_override
            )

        A pair is retained when either rule passes.

        No final mapping_score threshold and no final one-to-one selection are
        applied here.
        """

        if not base_pair_scores:
            return []

        self._validate_parameters(
            min_base_hybrid_score=min_base_hybrid_score,
            override_min_base_hybrid_score=(
                override_min_base_hybrid_score
            ),
            min_cosine_score=min_cosine_score,
            min_bm25_score=min_bm25_score,
            strong_cosine_override=strong_cosine_override,
            strong_bm25_override=strong_bm25_override,
            context_weight=context_weight,
            min_context_support_score=min_context_support_score,
        )

        eligible_pairs = self._filter_candidate_pairs(
            base_pair_scores,
            min_base_hybrid_score=min_base_hybrid_score,
            override_min_base_hybrid_score=(
                override_min_base_hybrid_score
            ),
            min_cosine_score=min_cosine_score,
            min_bm25_score=min_bm25_score,
            strong_cosine_override=strong_cosine_override,
            strong_bm25_override=strong_bm25_override,
        )

        if not eligible_pairs:
            return []

        candidate_mappings = self._apply_contextual_consistency(
            eligible_pairs,
            context_weight=context_weight,
            min_context_support_score=min_context_support_score,
        )

        # Deterministic ordering for inspection and NLI batching only.
        # This does not remove candidates or impose a final mapping decision.
        candidate_mappings.sort(
            key=lambda item: (
                -self._safe_float(
                    item.get("mapping_score")
                ),
                self._safe_int(
                    item.get("a_chunk_index")
                ),
                self._safe_int(
                    item.get("b_chunk_index")
                ),
            )
        )

        return candidate_mappings

    def _filter_candidate_pairs(
        self,
        base_pair_scores: list[dict[str, Any]],
        *,
        min_base_hybrid_score: float,
        override_min_base_hybrid_score: float,
        min_cosine_score: float,
        min_bm25_score: float,
        strong_cosine_override: float,
        strong_bm25_override: float,
    ) -> list[dict[str, Any]]:
        """
        Apply permissive content-based candidate rules before context scoring.

        The strong-signal rule marks a pair as worth sending to NLI. It does
        not mean that the pair is already confirmed as contradictory.
        """

        filtered_pairs: list[dict[str, Any]] = []

        for pair in base_pair_scores:
            a_chunk_id = pair.get("a_chunk_id")
            b_chunk_id = pair.get("b_chunk_id")

            if not a_chunk_id or not b_chunk_id:
                continue

            base_hybrid_score = self._get_base_hybrid_score(
                pair
            )
            cosine_score = self._get_bounded_score(
                pair,
                "cosine_score",
            )
            bm25_score = self._get_bounded_score(
                pair,
                "bm25_score",
            )

            ordinary_candidate = (
                base_hybrid_score >= min_base_hybrid_score
                and (
                    cosine_score >= min_cosine_score
                    or bm25_score >= min_bm25_score
                )
            )

            strong_signal_candidate = (
                base_hybrid_score
                >= override_min_base_hybrid_score
                and (
                    cosine_score >= strong_cosine_override
                    or bm25_score >= strong_bm25_override
                )
            )

            if not ordinary_candidate and not strong_signal_candidate:
                continue

            # Construct the candidate explicitly instead of copying the whole
            # upstream dictionary. This guarantees that factor/focus-scaling
            # fields cannot leak into the candidate-mapping stage.
            candidate: dict[str, Any] = {
                "a_chunk_id": a_chunk_id,
                "b_chunk_id": b_chunk_id,

                "a_chunk_index": pair.get(
                    "a_chunk_index"
                ),
                "b_chunk_index": pair.get(
                    "b_chunk_index"
                ),

                "a_paragraph_index": pair.get(
                    "a_paragraph_index"
                ),
                "b_paragraph_index": pair.get(
                    "b_paragraph_index"
                ),

                "a_article_ref": pair.get(
                    "a_article_ref"
                ),
                "b_article_ref": pair.get(
                    "b_article_ref"
                ),

                "cosine_score": cosine_score,
                "bm25_score": bm25_score,
                "bm25_raw_score": self._safe_float(
                    pair.get("bm25_raw_score")
                ),

                "semantic_weight": self._safe_float(
                    pair.get("semantic_weight")
                ),
                "lexical_weight": self._safe_float(
                    pair.get("lexical_weight")
                ),

                "base_hybrid_score": (
                    base_hybrid_score
                ),

                # Candidate provenance used by FinalCrossMappingService.
                "ordinary_candidate": (
                    ordinary_candidate
                ),
                "strong_signal_candidate": (
                    strong_signal_candidate
                ),
                "potential_contradiction_candidate": (
                    strong_signal_candidate
                ),
                "candidate_reason": self._candidate_reason(
                    ordinary_candidate=ordinary_candidate,
                    strong_signal_candidate=(
                        strong_signal_candidate
                    ),
                ),
            }

            filtered_pairs.append(candidate)

        return filtered_pairs

    def _apply_contextual_consistency(
        self,
        candidate_pairs: list[dict[str, Any]],
        *,
        context_weight: float,
        min_context_support_score: float,
    ) -> list[dict[str, Any]]:
        """
        Compute content-based context support and mapping_score.

        Example target pair:

            A-p3 -> B-p5

        Potential supporting neighbours:

            A-p2 -> B-p4
            A-p4 -> B-p6

        Only neighbouring candidate pairs whose base_hybrid_score reaches
        min_context_support_score can provide support.

        Formula:

            context_boost = (
                context_weight
                * context_support
                * (1 - base_hybrid_score)
            )

            mapping_score = base_hybrid_score + context_boost

        No final mapping_score threshold is applied in this service.
        """

        pair_lookup: dict[
            tuple[int, int],
            dict[str, Any],
        ] = {}

        for pair in candidate_pairs:
            a_order = self._get_order(pair, "a")
            b_order = self._get_order(pair, "b")

            if a_order is None or b_order is None:
                continue

            pair_lookup[(a_order, b_order)] = pair

        enhanced_pairs: list[dict[str, Any]] = []

        for pair in candidate_pairs:
            base_hybrid_score = self._get_base_hybrid_score(
                pair
            )
            a_order = self._get_order(pair, "a")
            b_order = self._get_order(pair, "b")

            neighbour_scores: list[float] = []

            if a_order is not None and b_order is not None:
                previous_pair = pair_lookup.get(
                    (a_order - 1, b_order - 1)
                )
                next_pair = pair_lookup.get(
                    (a_order + 1, b_order + 1)
                )

                self._append_context_score(
                    neighbour_scores,
                    previous_pair,
                    min_context_support_score=(
                        min_context_support_score
                    ),
                )
                self._append_context_score(
                    neighbour_scores,
                    next_pair,
                    min_context_support_score=(
                        min_context_support_score
                    ),
                )

            context_support = 0.0

            if neighbour_scores:
                context_support = (
                    sum(neighbour_scores)
                    / len(neighbour_scores)
                )

            context_boost = (
                context_weight
                * context_support
                * max(
                    0.0,
                    1.0 - base_hybrid_score,
                )
            )

            mapping_score = self._clamp(
                base_hybrid_score
                + context_boost
            )

            enhanced_pair = dict(pair)
            enhanced_pair["context_support"] = (
                context_support
            )
            enhanced_pair["context_boost"] = (
                context_boost
            )
            enhanced_pair["mapping_score"] = (
                mapping_score
            )

            enhanced_pairs.append(enhanced_pair)

        return enhanced_pairs

    def _append_context_score(
        self,
        neighbour_scores: list[float],
        neighbour_pair: dict[str, Any] | None,
        *,
        min_context_support_score: float,
    ) -> None:
        """
        Add a neighbouring pair's base score when it is strong enough.
        """

        if neighbour_pair is None:
            return

        neighbour_base_hybrid_score = (
            self._get_base_hybrid_score(
                neighbour_pair
            )
        )

        if (
            neighbour_base_hybrid_score
            >= min_context_support_score
        ):
            neighbour_scores.append(
                neighbour_base_hybrid_score
            )

    def _candidate_reason(
        self,
        *,
        ordinary_candidate: bool,
        strong_signal_candidate: bool,
    ) -> str:
        if ordinary_candidate and strong_signal_candidate:
            return "ordinary_and_strong_signal"

        if ordinary_candidate:
            return "ordinary"

        return "strong_signal_override"

    def _get_base_hybrid_score(
        self,
        pair: dict[str, Any],
    ) -> float:
        """
        Return the required unscaled base_hybrid_score.

        This method never falls back to hybrid_score or any factor-adjusted
        score.
        """

        return self._get_bounded_score(
            pair,
            "base_hybrid_score",
        )

    def _get_bounded_score(
        self,
        pair: dict[str, Any],
        field_name: str,
    ) -> float:
        """
        Return a required finite score in the inclusive range [0, 1].
        """

        if field_name not in pair:
            raise ValueError(
                "CandidateCrossMappingService requires "
                f"{field_name} for every pair."
            )

        try:
            value = float(pair[field_name])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be numeric."
            ) from exc

        if not math.isfinite(value):
            raise ValueError(
                f"{field_name} must be finite."
            )

        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{field_name} must be between 0.0 and 1.0."
            )

        return value

    def _get_order(
        self,
        pair: dict[str, Any],
        side: str,
    ) -> int | None:
        """
        Get paragraph or chunk order for contextual proximity.

        Paragraph order is preferred, with chunk order used as a fallback.
        """

        if side not in {"a", "b"}:
            raise ValueError(
                'side must be either "a" or "b".'
            )

        paragraph_key = f"{side}_paragraph_index"
        chunk_key = f"{side}_chunk_index"

        for key in (paragraph_key, chunk_key):
            value = pair.get(key)

            if value is None:
                continue

            try:
                return int(value)
            except (TypeError, ValueError):
                continue

        return None

    def _validate_parameters(
        self,
        *,
        min_base_hybrid_score: float,
        override_min_base_hybrid_score: float,
        min_cosine_score: float,
        min_bm25_score: float,
        strong_cosine_override: float,
        strong_bm25_override: float,
        context_weight: float,
        min_context_support_score: float,
    ) -> None:
        bounded_values = {
            "min_base_hybrid_score": (
                min_base_hybrid_score
            ),
            "override_min_base_hybrid_score": (
                override_min_base_hybrid_score
            ),
            "min_cosine_score": min_cosine_score,
            "min_bm25_score": min_bm25_score,
            "strong_cosine_override": (
                strong_cosine_override
            ),
            "strong_bm25_override": (
                strong_bm25_override
            ),
            "context_weight": context_weight,
            "min_context_support_score": (
                min_context_support_score
            ),
        }

        for name, value in bounded_values.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be between 0.0 and 1.0."
                )

        if (
            override_min_base_hybrid_score
            > min_base_hybrid_score
        ):
            raise ValueError(
                "override_min_base_hybrid_score must be less "
                "than or equal to min_base_hybrid_score."
            )

        if (
            strong_cosine_override
            < min_cosine_score
        ):
            raise ValueError(
                "strong_cosine_override must be greater "
                "than or equal to min_cosine_score."
            )

        if (
            strong_bm25_override
            < min_bm25_score
        ):
            raise ValueError(
                "strong_bm25_override must be greater "
                "than or equal to min_bm25_score."
            )

    def _safe_float(
        self,
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
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
            min(
                maximum,
                value,
            ),
        )


_candidate_cross_mapping_service = (
    CandidateCrossMappingService()
)


def get_candidate_cross_mapping_service(
) -> CandidateCrossMappingService:
    return _candidate_cross_mapping_service