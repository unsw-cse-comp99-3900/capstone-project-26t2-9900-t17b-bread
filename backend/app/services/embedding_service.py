# backend/app/services/embedding_service.py

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sentence_transformers import SentenceTransformer


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingService:
    """
    SBERT-based embedding service for paragraph chunks.

    Sprint 1 only supports paragraph chunk embeddings.
    Extractive summary embeddings can be added in later sprints without
    changing the core encode method.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode_paragraph_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Convert paragraph chunks into SBERT embedding vectors.

        Input:
            [
                {
                    "chunk_id": "article_a-p0",
                    "article_ref": "article_a",
                    "chunk_type": "paragraph",
                    "text": "paragraph text..."
                }
            ]

        Output:
            [
                {
                    "chunk_id": "article_a-p0",
                    "article_ref": "article_a",
                    "chunk_type": "paragraph",
                    "text": "paragraph text...",
                    "embedding": [...],
                    "dimension": 384
                }
            ]
        """

        valid_chunks: list[dict[str, Any]] = []

        for chunk in chunks:
            text = str(chunk.get("text", "")).strip()
            if text:
                cleaned_chunk = dict(chunk)
                cleaned_chunk["text"] = " ".join(text.split())
                valid_chunks.append(cleaned_chunk)

        if not valid_chunks:
            return []

        texts = [chunk["text"] for chunk in valid_chunks]

        embeddings = self.model.encode(
            texts,
            batch_size=16,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        results: list[dict[str, Any]] = []

        for chunk, embedding in zip(valid_chunks, embeddings):
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "article_ref": chunk["article_ref"],
                    "chunk_type": chunk.get("chunk_type", "paragraph"),
                    "chunk_index": chunk.get("chunk_index"),
                    "paragraph_index": chunk.get("paragraph_index"),
                    "text": chunk["text"],
                    "sentence_ids": chunk.get("sentence_ids", []),
                    "char_start": chunk.get("char_start"),
                    "char_end": chunk.get("char_end"),
                    "word_count": chunk.get("word_count"),
                    "embedding": embedding.tolist(),
                    "dimension": len(embedding),
                    "model_name": self.model_name,
                }
            )

        return results


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """
    Load the SBERT model once and reuse it across backend calls.
    """
    return EmbeddingService()