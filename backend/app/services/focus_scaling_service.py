from __future__ import annotations

from typing import Any

import numpy as np

from app.services.embedding_service import get_embedding_service


FOCUS_PROFILES: dict[str, str] = {
    "political": (
        "Government actions, political leaders, public policy, legislation, "
        "political power, authority, diplomacy, sanctions, conflict, state "
        "institutions, political responsibility, and official decisions."
    ),
    "sentiment": (
        "Emotional tone and human emotion, including fear, anger, grief, "
        "sympathy, blame, outrage, hope, distress, suffering, tragedy, "
        "concern, and emotional reactions."
    ),
    "economic": (
        "Economic and financial issues, including markets, prices, trade, "
        "business, employment, inflation, investment, budgets, costs, "
        "financial consequences, production, supply, and resources."
    ),
    "social": (
        "Social and community impact, including civilians, families, public "
        "life, education, healthcare, housing, inequality, social groups, "
        "human welfare, communities, and societal consequences."
    ),
}


FOCUS_MAX_BOOST: dict[str, float] = {
    "general": 0.0,
    "political": 0.15,
    "sentiment": 0.15,
    "economic": 0.15,
    "social": 0.15,
}


# Absolute cosine-similarity calibration range.
# This calibrates how strongly a chunk matches the selected focus profile.
# It is independent from CrossMappingService thresholds.
FOCUS_SIMILARITY_FLOOR = 0.25
FOCUS_SIMILARITY_CEILING = 0.55

# Cross mapping now accepts base scores from approximately 0.38 upward.
# Focus scaling should begin near that range, but should still provide no
# rescue for candidates below the cross-mapping relevance threshold.
FOCUS_GATE_START_SCORE = 0.38
FOCUS_GATE_FULL_SCORE = 0.58


