# backend/app/services/chunking_service.py

"""
Chunking Service — High-Level Overview
--------------------------------------

This module converts a fully preprocessed article (ProcessedArticle) into
paragraph-level semantic chunks. These chunks form the fundamental units used
throughout the NLP pipeline for embedding, similarity scoring, alignment,
crossmapping, and frontend highlighting.

Key Responsibilities
--------------------
1. Paragraph Extraction
   - Iterates through the cleaned paragraph list produced by the preprocessing
     pipeline.
   - Normalises whitespace and filters out empty paragraphs.

2. Sentence Association
   - Each paragraph chunk is linked to the sentences that belong to it.
   - Sentence IDs allow downstream components (embeddings, NLI, explanation)
     to trace model outputs back to specific textual units.

3. Character Range Tracking
   - char_start and char_end record the exact character offsets of the paragraph
     within the original article.
   - Enables precise frontend highlighting and diff visualisation.

4. Metadata Construction
   - Each chunk includes:
        • chunk_id (stable identifier)
        • article_ref (A/B/upload/fetch)
        • paragraph index
        • chunk index (sequential)
        • cleaned text
        • word count
   - This metadata ensures consistent behaviour across all pipeline stages.

Architectural Role
------------------
Paragraph chunking is the bridge between preprocessing and semantic modelling.
It ensures that:

    • The embedding service receives clean, meaningful text units
    • BM25 and cosine similarity operate on coherent narrative blocks
    • Crossmapping aligns comparable content rather than raw sentences
    • The frontend can highlight matched pairs with accurate character ranges

By isolating chunk construction in this module, the pipeline maintains:

    • Clear separation of concerns
    • Stable, reproducible chunk IDs
    • Consistent text segmentation across all article types (URL, PDF, upload)
    • A predictable structure for downstream scoring and explanation services
"""

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