# backend/app/services/summary_service.py

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

from app.schemas.article import ProcessedArticle, SentenceUnit
from app.services.embedding_service import get_embedding_service


class SummaryService:
    """
    Non-LLM extractive summary service.

    The service:
    1. Generates an embedding for every valid article sentence.
    2. Builds a document centroid from all sentence embeddings.
    3. Scores sentences by semantic relevance to the whole article.
    4. Applies a redundancy penalty so the summary does not repeat
       nearly identical information.
    5. Returns selected sentences in their original article order.

    All summary sentences are copied directly from the source article.
    No new text is generated.
    """

    def summarize_article(
        self,
        article: ProcessedArticle,
        *,
        max_sentences: int = 3,
        redundancy_threshold: float = 0.85,
    ) -> list[dict[str, Any]]:
        """
        Generate an extractive summary for one processed article.

        Args:
            article:
                A ProcessedArticle produced by preprocessing_service.
            max_sentences:
                Maximum number of original sentences to include.
            redundancy_threshold:
                A candidate sentence is skipped when its cosine similarity
                with an already selected sentence is greater than or equal
                to this value.

        Returns:
            A list of selected sentence dictionaries. Results are returned
            in original article order.

        Example:
            [
                {
                    "sentence_id": "A-0",
                    "article_ref": "A",
                    "text": "...",
                    "paragraph_index": 0,
                    "sentence_index": 0,
                    "char_start": 0,
                    "char_end": 82,
                    "score": 0.7342
                }
            ]
        """
        if max_sentences <= 0:
            return []

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

        relevance_scores = self._calculate_relevance_scores(embeddings)

        selected_indices = self._select_non_redundant_sentences(
            embeddings=embeddings,
            relevance_scores=relevance_scores,
            max_sentences=max_sentences,
            redundancy_threshold=redundancy_threshold,
        )

        # The sentences are ranked for selection, but displayed in their
        # original article order so the summary remains readable.
        selected_indices.sort(
            key=lambda index: valid_sentences[index].sentence_index
        )

        return [
            self._build_result(
                valid_sentences[index],
                score=float(relevance_scores[index]),
            )
            for index in selected_indices
        ]

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

    def _encode_sentences(
        self,
        sentences: list[SentenceUnit],
    ) -> np.ndarray:
        """
        Encode sentences using the existing cached SentenceBERT model.

        Reusing get_embedding_service() prevents the backend from loading
        a second copy of the same model.
        """
        texts = [" ".join(sentence.text.split()) for sentence in sentences]

        embedding_service = get_embedding_service()
        embeddings = embedding_service.encode_sentences(texts)

        array = np.asarray(embeddings, dtype=float)

        if array.ndim != 2:
            return np.empty((0, 0), dtype=float)

        return self._normalise_rows(array)

    def _calculate_relevance_scores(
        self,
        embeddings: np.ndarray,
    ) -> np.ndarray:
        """
        Score every sentence against the semantic centre of the article.

        A sentence close to the document centroid is likely to represent
        information central to the overall article.
        """
        document_centroid = embeddings.mean(axis=0, keepdims=True)
        document_centroid = self._normalise_rows(document_centroid)

        return embeddings @ document_centroid[0]

    def _select_non_redundant_sentences(
        self,
        *,
        embeddings: np.ndarray,
        relevance_scores: np.ndarray,
        max_sentences: int,
        redundancy_threshold: float,
    ) -> list[int]:
        """
        Select high-relevance sentences while avoiding repetition.

        Ties are resolved by sentence position because np.argsort with the
        stable sorting algorithm preserves deterministic ordering.
        """
        ranked_indices = np.argsort(
            -relevance_scores,
            kind="stable",
        ).tolist()

        selected: list[int] = []

        for candidate_index in ranked_indices:
            if len(selected) >= max_sentences:
                break

            if not selected:
                selected.append(candidate_index)
                continue

            similarities = embeddings[selected] @ embeddings[candidate_index]
            highest_similarity = float(np.max(similarities))

            if highest_similarity < redundancy_threshold:
                selected.append(candidate_index)

        # If the redundancy filter was too strict, fill the remaining slots
        # using the next highest-scoring sentences.
        if len(selected) < max_sentences:
            for candidate_index in ranked_indices:
                if candidate_index in selected:
                    continue

                selected.append(candidate_index)

                if len(selected) >= max_sentences:
                    break

        return selected

    @staticmethod
    def _build_result(
        sentence: SentenceUnit,
        *,
        score: float,
    ) -> dict[str, Any]:
        """Convert a selected SentenceUnit into an API-friendly dictionary."""
        return {
            "sentence_id": sentence.id,
            "article_ref": sentence.article_ref,
            "text": sentence.text,
            "paragraph_index": sentence.paragraph_index,
            "sentence_index": sentence.sentence_index,
            "char_start": sentence.char_start,
            "char_end": sentence.char_end,
            "score": round(score, 6),
        }


@lru_cache(maxsize=1)
def get_summary_service() -> SummaryService:
    """Return one reusable summary service instance."""
    return SummaryService()