class FocusScalingService:
    """
    Apply user focus preference using semantic focus relevance.

    Focus scaling is used to re-rank already relevant chunk pairs.
    It should not convert weak or unrelated pairs into valid mappings.
    """

    def __init__(self) -> None:
        self._focus_embedding_cache: dict[str, np.ndarray] = {}

    def compute_focus_relevance_lookup(
        self,
        embeddings_a: list[dict[str, Any]],
        embeddings_b: list[dict[str, Any]],
        *,
        focus: str,
    ) -> dict[str, float]:
        """
        Compute an absolute focus relevance score for each chunk.

        The score is calibrated to the fixed range [0, 1] rather than
        normalized relative to the strongest chunk in the current articles.
        """

        focus = (focus or "general").strip().lower()

        if focus == "general" or focus not in FOCUS_PROFILES:
            return {}

        focus_vector = self._get_focus_embedding(focus)

        chunk_scores: dict[str, float] = {}

        for item in embeddings_a + embeddings_b:
            chunk_id = item.get("chunk_id")
            vector = item.get("embedding")

            if not chunk_id or not isinstance(vector, list) or not vector:
                continue

            chunk_vector = np.asarray(vector, dtype=float)
            chunk_vector = self._safe_normalize_vector(chunk_vector)

            raw_similarity = float(chunk_vector @ focus_vector)

            chunk_scores[chunk_id] = self._calibrate_focus_similarity(
                raw_similarity
            )

        return chunk_scores

    def apply_focus_scaling(
        self,
        *,
        base_score: float,
        a_chunk_id: str,
        b_chunk_id: str,
        focus: str,
        focus_relevance_lookup: dict[str, float],
    ) -> dict[str, Any]:
        """
        Apply a bounded focus-based ranking boost.

        Both chunks should be relevant to the selected focus. The boost is
        also gated by the original base similarity so that weak pairs cannot
        be rescued only because one chunk matches the selected focus.
        """

        focus = (focus or "general").strip().lower()
        base_score = self._clamp(base_score)

        if focus == "general" or focus not in FOCUS_PROFILES:
            return {
                "focus": "general",
                "a_focus_relevance": 0.0,
                "b_focus_relevance": 0.0,
                "pair_focus_relevance": 0.0,
                "focus_gate": 0.0,
                "effective_boost": 0.0,
                "scale_factor": 1.0,
                "final_score": base_score,
            }

        a_relevance = self._clamp(
            focus_relevance_lookup.get(a_chunk_id, 0.0)
        )
        b_relevance = self._clamp(
            focus_relevance_lookup.get(b_chunk_id, 0.0)
        )

        # Geometric mean requires both sides to be relevant.
        bilateral_relevance = float(
            np.sqrt(a_relevance * b_relevance)
        )

        # Keep a small contribution from the stronger side.
        pair_relevance = (
            0.80 * bilateral_relevance
            + 0.20 * max(a_relevance, b_relevance)
        )

        focus_gate = self._compute_focus_gate(base_score)

        max_boost = FOCUS_MAX_BOOST.get(focus, 0.0)

        effective_boost = (
            max_boost
            * pair_relevance
            * focus_gate
        )

        scale_factor = 1.0 + effective_boost
        final_score = min(base_score * scale_factor, 1.0)

        return {
            "focus": focus,
            "a_focus_relevance": a_relevance,
            "b_focus_relevance": b_relevance,
            "bilateral_focus_relevance": bilateral_relevance,
            "pair_focus_relevance": pair_relevance,
            "focus_gate": focus_gate,
            "effective_boost": effective_boost,
            "scale_factor": scale_factor,
            "final_score": final_score,
        }

    def _get_focus_embedding(self, focus: str) -> np.ndarray:
        """
        Encode and cache the selected focus profile.
        """

        if focus in self._focus_embedding_cache:
            return self._focus_embedding_cache[focus]

        profile = FOCUS_PROFILES[focus]

        embedding_service = get_embedding_service()

        vector = embedding_service.model.encode(
            profile,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        vector = np.asarray(vector, dtype=float)
        vector = self._safe_normalize_vector(vector)

        self._focus_embedding_cache[focus] = vector

        return vector

    def _calibrate_focus_similarity(
        self,
        raw_similarity: float,
    ) -> float:
        """
        Convert absolute cosine similarity into a bounded 0-1 score.

        Values below the floor receive no focus relevance.
        Values at or above the ceiling receive full relevance.
        """

        denominator = (
            FOCUS_SIMILARITY_CEILING
            - FOCUS_SIMILARITY_FLOOR
        )

        if denominator <= 0:
            raise ValueError(
                "FOCUS_SIMILARITY_CEILING must be greater than "
                "FOCUS_SIMILARITY_FLOOR."
            )

        calibrated = (
            raw_similarity - FOCUS_SIMILARITY_FLOOR
        ) / denominator

        return self._clamp(calibrated)

    def _compute_focus_gate(
        self,
        base_score: float,
    ) -> float:
        """
        Compute how much focus scaling is allowed based on base similarity.

        Weak pairs receive no or limited boost. Strong pairs can receive the
        full focus boost.
        """

        if base_score <= FOCUS_GATE_START_SCORE:
            return 0.0

        if base_score >= FOCUS_GATE_FULL_SCORE:
            return 1.0

        return (
            base_score - FOCUS_GATE_START_SCORE
        ) / (
            FOCUS_GATE_FULL_SCORE - FOCUS_GATE_START_SCORE
        )

    def _safe_normalize_vector(
        self,
        vector: np.ndarray,
    ) -> np.ndarray:
        norm = np.linalg.norm(vector)

        if norm == 0:
            return vector

        return vector / norm

    def _clamp(
        self,
        value: float,
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> float:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return minimum

        return max(minimum, min(numeric_value, maximum))


_focus_scaling_service = FocusScalingService()


def get_focus_scaling_service() -> FocusScalingService:
    return _focus_scaling_service