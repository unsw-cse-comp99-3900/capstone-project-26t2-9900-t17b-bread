from app.schemas.article import RawArticle
from app.services.preprocessing_service import (
    normalize_text,
    preprocess_article,
    split_paragraphs,
)


def _raw(body: str) -> RawArticle:
    return RawArticle(
        url="https://news.example.com/story",
        title="Example",
        source_domain="news.example.com",
        body_text=body,
    )


def test_normalize_collapses_whitespace():
    assert normalize_text("Hello    world\t\tagain") == "Hello world again"


def test_split_paragraphs():
    text = "Para one.\n\nPara two.\n\n\nPara three."
    assert split_paragraphs(normalize_text(text)) == [
        "Para one.",
        "Para two.",
        "Para three.",
    ]


def test_sentences_keep_source_and_position():
    body = (
        "The government announced a new budget today. Officials praised the plan.\n\n"
        "Opposition leaders criticised the spending levels sharply."
    )
    processed = preprocess_article(_raw(body), "A")

    assert processed.article_ref == "A"
    assert [s.sentence_index for s in processed.sentences] == [0, 1, 2]
    assert all(s.id == f"A-{i}" for i, s in enumerate(processed.sentences))
    assert all(s.article_ref == "A" for s in processed.sentences)
    # Last sentence belongs to the second paragraph.
    assert processed.sentences[-1].paragraph_index == 1


def test_offsets_point_to_sentence_text():
    body = "First valid sentence about policy. Second valid sentence about markets."
    processed = preprocess_article(_raw(body), "B")
    normalized = normalize_text(body)
    for sentence in processed.sentences:
        assert normalized[sentence.char_start:sentence.char_end].strip() == sentence.text


def test_short_noise_is_filtered():
    body = "Share. The actual article sentence carries real content here."
    processed = preprocess_article(_raw(body), "A")
    texts = [s.text for s in processed.sentences]
    assert "Share." not in texts
    assert any("actual article sentence" in t for t in texts)


def test_empty_body_does_not_crash():
    processed = preprocess_article(_raw("   "), "A")
    assert processed.sentences == []
    assert processed.paragraphs == []


def test_reproducible_output():
    body = "Alpha sentence about elections. Beta sentence about the economy."
    first = preprocess_article(_raw(body), "A")
    second = preprocess_article(_raw(body), "A")
    assert first.model_dump() == second.model_dump()
