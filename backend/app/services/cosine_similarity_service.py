# backend/app/services/cosine_similarity_service.py

from __future__ import annotations

from typing import Any

import numpy as np

from app.services.candidate_pair_service import get_candidate_pair_service


def _safe_normalize(vectors: np.ndarray) -> np.ndarray:
    """
    Normalize vectors for cosine similarity.

    The embedding service already uses normalize_embeddings=True, but this
    keeps the scoring service safe if the embedding setting changes later.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _extract_vectors(
    embeddings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """
    Extract valid embedding vectors and keep their metadata.

    Invalid or empty embeddings are skipped.
    """
    valid_items: list[dict[str, Any]] = []
    vectors: list[list[float]] = []
    expected_dimension: int | None = None

    for item in embeddings:
        vector = item.get("embedding")

        if not isinstance(vector, list) or not vector:
            continue

        if expected_dimension is None:
            expected_dimension = len(vector)
        elif len(vector) != expected_dimension:
            raise ValueError(
                f"Inconsistent embedding dimensions: "
                f"expected {expected_dimension}, got {len(vector)}"
            )

        valid_items.append(item)
        vectors.append(vector)

    if not vectors:
        return [], np.empty((0, 0), dtype=float)

    return valid_items, np.array(vectors, dtype=float)


class CosineSimilarityService:
    """
    Cosine similarity scoring service for paragraph chunk embeddings.

    This service only computes semantic similarity scores.
    It does not perform final alignment, relationship classification,
    or explanation generation.
    """

    def _prepare_valid_embeddings(
        self,
        embeddings: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], np.ndarray]:
        """
        Keep only chunks that are valid candidate chunks and have embeddings.

        The candidate pair service filters invalid chunk_id or empty text.
        This service then filters invalid embedding vectors.
        """
        candidate_service = get_candidate_pair_service()

        valid_chunks = candidate_service.extract_valid_chunks(embeddings)
        valid_embeddings, vectors = _extract_vectors(valid_chunks)

        return valid_embeddings, vectors

    def build_candidate_pairs(
        self,
        embeddings_a: list[dict[str, Any]],
        embeddings_b: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Build all possible A-B paragraph chunk candidate pairs.

        This delegates candidate generation to candidate_pair_service.
        It does not calculate scores and does not decide final alignment.
        """
        candidate_service = get_candidate_pair_service()

        valid_a, _ = self._prepare_valid_embeddings(embeddings_a)
        valid_b, _ = self._prepare_valid_embeddings(embeddings_b)

        if not valid_a or not valid_b:
            return []

        return candidate_service.build_candidate_pairs_from_valid_chunks(
            valid_a,
            valid_b,
        )

    def compute_score_matrix(
        self,
        embeddings_a: list[dict[str, Any]],
        embeddings_b: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compute a cosine similarity matrix between Article A and Article B chunks.

        Output example:
            {
                "rows": ["A-p0", "A-p1"],
                "cols": ["B-p0", "B-p1"],
                "scores": [
                    [0.82, 0.43],
                    [0.51, 0.77]
                ]
            }
        """
        valid_a, vectors_a = self._prepare_valid_embeddings(embeddings_a)
        valid_b, vectors_b = self._prepare_valid_embeddings(embeddings_b)

        if not valid_a or not valid_b:
            return {
                "rows": [],
                "cols": [],
                "scores": [],
            }

        if vectors_a.shape[1] != vectors_b.shape[1]:
            raise ValueError(
                f"Embedding dimension mismatch: "
                f"A has {vectors_a.shape[1]}, B has {vectors_b.shape[1]}"
            )

        norm_a = _safe_normalize(vectors_a)
        norm_b = _safe_normalize(vectors_b)

        score_matrix = norm_a @ norm_b.T

        return {
            "rows": [item.get("chunk_id") for item in valid_a],
            "cols": [item.get("chunk_id") for item in valid_b],
            "scores": score_matrix.tolist(),
        }

    def compute_pair_scores(
        self,
        embeddings_a: list[dict[str, Any]],
        embeddings_b: list[dict[str, Any]],
        *,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Compute cosine similarity for all A-B candidate pairs.

        The output is designed for later hybrid scoring with BM25.
        This function does not perform final alignment.
        """
        candidate_service = get_candidate_pair_service()

        valid_a, vectors_a = self._prepare_valid_embeddings(embeddings_a)
        valid_b, vectors_b = self._prepare_valid_embeddings(embeddings_b)

        if not valid_a or not valid_b:
            return []

        if vectors_a.shape[1] != vectors_b.shape[1]:
            raise ValueError(
                f"Embedding dimension mismatch: "
                f"A has {vectors_a.shape[1]}, B has {vectors_b.shape[1]}"
            )

        candidate_pairs = candidate_service.build_candidate_pairs_from_valid_chunks(
            valid_a,
            valid_b,
        )

        norm_a = _safe_normalize(vectors_a)
        norm_b = _safe_normalize(vectors_b)

        score_matrix = norm_a @ norm_b.T

        pair_scores: list[dict[str, Any]] = []

        for pair in candidate_pairs:
            i = pair["a_position"]
            j = pair["b_position"]
            score = float(score_matrix[i][j])

            if min_score is not None and score < min_score:
                continue

            pair_scores.append(
                {
                    "a_chunk_id": pair["a_chunk_id"],
                    "b_chunk_id": pair["b_chunk_id"],
                    "a_chunk_index": pair["a_chunk_index"],
                    "b_chunk_index": pair["b_chunk_index"],
                    "a_paragraph_index": pair["a_paragraph_index"],
                    "b_paragraph_index": pair["b_paragraph_index"],
                    "a_article_ref": pair["a_article_ref"],
                    "b_article_ref": pair["b_article_ref"],
                    "cosine_score": score,
                }
            )

        return pair_scores


_cosine_similarity_service = CosineSimilarityService()


def get_cosine_similarity_service() -> CosineSimilarityService:
    return _cosine_similarity_service