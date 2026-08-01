# backend/tests/test_summary_service.py

from __future__ import annotations

import numpy as np

from app.schemas.article import ProcessedArticle, SentenceUnit
from app.services.summary_service import SummaryService


def _make_sentence(
    index: int,
    text: str,
    *,
    article_ref: str = "A",
    paragraph_index: int = 0,
) -> SentenceUnit:
    """Create one SentenceUnit for summary-service tests."""
    return SentenceUnit(
        id=f"{article_ref}-{index}",
        article_ref=article_ref,
        text=text,
        paragraph_index=paragraph_index,
        sentence_index=index,
        char_start=index * 100,
        char_end=(index * 100) + len(text),
    )


def _make_article(sentences: list[SentenceUnit]) -> ProcessedArticle:
    """Create a minimal ProcessedArticle for testing."""
    return ProcessedArticle(
        article_ref="A",
        url="https://example.com/article",
        title="Example article",
        source_domain="example.com",
        paragraphs=[],
        sentences=sentences,
        paragraph_chunks=[],
    )


class _FakeModel:
    """Fake SentenceBERT model returning deterministic test vectors."""

    def encode(
        self,
        texts,
        *,
        batch_size,
        convert_to_numpy,
        normalize_embeddings,
        show_progress_bar,
    ):
        vectors = {
            "The government announced a new national budget.": [1.0, 0.0, 0.0],
            "The budget increases funding for public hospitals.": [0.9, 0.1, 0.0],
            "The plan also includes new transport projects.": [0.8, 0.2, 0.0],
            "Opposition parties criticised the proposal.": [0.0, 1.0, 0.0],
            "Heavy rain was reported in another region.": [0.0, 0.0, 1.0],
            "The government repeated its national budget announcement.": [
                0.99,
                0.01,
                0.0,
            ],
        }

        return np.array(
            [vectors[text] for text in texts],
            dtype=float,
        )


class _FakeEmbeddingService:
    """Fake wrapper matching the existing embedding service interface."""

    def __init__(self):
        self.model = _FakeModel()

    def encode_sentences(self, texts):
        return self.model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )


def test_empty_article_returns_empty_summary():
    service = SummaryService()
    article = _make_article([])

    result = service.summarize_article(article)

    assert result == []


def test_article_with_fewer_sentences_returns_all_sentences():
    service = SummaryService()

    sentences = [
        _make_sentence(0, "The government announced a new national budget."),
        _make_sentence(
            1,
            "The budget increases funding for public hospitals.",
        ),
    ]

    article = _make_article(sentences)

    result = service.summarize_article(
        article,
        max_sentences=3,
    )

    assert len(result) == 2
    assert [item["sentence_id"] for item in result] == ["A-0", "A-1"]
    assert [item["text"] for item in result] == [
        sentence.text for sentence in sentences
    ]


def test_summary_selects_original_sentences(monkeypatch):
    fake_service = _FakeEmbeddingService()

    monkeypatch.setattr(
        "app.services.summary_service.get_embedding_service",
        lambda: fake_service,
    )

    sentences = [
        _make_sentence(0, "The government announced a new national budget."),
        _make_sentence(
            1,
            "The budget increases funding for public hospitals.",
        ),
        _make_sentence(
            2,
            "The plan also includes new transport projects.",
        ),
        _make_sentence(
            3,
            "Opposition parties criticised the proposal.",
        ),
        _make_sentence(
            4,
            "Heavy rain was reported in another region.",
        ),
    ]

    article = _make_article(sentences)
    service = SummaryService()

    result = service.summarize_article(
        article,
        max_sentences=3,
    )

    original_texts = {sentence.text for sentence in sentences}

    assert 1 <= len(result) <= 3
    assert all(item["text"] in original_texts for item in result)
    assert all(item["article_ref"] == "A" for item in result)
    assert all("score" in item for item in result)


def test_summary_is_returned_in_original_article_order(monkeypatch):
    fake_service = _FakeEmbeddingService()

    monkeypatch.setattr(
        "app.services.summary_service.get_embedding_service",
        lambda: fake_service,
    )

    sentences = [
        _make_sentence(0, "The government announced a new national budget."),
        _make_sentence(
            1,
            "The budget increases funding for public hospitals.",
        ),
        _make_sentence(
            2,
            "The plan also includes new transport projects.",
        ),
        _make_sentence(
            3,
            "Opposition parties criticised the proposal.",
        ),
        _make_sentence(
            4,
            "Heavy rain was reported in another region.",
        ),
    ]

    article = _make_article(sentences)
    service = SummaryService()

    result = service.summarize_article(
        article,
        max_sentences=3,
    )

    selected_positions = [
        item["sentence_index"]
        for item in result
    ]

    assert selected_positions == sorted(selected_positions)


def test_max_sentences_zero_returns_empty_summary():
    service = SummaryService()

    article = _make_article(
        [
            _make_sentence(
                0,
                "The government announced a new national budget.",
            )
        ]
    )

    result = service.summarize_article(
        article,
        max_sentences=0,
    )

    assert result == []


def test_highly_redundant_sentence_is_avoided(monkeypatch):
    fake_service = _FakeEmbeddingService()

    monkeypatch.setattr(
        "app.services.summary_service.get_embedding_service",
        lambda: fake_service,
    )

    sentences = [
        _make_sentence(0, "The government announced a new national budget."),
        _make_sentence(
            1,
            "The government repeated its national budget announcement.",
        ),
        _make_sentence(
            2,
            "Opposition parties criticised the proposal.",
        ),
        _make_sentence(
            3,
            "Heavy rain was reported in another region.",
        ),
    ]

    article = _make_article(sentences)
    service = SummaryService()

    result = service.summarize_article(
        article,
        max_sentences=2,
        redundancy_threshold=0.85,
    )

    selected_ids = {
        item["sentence_id"]
        for item in result
    }

    # The two nearly identical budget sentences should not both appear.
    assert not {"A-0", "A-1"}.issubset(selected_ids)