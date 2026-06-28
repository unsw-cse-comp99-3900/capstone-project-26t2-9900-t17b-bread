# backend/app/services/chunking_service.py

from __future__ import annotations

from typing import Any

from app.schemas.article import ProcessedArticle


def build_paragraph_chunks(processed: ProcessedArticle) -> list[dict[str, Any]]:
    """
    Build paragraph-level chunks from a ProcessedArticle.

    Sprint 1 uses paragraph chunks as the semantic embedding unit.
    Each chunk keeps links to its source article, paragraph index, sentence ids,
    and character range so later comparison/highlighting can trace results
    back to the original article.
    """

    chunks: list[dict[str, Any]] = []

    for paragraph_index, paragraph_text in enumerate(processed.paragraphs):
        text = " ".join(paragraph_text.split()).strip()

        if not text:
            continue

        paragraph_sentences = [
            sentence
            for sentence in processed.sentences
            if sentence.paragraph_index == paragraph_index
        ]

        sentence_ids = [sentence.id for sentence in paragraph_sentences]

        char_start = paragraph_sentences[0].char_start if paragraph_sentences else None
        char_end = paragraph_sentences[-1].char_end if paragraph_sentences else None

        chunks.append(
            {
                "chunk_id": f"{processed.article_ref}-p{paragraph_index}",
                "article_ref": processed.article_ref,
                "chunk_type": "paragraph",
                "chunk_index": len(chunks),
                "paragraph_index": paragraph_index,
                "text": text,
                "sentence_ids": sentence_ids,
                "char_start": char_start,
                "char_end": char_end,
                "word_count": len(text.split()),
            }
        )

    return chunks