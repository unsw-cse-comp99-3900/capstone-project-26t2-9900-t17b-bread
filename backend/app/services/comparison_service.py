from __future__ import annotations

import numpy as np

from app.schemas.compare import Alignment, Relationship, Explanation
from app.services.pipeline import ArticleResult

#SPRINT 2 - COMPARISON 

def compare_articles(article_a: ArticleResult, article_b: ArticleResult) -> dict:
    """
    Main entry point for Sprint 2 comparison.
    Takes two ArticleResult objects and returns:
    - alignments
    - relationships
    - explanations
    """

    chunks_a = article_a.paragraph_chunks or []
    chunks_b = article_b.paragraph_chunks or []
    emb_a = article_a.chunk_embeddings or []
    emb_b = article_b.chunk_embeddings or []

    alignments = build_alignments(chunks_a, chunks_b, emb_a, emb_b)
    relationships = build_relationships(alignments)
    explanations = build_explanations(chunks_a, chunks_b, relationships)

    return {
        "alignments": alignments,
        "relationships": relationships,
        "explanations": explanations,
    }


# PROJ‑6: Identify Corresponding Content Across Articles

def build_alignments(
    chunks_a: list[dict],
    chunks_b: list[dict],
    emb_a: list[dict],
    emb_b: list[dict],
) -> list[Alignment]:

    # Extract embedding vectors
    vec_a = np.array([e.get("embedding", []) for e in emb_a])
    vec_b = np.array([e.get("embedding", []) for e in emb_b])

    if len(vec_a) == 0 or len(vec_b) == 0:
        return []

    # Normalise vectors
    norm_a = vec_a / np.linalg.norm(vec_a, axis=1, keepdims=True)
    norm_b = vec_b / np.linalg.norm(vec_b, axis=1, keepdims=True)

    # Cosine similarity matrix
    sim = norm_a @ norm_b.T

    alignments: list[Alignment] = []

    for i in range(len(chunks_a)):
        j = int(sim[i].argmax())
        score = float(sim[i][j])

        # AC 6.2: filter weak matches
        if score < 0.45:
            continue

        # AC 6.4: contextual proximity smoothing
        if i > 0:
            score *= 0.5 + 0.5 * float(sim[i - 1][j])
        if i < len(chunks_a) - 1:
            score *= 0.5 + 0.5 * float(sim[i + 1][j])

        alignments.append(
            Alignment(
                a_index=i,
                b_index=j,
                similarity=score,
            )
        )

    return alignments


# PROJ‑7: Categorise Differences in Reporting

def build_relationships(alignments: list[Alignment]) -> list[Relationship]:
    relationships: list[Relationship] = []

    for a in alignments:
        score = a.similarity

        if score >= 0.80:
            label = "aligned"
        elif score >= 0.50:
            label = "partially_aligned"
        else:
            label = "divergent"

        relationships.append(
            Relationship(
                a_index=a.a_index,
                b_index=a.b_index,
                label=label,
            )
        )

    return relationships


# PROJ‑9: Explanations for Comparison Decisions

def build_explanations(
    chunks_a: list[dict],
    chunks_b: list[dict],
    relationships: list[Relationship],
) -> list[Explanation]:

    explanations: list[Explanation] = []

    for r in relationships:
        text_a = chunks_a[r.a_index].get("text", "")
        text_b = chunks_b[r.b_index].get("text", "")

        # Simple explanations
        if r.label == "aligned":
            text = "Both sections discuss similar events with comparable details."
        elif r.label == "partially_aligned":
            text = "These sections cover the same event but differ in emphasis or specific details."
        else:
            text = "These sections focus on different aspects or events."

        explanations.append(
            Explanation(
                a_index=r.a_index,
                b_index=r.b_index,
                text=text,
            )
        )

    return explanations

Alignment.model_rebuild()
Explanation.model_rebuild()
Relationship.model_rebuild()

