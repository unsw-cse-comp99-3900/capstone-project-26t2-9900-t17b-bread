# backend/app/services/hybrid_scoring_service.py

from __future__ import annotations

from typing import Any

from app.services.focus_scaling_service import get_focus_scaling_service


DEFAULT_SEMANTIC_WEIGHT = 0.65
DEFAULT_LEXICAL_WEIGHT = 0.35


def _normalise_focus(focus: Any) -> str:
    """
    Convert frontend focus value or enum into a plain lowercase string.
    """
    if focus is None:
        return "general"

    if hasattr(focus, "value"):
        focus = focus.value

    return str(focus).strip().lower() or "general"


class HybridScoringService:
    """
    Combine SBERT cosine scores and BM25 lexical scores.

    This service produces final pair-level hybrid scores.
    It does not perform cross mapping, final alignment, relationship
    classification, or explanation generation.
    """

    def combine_pair_scores(
        self,
        *,
        cosine_pair_scores: list[dict[str, Any]],
        bm25_pair_scores: list[dict[str, Any]],
        chunk_embeddings_a: list[dict[str, Any]],
        chunk_embeddings_b: list[dict[str, Any]],
        focus: Any = "general",
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Combine cosine and BM25 pair scores.

        cosine_score represents semantic similarity.
        bm25_score represents lexical overlap.
        base_hybrid_score combines both scores.
        hybrid_score applies the user focus scaling layer.
        """

        if not cosine_pair_scores:
            return []

        focus_value = _normalise_focus(focus)

        semantic_weight, lexical_weight = self._normalise_weights(
            semantic_weight,
            lexical_weight,
        )

        bm25_lookup = self._build_bm25_lookup(bm25_pair_scores)

        focus_scaling_service = get_focus_scaling_service()
        focus_relevance_lookup = focus_scaling_service.compute_focus_relevance_lookup(
            chunk_embeddings_a,
            chunk_embeddings_b,
            focus=focus_value,
        )

        hybrid_pair_scores: list[dict[str, Any]] = []

        for cosine_item in cosine_pair_scores:
            a_chunk_id = cosine_item.get("a_chunk_id")
            b_chunk_id = cosine_item.get("b_chunk_id")

            if not a_chunk_id or not b_chunk_id:
                continue

            key = (a_chunk_id, b_chunk_id)
            bm25_item = bm25_lookup.get(key, {})

            cosine_score = self._safe_float(
                cosine_item.get("cosine_score"),
                default=0.0,
            )

            bm25_score = self._safe_float(
                bm25_item.get("bm25_score"),
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

            scaling_result = focus_scaling_service.apply_focus_scaling(
                base_score=base_hybrid_score,
                a_chunk_id=a_chunk_id,
                b_chunk_id=b_chunk_id,
                focus=focus_value,
                focus_relevance_lookup=focus_relevance_lookup,
            )

            hybrid_score = self._safe_float(
                scaling_result.get("final_score"),
                default=base_hybrid_score,
            )

            if min_score is not None and hybrid_score < min_score:
                continue

            hybrid_pair_scores.append(
                {
                    "a_chunk_id": a_chunk_id,
                    "b_chunk_id": b_chunk_id,
                    "a_chunk_index": cosine_item.get("a_chunk_index"),
                    "b_chunk_index": cosine_item.get("b_chunk_index"),
                    "a_paragraph_index": cosine_item.get("a_paragraph_index"),
                    "b_paragraph_index": cosine_item.get("b_paragraph_index"),
                    "a_article_ref": cosine_item.get("a_article_ref"),
                    "b_article_ref": cosine_item.get("b_article_ref"),

                    "cosine_score": cosine_score,
                    "bm25_score": bm25_score,
                    "bm25_raw_score": bm25_raw_score,

                    "semantic_weight": semantic_weight,
                    "lexical_weight": lexical_weight,
                    "base_hybrid_score": base_hybrid_score,

                    "focus": scaling_result.get("focus", focus_value),
                    "a_focus_relevance": scaling_result.get("a_focus_relevance", 0.0),
                    "b_focus_relevance": scaling_result.get("b_focus_relevance", 0.0),
                    "pair_focus_relevance": scaling_result.get(
                        "pair_focus_relevance",
                        0.0,
                    ),
                    "scale_factor": scaling_result.get("scale_factor", 1.0),

                    "hybrid_score": hybrid_score,
                }
            )

        hybrid_pair_scores.sort(
            key=lambda item: item["hybrid_score"],
            reverse=True,
        )

        return hybrid_pair_scores

    def _build_bm25_lookup(
        self,
        bm25_pair_scores: list[dict[str, Any]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """
        Build lookup table by pair id.

        Key:
            (a_chunk_id, b_chunk_id)
        """
        lookup: dict[tuple[str, str], dict[str, Any]] = {}

        for item in bm25_pair_scores:
            a_chunk_id = item.get("a_chunk_id")
            b_chunk_id = item.get("b_chunk_id")

            if not a_chunk_id or not b_chunk_id:
                continue

            lookup[(a_chunk_id, b_chunk_id)] = item

        return lookup

    def _normalise_weights(
        self,
        semantic_weight: float,
        lexical_weight: float,
    ) -> tuple[float, float]:
        """
        Make sure semantic and lexical weights sum to 1.
        """
        total = semantic_weight + lexical_weight

        if total <= 0:
            raise ValueError(
                "semantic_weight + lexical_weight must be greater than 0."
            )

        return semantic_weight / total, lexical_weight / total

    def _safe_float(
        self,
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        """
        Convert value to float safely.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


_hybrid_scoring_service = HybridScoringService()


def get_hybrid_scoring_service() -> HybridScoringService:
    return _hybrid_scoring_service