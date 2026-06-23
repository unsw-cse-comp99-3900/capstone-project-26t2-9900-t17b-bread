"""Sprint 2 service interfaces (placeholders).

These define the contracts for the comparison half of the Compare Controller
described on p.19-20 of the proposal. They are intentionally not implemented in
Sprint 1; each raises ``NotImplementedError`` and documents its responsibility,
inputs and outputs so the work can be picked up cleanly in Sprint 2.

Implementation order roughly follows the data flow:
    summary -> embedding -> retrieval/alignment -> crossmapping
    -> scaling/scoring -> narrative comparison -> explanation
"""

from __future__ import annotations

from app.schemas.article import ProcessedArticle, SentenceUnit
from app.schemas.compare import ComparisonFocus


def generate_extractive_summary(article: ProcessedArticle, max_sentences: int = 5) -> list[SentenceUnit]:
    """Extractive Summary Service (non-LLM) — PROJ-11.

    Select the most salient sentences (e.g. TextRank / centrality scoring) to
    form a concise summary, without generating new text.
    """
    raise NotImplementedError("Sprint 2: extractive summary service")


def embed_sentences(sentences: list[SentenceUnit]) -> list[list[float]]:
    """Embedding Service — SBERT sentence embeddings.

    Returns one dense vector per sentence, aligned by index. Embeddings should
    be cacheable/persistable (Embeddings collection) to avoid recomputation.
    """
    raise NotImplementedError("Sprint 2: SBERT embedding service")


def retrieve_candidates(
    sentences_a: list[SentenceUnit],
    sentences_b: list[SentenceUnit],
) -> list[tuple[str, str, float]]:
    """Retrieval & Alignment Service (BM25 + cosine) — PROJ-6.

    Returns candidate (sentence_a_id, sentence_b_id, score) pairs combining
    lexical (BM25) and semantic (cosine) similarity.
    """
    raise NotImplementedError("Sprint 2: BM25 + cosine hybrid retrieval")


def crossmap(candidates: list[tuple[str, str, float]]) -> list[dict]:
    """Crossmapping Service — PROJ-6.

    Resolves candidate pairs into a one-/few-to-one alignment of corresponding
    narrative segments across the two articles.
    """
    raise NotImplementedError("Sprint 2: crossmapping service")


def scale_scores(
    aligned: list[dict],
    focus: ComparisonFocus,
) -> list[dict]:
    """Scaling & Scoring Service — user-selected focus weighting.

    Re-weights alignment scores according to the chosen comparison focus
    (political / sentiment / economic / ...).
    """
    raise NotImplementedError("Sprint 2: scaling & scoring service")


def compare_narratives(scaled: list[dict]) -> list[dict]:
    """Narrative Comparison Service — PROJ-7.

    Labels each aligned pair as ``aligned`` / ``partially_aligned`` /
    ``divergent`` based on similarity and contextual difference.
    """
    raise NotImplementedError("Sprint 2: narrative comparison service")


def generate_explanations(labeled: list[dict]) -> list[dict]:
    """Explanation Generator (rule-based) — PROJ-9.

    Converts comparison outputs into human-readable explanations describing the
    main factors behind each label (shared vs missing details).
    """
    raise NotImplementedError("Sprint 2: rule-based explanation generator")
