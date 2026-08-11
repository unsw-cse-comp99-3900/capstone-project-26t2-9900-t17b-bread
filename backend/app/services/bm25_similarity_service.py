# backend/app/services/bm25_similarity_service.py

"""
BM25 Similarity Service — High-Level Overview
---------------------------------------------

This module provides lexical similarity scoring using the BM25 algorithm.
It is one of the two core similarity components in the comparison pipeline:
    • BM25 (lexical / keyword overlap)
    • SBERT (semantic / embedding-based similarity)

BM25 focuses strictly on word-level matching and does not perform semantic
reasoning, alignment, or relationship classification. Its output is combined
later with cosine similarity to produce hybrid scores.

Key Responsibilities
--------------------
1. Tokenization and Stopword Filtering
   - Tokenizes text using a lightweight regex that preserves alphanumeric words.
   - Removes common stopwords while keeping negation terms (“not”, “no”,
     “without”) because they meaningfully affect news statements.
   - Ensures BM25 operates on informative lexical units.

2. Chunk Validation and Preparation
   - Delegates initial filtering (empty text, invalid IDs) to the candidate
     pair service.
   - Removes chunks that produce no useful tokens.
   - Stores token lists in `_tokens` for efficient BM25 scoring.

3. Candidate Pair Generation
   - Builds all possible A–B paragraph chunk pairs using the candidate pair
     service.
   - Does not compute scores or decide alignment; it only prepares valid pairs.

4. BM25 Score Matrix Computation
   - Treats Article B chunks as the corpus and Article A chunks as queries.
   - Produces:
        • raw_scores: original BM25 values
        • scores: normalized 0–1 values for hybrid scoring
   - Normalization ensures compatibility with cosine similarity.

5. Pair-Level Scoring
   - Computes BM25 scores for each candidate pair.
   - Applies optional minimum-score filtering.
   - Returns structured results including chunk IDs, indices, and both raw
     and normalized scores.

Architectural Role
------------------
BM25 provides the lexical foundation for the hybrid similarity model. It ensures:

    • Paragraph pairs with strong keyword overlap are surfaced
    • Negation-sensitive lexical differences are preserved
    • Hybrid scoring can combine semantic and lexical signals
    • Alignment decisions later in the pipeline have reliable lexical evidence

By isolating BM25 logic in this module, the system maintains:

    • Clear separation between lexical and semantic similarity
    • Reusable tokenization and scoring routines
    • Predictable behaviour across all article types (URL, PDF, upload)
    • A stable interface for candidate pair generation and hybrid scoring
"""

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