"""Shared pytest fixtures."""

from __future__ import annotations

import numpy as np
import pytest


class _FakeModel:
    """Stand-in for a SentenceTransformer model (no torch/SBERT needed)."""

    def encode(self, inputs, **kwargs):
        single = isinstance(inputs, str)
        texts = [inputs] if single else list(inputs)
        vectors = np.array([[0.1, 0.2, 0.3] for _ in texts], dtype=float)
        return vectors[0] if single else vectors


class FakeEmbeddingService:
    model_name = "fake-model"
    model = _FakeModel()

    def encode_paragraph_chunks(self, chunks):
        results = []
        for chunk in chunks:
            text = str(chunk.get("text", "")).strip()
            if not text:
                continue
            results.append(
                {
                    **chunk,
                    "embedding": [0.1, 0.2, 0.3],
                    "dimension": 3,
                    "model_name": self.model_name,
                }
            )
        return results


@pytest.fixture(autouse=True)
def mock_embedding_service(monkeypatch):
    """Avoid loading SBERT during tests, in every module that uses it."""
    fake = FakeEmbeddingService()
    for target in (
        "app.services.embedding_service.get_embedding_service",
        "app.services.pipeline.get_embedding_service",
        "app.services.focus_scaling_service.get_embedding_service",
    ):
        monkeypatch.setattr(target, lambda: fake, raising=False)
