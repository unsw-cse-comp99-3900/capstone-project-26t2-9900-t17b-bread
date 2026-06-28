"""Preprocessing Service (PROJ-2 cleaning + PROJ-4 sentence preparation).

Takes cleaned body text from the Fetch Service and turns it into a structured
``ProcessedArticle``:
  * normalises whitespace,
  * splits the body into paragraphs,
  * segments paragraphs into sentences, attaching a stable id, source ref and
    position to each (PROJ-4 AC 4.1 / 4.2).

The transformation is deterministic: identical input + configuration yields
identical output (PROJ-4 AC 4.3). Empty/invalid sentences are skipped rather
than raising, so noisy content never breaks the pipeline (PROJ-4 AC 4.4).
"""

from __future__ import annotations

import re

from app.config import Settings, get_settings
from app.schemas.article import ProcessedArticle, RawArticle, SentenceUnit
from app.services.sentence_splitter import split_sentences

_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{2,}")


def normalize_text(text: str) -> str:
    """Collapse runs of intra-line whitespace and trim each line."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return _MULTI_NEWLINE_RE.sub("\n\n", text).strip()


def split_paragraphs(text: str) -> list[str]:
    """Split normalised text into non-empty paragraphs."""
    return [p.strip() for p in text.split("\n") if p.strip()]


def _is_valid_sentence(sentence: str, min_chars: int) -> bool:
    """Filter out noise (too short, or no alphabetic content)."""
    stripped = sentence.strip()
    if len(stripped) < min_chars:
        return False
    return any(ch.isalpha() for ch in stripped)


def preprocess_article(
    raw: RawArticle,
    article_ref: str,
    *,
    settings: Settings | None = None,
) -> ProcessedArticle:
    """Convert a ``RawArticle`` into a structured ``ProcessedArticle``."""
    settings = settings or get_settings()
    normalized = normalize_text(raw.body_text)
    paragraphs = split_paragraphs(normalized)
    paragraph_chunks = build_paragraph_chunks(article_ref, paragraphs)

    sentences: list[SentenceUnit] = []
    sentence_index = 0
    cursor = 0  # running char offset within the normalized body

    for paragraph_index, paragraph in enumerate(paragraphs):
        para_offset = normalized.find(paragraph, cursor)
        if para_offset == -1:
            para_offset = cursor
        cursor = para_offset + len(paragraph)

        local_cursor = 0
        for sentence in split_sentences(paragraph):
            local_offset = paragraph.find(sentence, local_cursor)
            if local_offset == -1:
                local_offset = local_cursor
            local_cursor = local_offset + len(sentence)

            if not _is_valid_sentence(sentence, settings.min_sentence_chars):
                continue

            char_start = para_offset + local_offset
            sentences.append(
                SentenceUnit(
                    id=f"{article_ref}-{sentence_index}",
                    article_ref=article_ref,
                    text=sentence.strip(),
                    paragraph_index=paragraph_index,
                    sentence_index=sentence_index,
                    char_start=char_start,
                    char_end=char_start + len(sentence),
                )
            )
            sentence_index += 1

    return ProcessedArticle(
        article_ref=article_ref,
        url=raw.url,
        title=raw.title,
        source_domain=raw.source_domain,
        paragraphs=paragraphs,
        sentences=sentences,
        paragraph_chunks=build_paragraph_chunks(article_ref, paragraphs)
    )

def build_paragraph_chunks(article_ref: str, paragraphs: list[str]):
    return [
        {
            "chunk_id": f"{article_ref}-p{i}",
            "article_ref": article_ref,
            "chunk_type": "paragraph",
            "text": p,
            "chunk_index": i,
        }
        for i, p in enumerate(paragraphs)
    ]