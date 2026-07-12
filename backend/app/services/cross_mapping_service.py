# backend/app/services/cross_mapping_service.py

from __future__ import annotations

from typing import Any


DEFAULT_MIN_MAPPING_SCORE = 0.55
DEFAULT_CONTEXT_WEIGHT = 0.10


class CrossMappingService:
    """
    Select final cross-article mappings from hybrid pair scores.

    This service performs final alignment/cross mapping.
    It does not compute cosine scores, BM25 scores, hybrid scores,
    relationship labels, or explanations.
    """

    def build_cross_mappings(
        self,
        hybrid_pair_scores: list[dict[str, Any]],
        *,
        min_score: float = DEFAULT_MIN_MAPPING_SCORE,
        context_weight: float = DEFAULT_CONTEXT_WEIGHT,
        allow_many_to_one: bool = False,
        max_mappings: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build final mappings between Article A chunks and Article B chunks.

        Steps:
        1. Apply optional contextual consistency adjustment.
        2. Filter weak mappings.
        3. Select mappings greedily by mapping_score.

        By default, each A chunk and each B chunk can appear at most once.
        """

        if not hybrid_pair_scores:
            return []

        enhanced_pairs = self._apply_contextual_consistency(
            hybrid_pair_scores,
            context_weight=context_weight,
        )

        ranked_pairs = sorted(
            enhanced_pairs,
            key=lambda item: item["mapping_score"],
            reverse=True,
        )

        mappings: list[dict[str, Any]] = []
        used_a: set[str] = set()
        used_b: set[str] = set()

        for pair in ranked_pairs:
            mapping_score = self._safe_float(pair.get("mapping_score"))

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

                    "cosine_score": pair.get("cosine_score", 0.0),
                    "bm25_score": pair.get("bm25_score", 0.0),
                    "bm25_raw_score": pair.get("bm25_raw_score", 0.0),
                    "base_hybrid_score": pair.get("base_hybrid_score", 0.0),
                    "hybrid_score": pair.get("hybrid_score", 0.0),

                    "focus": pair.get("focus", "general"),
                    "pair_focus_relevance": pair.get("pair_focus_relevance", 0.0),
                    "scale_factor": pair.get("scale_factor", 1.0),

                    "context_support": pair.get("context_support", 0.0),
                    "mapping_score": mapping_score,
                }
            )

            used_a.add(a_chunk_id)
            used_b.add(b_chunk_id)

            if max_mappings is not None and len(mappings) >= max_mappings:
                break

        mappings.sort(
            key=lambda item: (
                self._safe_int(item.get("a_chunk_index")),
                self._safe_int(item.get("b_chunk_index")),
            )
        )

        return mappings

    def _apply_contextual_consistency(
        self,
        hybrid_pair_scores: list[dict[str, Any]],
        *,
        context_weight: float,
    ) -> list[dict[str, Any]]:
        """
        Apply a small contextual consistency boost.

        If A-p3 maps to B-p5, and nearby pairs such as A-p2 -> B-p4
        or A-p4 -> B-p6 also have high hybrid scores, this mapping becomes
        slightly more reliable.

        This addresses contextual proximity without replacing hybrid_score.
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

            context_support = 0.0

            if a_order is not None and b_order is not None:
                neighbour_scores: list[float] = []

                previous_pair = pair_lookup.get((a_order - 1, b_order - 1))
                next_pair = pair_lookup.get((a_order + 1, b_order + 1))

                if previous_pair is not None:
                    neighbour_scores.append(
                        self._safe_float(previous_pair.get("hybrid_score"))
                    )

                if next_pair is not None:
                    neighbour_scores.append(
                        self._safe_float(next_pair.get("hybrid_score"))
                    )

                if neighbour_scores:
                    context_support = sum(neighbour_scores) / len(neighbour_scores)

            mapping_score = min(
                hybrid_score + context_weight * context_support * (1.0 - hybrid_score),
                1.0,
            )

            enhanced_pair = dict(pair)
            enhanced_pair["context_support"] = context_support
            enhanced_pair["mapping_score"] = mapping_score
            enhanced_pairs.append(enhanced_pair)

        return enhanced_pairs

    def _get_order(
        self,
        pair: dict[str, Any],
        side: str,
    ) -> int | None:
        """
        Get paragraph/chunk order for contextual proximity.

        side should be "a" or "b".
        """
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