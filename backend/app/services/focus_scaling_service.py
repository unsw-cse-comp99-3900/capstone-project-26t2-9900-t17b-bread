# backend/app/services/focus_scaling_service.py

from __future__ import annotations

from typing import Any

import numpy as np

from app.services.embedding_service import get_embedding_service


FOCUS_PROFILES: dict[str, str] = {
    "political": (
        "Political framing focuses on how articles describe governments, "
        "political actors, public policy, power, responsibility, diplomacy, "
        "conflict, law, authority, and institutional decisions."
    ),
    "sentiment": (
        "Sentiment focuses on emotional tone, fear, anger, grief, concern, "
        "sympathy, blame, outrage, hope, suffering, tragedy, and human emotion."
    ),
    "economic": (
        "Economic focus concerns markets, prices, trade, business, employment, "
        "costs, inflation, investment, budgets, financial consequences, and resources."
    ),
    "social": (
        "Social impact focuses on communities, families, civilians, public life, "
        "education, health, housing, social groups, human consequences, and society."
    ),
}


FOCUS_MAX_BOOST: dict[str, float] = {
    "general": 0.0,
    "political": 0.18,
    "sentiment": 0.18,
    "economic": 0.18,
    "social": 0.18,
}


class FocusScalingService:
    """
    Apply user focus preference using semantic focus relevance.

    This service does not use keyword matching.
    It compares existing chunk embeddings with a focus-profile embedding.
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
        Compute chunk_id -> focus relevance score.

        The output score is between 0 and 1.
        For general comparison, all focus relevance scores are 0.
        """
        focus = (focus or "general").lower()

        if focus == "general" or focus not in FOCUS_PROFILES:
            return {}

        focus_vector = self._get_focus_embedding(focus)

        chunk_scores: dict[str, float] = {}
        raw_scores: list[tuple[str, float]] = []

        for item in embeddings_a + embeddings_b:
            chunk_id = item.get("chunk_id")
            vector = item.get("embedding")

            if not chunk_id or not isinstance(vector, list) or not vector:
                continue

            chunk_vector = np.array(vector, dtype=float)
            chunk_vector = self._safe_normalize_vector(chunk_vector)

            raw_score = float(chunk_vector @ focus_vector)

            raw_scores.append((chunk_id, raw_score))

        if not raw_scores:
            return {}

        return self._normalize_focus_scores(raw_scores)

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
        Apply focus scaling to a base hybrid score.

        This only applies a small boost. It should not replace the base
        cosine + BM25 similarity score.
        """
        focus = (focus or "general").lower()

        if focus == "general":
            return {
                "focus": focus,
                "a_focus_relevance": 0.0,
                "b_focus_relevance": 0.0,
                "pair_focus_relevance": 0.0,
                "scale_factor": 1.0,
                "final_score": base_score,
            }

        a_relevance = focus_relevance_lookup.get(a_chunk_id, 0.0)
        b_relevance = focus_relevance_lookup.get(b_chunk_id, 0.0)

        # Use both sides, but allow one strongly focus-relevant side to matter.
        pair_relevance = 0.7 * max(a_relevance, b_relevance) + 0.3 * min(
            a_relevance,
            b_relevance,
        )

        max_boost = FOCUS_MAX_BOOST.get(focus, 0.0)
        scale_factor = 1.0 + max_boost * pair_relevance

        final_score = min(base_score * scale_factor, 1.0)

        return {
            "focus": focus,
            "a_focus_relevance": a_relevance,
            "b_focus_relevance": b_relevance,
            "pair_focus_relevance": pair_relevance,
            "scale_factor": scale_factor,
            "final_score": final_score,
        }

    def _get_focus_embedding(self, focus: str) -> np.ndarray:
        """Encode and cache the selected focus profile."""
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

        vector = np.array(vector, dtype=float)
        vector = self._safe_normalize_vector(vector)

        self._focus_embedding_cache[focus] = vector
        return vector

    def _safe_normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vector)

        if norm == 0:
            return vector

        return vector / norm

    def _normalize_focus_scores(
        self,
        raw_scores: list[tuple[str, float]],
    ) -> dict[str, float]:
        """
        Normalize raw focus similarity scores to 0-1.

        A small floor is used so that weak accidental similarity does not
        create unnecessary focus boosts.
        """
        floor = 0.20

        adjusted = [
            (chunk_id, max(score - floor, 0.0))
            for chunk_id, score in raw_scores
        ]

        max_score = max((score for _, score in adjusted), default=0.0)

        if max_score <= 0:
            return {chunk_id: 0.0 for chunk_id, _ in raw_scores}

        return {
            chunk_id: float(score / max_score)
            for chunk_id, score in adjusted
        }


_focus_scaling_service = FocusScalingService()


def get_focus_scaling_service() -> FocusScalingService:
    return _focus_scaling_service