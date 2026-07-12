"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def mock_embedding_service(monkeypatch):
    """Avoid loading SBERT during API tests."""

    class FakeEmbeddingService:
        model_name = "fake-model"

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

    monkeypatch.setattr(
        "app.services.pipeline.get_embedding_service",
        lambda: FakeEmbeddingService(),
    )
