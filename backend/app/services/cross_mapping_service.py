# backend/app/services/cross_mapping_service.py

from __future__ import annotations

from typing import Any


# The original hybrid score must reach this threshold before context is applied.
DEFAULT_MIN_HYBRID_SCORE = 0.38

# Final threshold after contextual consistency adjustment.
DEFAULT_MIN_MAPPING_SCORE = 0.42

# Context should only provide a small ranking adjustment.
DEFAULT_CONTEXT_WEIGHT = 0.04

# Only sufficiently strong neighbouring pairs can provide context support.
DEFAULT_MIN_CONTEXT_SUPPORT_SCORE = 0.50

# Reject a pair when both semantic and lexical signals are weak.
DEFAULT_MIN_COSINE_SCORE = 0.30
DEFAULT_MIN_BM25_SCORE = 0.12

# A strong signal from either channel may keep a pair even when the hybrid
# score is slightly below the ordinary hybrid threshold. This is important
# for contradictory pairs, which often retain lexical overlap but receive a
# lower cosine score because their predicates point in opposite directions.
DEFAULT_STRONG_COSINE_OVERRIDE = 0.58
DEFAULT_STRONG_BM25_OVERRIDE = 0.42
DEFAULT_OVERRIDE_MIN_HYBRID_SCORE = 0.30


