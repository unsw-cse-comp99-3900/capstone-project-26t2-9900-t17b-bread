from app.services.sentence_splitter import split_sentences


def test_basic_split():
    text = "The budget passed today. Critics disagreed strongly. Markets rose."
    assert split_sentences(text) == [
        "The budget passed today.",
        "Critics disagreed strongly.",
        "Markets rose.",
    ]


def test_abbreviations_do_not_split():
    text = "Dr. Smith met Mr. Lee on Tuesday. They discussed the U.S. economy."
    sentences = split_sentences(text)
    assert sentences == [
        "Dr. Smith met Mr. Lee on Tuesday.",
        "They discussed the U.S. economy.",
    ]


def test_decimal_numbers_do_not_split():
    text = "Inflation reached 3.5 percent last quarter. Growth slowed."
    assert split_sentences(text) == [
        "Inflation reached 3.5 percent last quarter.",
        "Growth slowed.",
    ]


def test_empty_input():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_deterministic():
    text = "First sentence here. Second one follows! And a third?"
    assert split_sentences(text) == split_sentences(text)
