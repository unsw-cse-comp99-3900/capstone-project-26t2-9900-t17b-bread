# backend/app/services/summary_service.py

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

from app.schemas.article import ProcessedArticle, SentenceUnit
from app.services.bm25_similarity_service import get_bm25_similarity_service
from app.services.embedding_service import get_embedding_service


class SummaryService:
    """
    Non-LLM extractive summary service.

    The service:
    1. Generates an embedding for every valid article sentence.
    2. Calculates semantic relevance using the document centroid.
    3. Calculates lexical relevance using the shared BM25 service.
    4. Combines semantic and BM25 scores into one relevance score.
    5. Filters candidates using a relevance threshold.
    6. Removes sentences that are too similar to already selected sentences.
    7. Returns the selected sentences in their original article order.

    All summary sentences are copied directly from the source article.
    No new text is generated.
    """

    def summarize_article(
        self,
        article: ProcessedArticle,
        *,
        max_sentences: int = 3,
        semantic_weight: float = 0.7,
        bm25_weight: float = 0.3,
        relevance_threshold: float = 0.3,
        redundancy_threshold: float = 0.85,
    ) -> list[dict[str, Any]]:
        """
        Generate an extractive summary for one processed article.

        Args:
            article:
                A ProcessedArticle produced by preprocessing_service.
            max_sentences:
                Maximum number of source sentences to return.
            semantic_weight:
                Weight given to SBERT semantic relevance.
            bm25_weight:
                Weight given to BM25 lexical relevance.
            relevance_threshold:
                Candidates below this combined score are ignored.
            redundancy_threshold:
                A candidate is skipped when its cosine similarity with an
                already selected sentence is greater than or equal to this
                value.
        """
        if max_sentences <= 0:
            return []

        if semantic_weight < 0 or bm25_weight < 0:
            raise ValueError("Summary score weights cannot be negative.")

        total_weight = semantic_weight + bm25_weight

        if total_weight <= 0:
            raise ValueError(
                "At least one summary score weight must be greater than zero."
            )

        # Ensure the weights always add up to 1.
        semantic_weight /= total_weight
        bm25_weight /= total_weight

        valid_sentences = self._get_valid_sentences(article.sentences)

        if not valid_sentences:
            return []

        if len(valid_sentences) <= max_sentences:
            return [
                self._build_result(sentence, score=1.0)
                for sentence in valid_sentences
            ]

        embeddings = self._encode_sentences(valid_sentences)

        if embeddings.size == 0:
            return []

        semantic_scores = self._calculate_semantic_scores(embeddings)
        semantic_scores = self._min_max_normalise(semantic_scores)

        bm25_scores = self._calculate_bm25_scores(valid_sentences)

        combined_scores = (
            semantic_weight * semantic_scores
            + bm25_weight * bm25_scores
        )

        selected_indices = self._select_non_redundant_sentences(
            embeddings=embeddings,
            relevance_scores=combined_scores,
            max_sentences=max_sentences,
            relevance_threshold=relevance_threshold,
            redundancy_threshold=redundancy_threshold,
        )

        # Keep the final extractive summary in source order.
        selected_indices.sort(
            key=lambda index: (
                valid_sentences[index].paragraph_index,
                valid_sentences[index].sentence_index,
            )
        )

        return [
            self._build_result(
                valid_sentences[index],
                score=float(combined_scores[index]),
            )
            for index in selected_indices
        ]

    def summarize_comparison(
        self,
        comparison_results: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Generate a structured high-level summary from comparison results.

        Expected relationship labels:
        - aligned
        - partially_aligned
        - divergent
        - unique_to_a
        - unique_to_b
        """
        summary: dict[str, list[dict[str, Any]]] = {
            "similarities": [],
            "differences": [],
            "unique_to_a": [],
            "unique_to_b": [],
        }

        for result in comparison_results:
            relationship = str(
                result.get("label", "")
            ).strip().lower()

            item = {
                "text_a": result.get("a_text_preview"),
                "text_b": result.get("b_text_preview"),
                "score": result.get("score"),
                "label": relationship,
            }

            if relationship == "aligned":
                summary["similarities"].append(item)

            elif relationship in {
                "partially_aligned",
                "divergent",
            }:
                summary["differences"].append(item)

            elif relationship == "unique_to_a":
                summary["unique_to_a"].append(item)

            elif relationship == "unique_to_b":
                summary["unique_to_b"].append(item)

        return summary

    @staticmethod
    def _get_valid_sentences(
        sentences: list[SentenceUnit],
    ) -> list[SentenceUnit]:
        """Remove empty sentence records while preserving source order."""
        return [
            sentence
            for sentence in sentences
            if sentence.text and sentence.text.strip()
        ]

    @staticmethod
    def _normalise_rows(vectors: np.ndarray) -> np.ndarray:
        """Safely normalise each row for cosine similarity."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    @staticmethod
    def _min_max_normalise(scores: np.ndarray) -> np.ndarray:
        """Normalise a one-dimensional score array to the range 0–1."""
        if scores.size == 0:
            return scores

        minimum = float(np.min(scores))
        maximum = float(np.max(scores))

        if maximum <= minimum:
            return np.ones_like(scores, dtype=float)

        return (scores - minimum) / (maximum - minimum)

    def _encode_sentences(
        self,
        sentences: list[SentenceUnit],
    ) -> np.ndarray:
        """
        Encode sentences using the shared cached Sentence-BERT model.
        """
        texts = [
            " ".join(sentence.text.split())
            for sentence in sentences
        ]

        embedding_service = get_embedding_service()
        embeddings = embedding_service.encode_sentences(texts)

        array = np.asarray(embeddings, dtype=float)

        if array.ndim != 2:
            return np.empty((0, 0), dtype=float)

        return self._normalise_rows(array)

    def _calculate_semantic_scores(
        self,
        embeddings: np.ndarray,
    ) -> np.ndarray:
        """
        Score each sentence against the semantic centre of the article.
        """
        document_centroid = embeddings.mean(axis=0, keepdims=True)
        document_centroid = self._normalise_rows(document_centroid)

        return embeddings @ document_centroid[0]

    def _calculate_bm25_scores(
        self,
        sentences: list[SentenceUnit],
    ) -> np.ndarray:
        """
        Calculate lexical relevance using the existing BM25 service.

        The complete article is used as the query, while each sentence is
        treated as a candidate BM25 document.
        """
        article_text = " ".join(
            " ".join(sentence.text.split())
            for sentence in sentences
        )

        query_chunk = {
            "chunk_id": "summary-query",
            "article_ref": "SUMMARY",
            "chunk_index": 0,
            "paragraph_index": 0,
            "text": article_text,
        }

        sentence_chunks = [
            {
                "chunk_id": sentence.id,
                "article_ref": sentence.article_ref,
                "chunk_index": index,
                "paragraph_index": sentence.paragraph_index,
                "text": sentence.text,
            }
            for index, sentence in enumerate(sentences)
        ]

        bm25_service = get_bm25_similarity_service()

        matrix = bm25_service.compute_score_matrix(
            [query_chunk],
            sentence_chunks,
        )

        rows = matrix.get("scores", [])
        column_ids = matrix.get("cols", [])

        if not rows or not rows[0]:
            return np.zeros(len(sentences), dtype=float)

        score_by_sentence_id = {
            sentence_id: float(score)
            for sentence_id, score in zip(column_ids, rows[0])
        }

        return np.asarray(
            [
                score_by_sentence_id.get(sentence.id, 0.0)
                for sentence in sentences
            ],
            dtype=float,
        )

    def _select_non_redundant_sentences(
        self,
        *,
        embeddings: np.ndarray,
        relevance_scores: np.ndarray,
        max_sentences: int,
        relevance_threshold: float,
        redundancy_threshold: float,
    ) -> list[int]:
        """
        Select relevant sentences while avoiding semantic repetition.
        """
        ranked_indices = np.argsort(
            -relevance_scores,
            kind="stable",
        ).tolist()

        selected: list[int] = []

        for candidate_index in ranked_indices:
            if len(selected) >= max_sentences:
                break

            candidate_score = float(relevance_scores[candidate_index])

            # Relevant threshold:
            # ignore sentences whose combined score is too low.
            if candidate_score < relevance_threshold:
                continue

            if not selected:
                selected.append(candidate_index)
                continue

            # Similarity threshold:
            # skip a sentence if it is too similar to a selected sentence.
            similarities = (
                embeddings[selected]
                @ embeddings[candidate_index]
            )

            highest_similarity = float(np.max(similarities))

            if highest_similarity < redundancy_threshold:
                selected.append(candidate_index)

        # Avoid returning an empty summary when every candidate falls just
        # below the relevance threshold.
        if not selected and ranked_indices:
            selected.append(ranked_indices[0])

        return selected

    @staticmethod
    def _build_result(
        sentence: SentenceUnit,
        *,
        score: float,
    ) -> dict[str, Any]:
        """Convert a selected sentence into an API-friendly dictionary."""
        return {
            "sentence_id": sentence.id,
            "article_ref": sentence.article_ref,
            "text": sentence.text,
            "paragraph_index": sentence.paragraph_index,
            "sentence_index": sentence.sentence_index,
            "char_start": sentence.char_start,
            "char_end": sentence.char_end,
            "score": round(float(np.clip(score, 0.0, 1.0)), 6),
        }


@lru_cache(maxsize=1)
def get_summary_service() -> SummaryService:
    """Return one reusable summary service instance."""
    return SummaryService()