# backend/app/services/embedding_service.py

"""
Embedding Service — High-Level Overview
---------------------------------------

This module provides a shared Sentence-BERT (SBERT) embedding service used
throughout the NLP pipeline. It is responsible for converting cleaned text
chunks and sentences into dense semantic vectors that downstream components
use for similarity scoring, alignment, hybrid scoring, and crossmapping.

Key Responsibilities
--------------------
1. Model Loading and Reuse
   - Loads the SBERT model lazily on first access.
   - Uses a global lru_cache to ensure the model is instantiated only once
     per backend process, preventing repeated heavy initialisation.
   - Avoids GPU/MPS usage on macOS to prevent known instability issues.

2. Paragraph Chunk Embeddings
   - encode_paragraph_chunks() receives structured paragraph chunks from the
     preprocessing pipeline.
   - Cleans text, removes excess whitespace, and filters empty chunks.
   - Produces normalised embeddings (unit vectors) suitable for cosine-based
     similarity and hybrid scoring.

3. Sentence Embeddings
   - encode_sentences() provides a lightweight interface for encoding raw
     sentences, used by summarisation, NLI, and explanation components.
   - Ensures consistent cleaning and normalisation across all text inputs.

4. Output Structure
   - Embedding results include metadata such as chunk_id, article_ref,
     paragraph index, character ranges, and embedding dimension.
   - This metadata allows downstream services to trace embeddings back to
     their original article structure for alignment and explanation.

Architectural Role
------------------
The Embedding Service is a core dependency of the NLP pipeline. It ensures:

    • A single, shared SBERT model instance across the backend
    • Consistent text cleaning and normalisation before embedding
    • Stable, reproducible embeddings for all pipeline stages
    • Clear separation between model inference and higher-level logic

By isolating embedding logic in this module, the rest of the pipeline can
focus on alignment, scoring, and explanation without needing to manage
model loading, batching, or device configuration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

import torch

#security checks for macs with gpu
if torch.backends.mps.is_available():
    print("⚠️ MPS detected — disabling to prevent crashes.")
    torch.backends.mps.is_available = lambda: False
    torch.backends.mps.is_built = lambda: False

class EmbeddingService:
    """SBERT-based embedding service for paragraph chunks."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode_paragraph_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
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
    
    def encode_sentences(
        self,
        sentences: list[str],
    ) -> list[list[float]]:
        """
        Encode a list of sentences using the shared SBERT model.
        """

        cleaned = [
            " ".join(sentence.split()).strip()
            for sentence in sentences
            if sentence.strip()
        ]

        if not cleaned:
            return []

        embeddings = self.model.encode(
            cleaned,
            batch_size=16,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()
    
    
    


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Load the SBERT model once and reuse it across backend calls."""
    return EmbeddingService()

