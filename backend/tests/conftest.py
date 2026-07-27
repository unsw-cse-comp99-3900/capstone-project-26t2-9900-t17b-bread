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


class FakeContradictionDetectionService:
    """Stand-in for the CrossEncoder NLI model used by the comparison pipeline."""

    def analyse_mappings(self, cross_mappings, *, chunks_a, chunks_b):
        results = []
        for mapping in cross_mappings:
            enriched = dict(mapping)
            enriched.update(
                {
                    "entailment_score": 0.0,
                    "neutral_score": 1.0,
                    "contradiction_score": 0.0,
                    "forward_entailment_score": 0.0,
                    "forward_neutral_score": 1.0,
                    "forward_contradiction_score": 0.0,
                    "reverse_entailment_score": 0.0,
                    "reverse_neutral_score": 1.0,
                    "reverse_contradiction_score": 0.0,
                    "contradiction_margin": 0.0,
                    "contradiction_is_dominant": False,
                    "has_numeric_difference": False,
                    "casualty_numeric_difference": False,
                    "explicit_casualty_conflict": False,
                    "scope_mismatch": False,
                    "nli_label": "neutral",
                    "nli_evaluated": True,
                }
            )
            results.append(enriched)
        return results


@pytest.fixture(autouse=True)
def mock_ml_services(monkeypatch):
    """Avoid loading external ML models during tests."""
    fake_embedding = FakeEmbeddingService()
    fake_contradiction = FakeContradictionDetectionService()
    for target in (
        "app.services.embedding_service.get_embedding_service",
        "app.services.pipeline.get_embedding_service",
        "app.services.focus_scaling_service.get_embedding_service",
    ):
        monkeypatch.setattr(target, lambda: fake_embedding, raising=False)

    for target in (
        "app.services.contradiction_detection_service.get_contradiction_detection_service",
        "app.services.pipeline.get_contradiction_detection_service",
    ):
        monkeypatch.setattr(target, lambda: fake_contradiction, raising=False)