class CrossMappingService:
    """
    Select final cross-article mappings from hybrid pair scores.

    This service:
    1. Filters clearly weak candidate pairs.
    2. Applies a small contextual consistency adjustment.
    3. Selects final mappings greedily by mapping_score.

    It does not classify relationships as aligned, partially aligned,
    divergent, or unrelated.
    """

    def build_cross_mappings(
        self,
        hybrid_pair_scores: list[dict[str, Any]],
        *,
        min_hybrid_score: float = DEFAULT_MIN_HYBRID_SCORE,
        min_score: float = DEFAULT_MIN_MAPPING_SCORE,
        context_weight: float = DEFAULT_CONTEXT_WEIGHT,
        min_context_support_score: float = DEFAULT_MIN_CONTEXT_SUPPORT_SCORE,
        min_cosine_score: float = DEFAULT_MIN_COSINE_SCORE,
        min_bm25_score: float = DEFAULT_MIN_BM25_SCORE,
        strong_cosine_override: float = DEFAULT_STRONG_COSINE_OVERRIDE,
        strong_bm25_override: float = DEFAULT_STRONG_BM25_OVERRIDE,
        override_min_hybrid_score: float = DEFAULT_OVERRIDE_MIN_HYBRID_SCORE,
        allow_many_to_one: bool = False,
        max_mappings: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build final mappings between Article A chunks and Article B chunks.

        Steps:
        1. Filter pairs whose original hybrid score is too low.
        2. Filter pairs whose semantic and lexical evidence are both weak.
        3. Apply a small contextual consistency adjustment.
        4. Filter pairs by final mapping_score.
        5. Select mappings greedily.

        By default, each A chunk and each B chunk can appear at most once.
        """

        if not hybrid_pair_scores:
            return []

        self._validate_parameters(
            min_hybrid_score=min_hybrid_score,
            min_score=min_score,
            context_weight=context_weight,
            min_context_support_score=min_context_support_score,
            min_cosine_score=min_cosine_score,
            min_bm25_score=min_bm25_score,
            strong_cosine_override=strong_cosine_override,
            strong_bm25_override=strong_bm25_override,
            override_min_hybrid_score=override_min_hybrid_score,
        )

        # First-stage filtering:
        # context is not allowed to rescue clearly weak pairs.
        eligible_pairs = self._filter_candidate_pairs(
            hybrid_pair_scores,
            min_hybrid_score=min_hybrid_score,
            min_cosine_score=min_cosine_score,
            min_bm25_score=min_bm25_score,
            strong_cosine_override=strong_cosine_override,
            strong_bm25_override=strong_bm25_override,
            override_min_hybrid_score=override_min_hybrid_score,
        )

        if not eligible_pairs:
            return []

        enhanced_pairs = self._apply_contextual_consistency(
            eligible_pairs,
            context_weight=context_weight,
            min_context_support_score=min_context_support_score,
        )

        ranked_pairs = sorted(
            enhanced_pairs,
            key=lambda item: self._safe_float(item.get("mapping_score")),
            reverse=True,
        )

        mappings: list[dict[str, Any]] = []
        used_a: set[str] = set()
        used_b: set[str] = set()

        for pair in ranked_pairs:
            mapping_score = self._safe_float(pair.get("mapping_score"))
            hybrid_score = self._safe_float(pair.get("hybrid_score"))

            # The candidate has already passed either the ordinary gate or
            # the strong single-signal override. Do not re-apply the stricter
            # original hybrid gate here, otherwise contradiction candidates
            # rescued by lexical or semantic evidence would be removed again.
            if mapping_score < min_score:
                continue

            a_chunk_id = pair.get("a_chunk_id")
            b_chunk_id = pair.get("b_chunk_id")

            if not a_chunk_id or not b_chunk_id:
                continue

            if a_chunk_id in used_a:
                continue

            if not allow_many_to_one and b_chunk_id in used_b:
                continue

            mappings.append(
                {
                    "a_chunk_id": a_chunk_id,
                    "b_chunk_id": b_chunk_id,
                    "a_chunk_index": pair.get("a_chunk_index"),
                    "b_chunk_index": pair.get("b_chunk_index"),
                    "a_paragraph_index": pair.get("a_paragraph_index"),
                    "b_paragraph_index": pair.get("b_paragraph_index"),
                    "a_article_ref": pair.get("a_article_ref"),
                    "b_article_ref": pair.get("b_article_ref"),

                    "cosine_score": self._safe_float(
                        pair.get("cosine_score")
                    ),
                    "bm25_score": self._safe_float(
                        pair.get("bm25_score")
                    ),
                    "bm25_raw_score": self._safe_float(
                        pair.get("bm25_raw_score")
                    ),
                    "base_hybrid_score": self._safe_float(
                        pair.get("base_hybrid_score")
                    ),
                    "hybrid_score": hybrid_score,

                    "focus": pair.get("focus", "general"),
                    "pair_focus_relevance": self._safe_float(
                        pair.get("pair_focus_relevance")
                    ),
                    "scale_factor": self._safe_float(
                        pair.get("scale_factor"),
                        default=1.0,
                    ),

                    "context_support": self._safe_float(
                        pair.get("context_support")
                    ),
                    "mapping_score": mapping_score,
                }
            )

            used_a.add(a_chunk_id)
            used_b.add(b_chunk_id)

            if max_mappings is not None and len(mappings) >= max_mappings:
                break

        # Restore article order for frontend display.
        mappings.sort(
            key=lambda item: (
                self._safe_int(item.get("a_chunk_index")),
                self._safe_int(item.get("b_chunk_index")),
            )
        )

        return mappings

    def _filter_candidate_pairs(
        self,
        hybrid_pair_scores: list[dict[str, Any]],
        *,
        min_hybrid_score: float,
        min_cosine_score: float,
        min_bm25_score: float,
        strong_cosine_override: float,
        strong_bm25_override: float,
        override_min_hybrid_score: float,
    ) -> list[dict[str, Any]]:
        """
        Remove clearly weak candidate pairs before applying context.

        A pair is removed when:
        1. hybrid_score is below min_hybrid_score; or
        2. both cosine_score and bm25_score are weak.

        A strong semantic signal or a strong lexical signal can therefore
        keep a pair eligible, but the hybrid score must still pass the
        overall relevance threshold.
        """

        filtered_pairs: list[dict[str, Any]] = []

        for pair in hybrid_pair_scores:
            hybrid_score = self._safe_float(pair.get("hybrid_score"))
            cosine_score = self._safe_float(pair.get("cosine_score"))
            bm25_score = self._safe_float(pair.get("bm25_score"))

            ordinary_candidate = (
                hybrid_score >= min_hybrid_score
                and (
                    cosine_score >= min_cosine_score
                    or bm25_score >= min_bm25_score
                )
            )

            strong_signal_override = (
                hybrid_score >= override_min_hybrid_score
                and (
                    cosine_score >= strong_cosine_override
                    or bm25_score >= strong_bm25_override
                )
            )

            if not (
                ordinary_candidate
                or strong_signal_override
            ):
                continue

            filtered_pairs.append(pair)

        return filtered_pairs

    def _apply_contextual_consistency(
        self,
        hybrid_pair_scores: list[dict[str, Any]],
        *,
        context_weight: float,
        min_context_support_score: float,
    ) -> list[dict[str, Any]]:
        """
        Apply a small contextual consistency boost.

        Example:
            A-p3 -> B-p5

        This pair may receive support from:
            A-p2 -> B-p4
            A-p4 -> B-p6

        Only neighbouring pairs whose hybrid scores reach
        min_context_support_score are allowed to provide support.

        Context is a small ranking adjustment. It must not replace the
        pair's own semantic and lexical evidence.
        """

        pair_lookup: dict[tuple[int, int], dict[str, Any]] = {}

        for pair in hybrid_pair_scores:
            a_order = self._get_order(pair, "a")
            b_order = self._get_order(pair, "b")

            if a_order is None or b_order is None:
                continue

            pair_lookup[(a_order, b_order)] = pair

        enhanced_pairs: list[dict[str, Any]] = []

        for pair in hybrid_pair_scores:
            hybrid_score = self._safe_float(pair.get("hybrid_score"))
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
                    min_context_support_score=min_context_support_score,
                )

                self._append_context_score(
                    neighbour_scores,
                    next_pair,
                    min_context_support_score=min_context_support_score,
                )

            context_support = 0.0

            if neighbour_scores:
                context_support = (
                    sum(neighbour_scores) / len(neighbour_scores)
                )

            # The (1 - hybrid_score) term prevents already-high scores
            # from receiving an excessive boost.
            context_boost = (
                context_weight
                * context_support
                * max(0.0, 1.0 - hybrid_score)
            )

            mapping_score = min(
                max(hybrid_score + context_boost, 0.0),
                1.0,
            )

            enhanced_pair = dict(pair)
            enhanced_pair["context_support"] = context_support
            enhanced_pair["context_boost"] = context_boost
            enhanced_pair["mapping_score"] = mapping_score

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
        Add a neighbouring pair's score only when it is strong enough
        to provide reliable contextual support.
        """

        if neighbour_pair is None:
            return

        neighbour_score = self._safe_float(
            neighbour_pair.get("hybrid_score")
        )

        if neighbour_score >= min_context_support_score:
            neighbour_scores.append(neighbour_score)

    def _get_order(
        self,
        pair: dict[str, Any],
        side: str,
    ) -> int | None:
        """
        Get paragraph or chunk order for contextual proximity.

        side must be "a" or "b".
        """

        if side not in {"a", "b"}:
            raise ValueError("side must be either 'a' or 'b'.")

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
        min_hybrid_score: float,
        min_score: float,
        context_weight: float,
        min_context_support_score: float,
        min_cosine_score: float,
        min_bm25_score: float,
        strong_cosine_override: float,
        strong_bm25_override: float,
        override_min_hybrid_score: float,
    ) -> None:
        """
        Validate score thresholds and weights.
        """

        bounded_values = {
            "min_hybrid_score": min_hybrid_score,
            "min_score": min_score,
            "context_weight": context_weight,
            "min_context_support_score": min_context_support_score,
            "min_cosine_score": min_cosine_score,
            "min_bm25_score": min_bm25_score,
            "strong_cosine_override": strong_cosine_override,
            "strong_bm25_override": strong_bm25_override,
            "override_min_hybrid_score": override_min_hybrid_score,
        }

        for name, value in bounded_values.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be between 0.0 and 1.0."
                )

        if min_score < min_hybrid_score:
            raise ValueError(
                "min_score should be greater than or equal to "
                "min_hybrid_score."
            )

    def _safe_float(
        self,
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

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


_cross_mapping_service = CrossMappingService()


def get_cross_mapping_service() -> CrossMappingService:
    return _cross_mapping_service