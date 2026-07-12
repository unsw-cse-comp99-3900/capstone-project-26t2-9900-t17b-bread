# backend/app/services/bm25_similarity_service.py

from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi

from app.services.candidate_pair_service import get_candidate_pair_service


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Keep negation words such as "not", "no", and "without"
# because they may change the meaning of news statements.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "while", "of", "in", "on",
    "at", "to", "for", "from", "by", "with", "as", "is", "are", "was",
    "were", "be", "been", "being", "it", "this", "that", "these", "those",
    "he", "she", "they", "them", "his", "her", "their", "its", "we", "you",
    "i", "there", "here", "which", "who", "whom", "whose", "what", "when",
    "where", "why", "how",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 lexical matching."""
    tokens = _TOKEN_RE.findall(text.lower())
    return [token for token in tokens if token not in _STOPWORDS]


class BM25SimilarityService:
    """
    BM25 lexical similarity scoring service for paragraph chunks.

    This service only computes lexical similarity scores.
    It does not perform final alignment, relationship classification,
    or explanation generation.
    """

    def _prepare_valid_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Keep chunks that are valid for BM25 scoring.

        The candidate pair service first filters invalid chunk_id or empty text.
        This method then tokenizes text and removes chunks with no useful tokens.
        """
        candidate_service = get_candidate_pair_service()

        valid_chunks = candidate_service.extract_valid_chunks(chunks)

        prepared_chunks: list[dict[str, Any]] = []

        for chunk in valid_chunks:
            text = str(chunk.get("text", "")).strip()
            tokens = _tokenize(text)

            if not tokens:
                continue

            prepared_chunk = dict(chunk)
            prepared_chunk["_tokens"] = tokens
            prepared_chunks.append(prepared_chunk)

        return prepared_chunks

    def build_candidate_pairs(
        self,
        chunks_a: list[dict[str, Any]],
        chunks_b: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Build all possible A-B paragraph chunk candidate pairs.

        This delegates candidate generation to candidate_pair_service.
        It does not calculate scores and does not decide final alignment.
        """
        candidate_service = get_candidate_pair_service()

        valid_a = self._prepare_valid_chunks(chunks_a)
        valid_b = self._prepare_valid_chunks(chunks_b)

        if not valid_a or not valid_b:
            return []

        return candidate_service.build_candidate_pairs_from_valid_chunks(
            valid_a,
            valid_b,
        )

    def compute_score_matrix(
        self,
        chunks_a: list[dict[str, Any]],
        chunks_b: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compute BM25 lexical score matrix.

        Article B chunks are treated as the document corpus.
        Article A chunks are treated as queries.

        raw_scores are original BM25 values.
        scores are normalized to 0-1 for later hybrid scoring.
        """
        valid_a = self._prepare_valid_chunks(chunks_a)
        valid_b = self._prepare_valid_chunks(chunks_b)

        if not valid_a or not valid_b:
            return {
                "rows": [],
                "cols": [],
                "raw_scores": [],
                "scores": [],
            }

        raw_matrix = self._compute_raw_matrix(valid_a, valid_b)
        normalized_matrix = self._normalize_matrix(raw_matrix)

        return {
            "rows": [item.get("chunk_id") for item in valid_a],
            "cols": [item.get("chunk_id") for item in valid_b],
            "raw_scores": raw_matrix,
            "scores": normalized_matrix,
        }

    def compute_pair_scores(
        self,
        chunks_a: list[dict[str, Any]],
        chunks_b: list[dict[str, Any]],
        *,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Compute BM25 score for all A-B candidate pairs.

        bm25_raw_score is the original BM25 value.
        bm25_score is normalized to 0-1 for later hybrid scoring.
        """
        candidate_service = get_candidate_pair_service()

        valid_a = self._prepare_valid_chunks(chunks_a)
        valid_b = self._prepare_valid_chunks(chunks_b)

        if not valid_a or not valid_b:
            return []

        candidate_pairs = candidate_service.build_candidate_pairs_from_valid_chunks(
            valid_a,
            valid_b,
        )

        raw_matrix = self._compute_raw_matrix(valid_a, valid_b)
        normalized_matrix = self._normalize_matrix(raw_matrix)

        pair_scores: list[dict[str, Any]] = []

        for pair in candidate_pairs:
            i = pair["a_position"]
            j = pair["b_position"]

            raw_score = float(raw_matrix[i][j])
            score = float(normalized_matrix[i][j])

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
                    "bm25_raw_score": raw_score,
                    "bm25_score": score,
                }
            )

        return pair_scores

    def _compute_raw_matrix(
        self,
        valid_a: list[dict[str, Any]],
        valid_b: list[dict[str, Any]],
    ) -> list[list[float]]:
        """
        Compute raw BM25 scores from already prepared valid chunks.

        valid_b is used as the BM25 corpus.
        valid_a is used as the query side.
        """
        corpus_tokens = [item["_tokens"] for item in valid_b]
        query_tokens = [item["_tokens"] for item in valid_a]

        bm25 = BM25Okapi(corpus_tokens)

        raw_matrix: list[list[float]] = []

        for query in query_tokens:
            raw_scores = bm25.get_scores(query)
            raw_matrix.append([float(score) for score in raw_scores])

        return raw_matrix

    def _normalize_matrix(
        self,
        matrix: list[list[float]],
    ) -> list[list[float]]:
        """
        Normalize BM25 scores to 0-1.

        BM25 raw scores are not naturally bounded, so they need normalization
        before being combined with cosine similarity.
        """
        if not matrix:
            return []

        flat_scores = [score for row in matrix for score in row]
        max_score = max(flat_scores, default=0.0)

        if max_score <= 0:
            return [[0.0 for _ in row] for row in matrix]

        return [[float(score / max_score) for score in row] for row in matrix]


_bm25_similarity_service = BM25SimilarityService()


def get_bm25_similarity_service() -> BM25SimilarityService:
    return _bm25_similarity_service