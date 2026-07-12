"""Schemas for the comparison endpoint (Compare Controller)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.article import ProcessedArticle
from app.schemas.progress import ProcessingSummary


class ComparisonFocus(str, Enum):
    """User-selected comparison focus."""

    GENERAL = "general"
    POLITICAL = "political"
    SENTIMENT = "sentiment"
    ECONOMIC = "economic"
    SOCIAL = "social"


class CompareRequest(BaseModel):
    """Request to run the article-processing and comparison pipeline."""

    article_a_url: str = Field(..., description="HTTP/HTTPS URL of article A.")
    article_b_url: str = Field(..., description="HTTP/HTTPS URL of article B.")
    focus: ComparisonFocus = ComparisonFocus.GENERAL


class StageError(BaseModel):
    """A structured per-article error."""

    stage: str
    code: str | None = None
    message: str
    article_ref: str | None = None
    url: str | None = None


class ChunkDebug(BaseModel):
    """Lightweight paragraph chunk information for frontend testing."""

    chunk_id: str
    article_ref: str
    chunk_type: str = "paragraph"
    chunk_index: int | None = None
    paragraph_index: int | None = None
    text_preview: str
    word_count: int | None = None
    sentence_ids: list[str] = Field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None


class EmbeddingDebug(BaseModel):
    """Lightweight SBERT embedding information for frontend testing."""

    chunk_id: str
    article_ref: str
    model_name: str | None = None
    dimension: int | None = None
    vector_length: int
    vector_preview: list[float] = Field(default_factory=list)
    ok: bool


class ArticleNLPDebug(BaseModel):
    """Frontend-facing debug summary for chunking and embedding."""

    article_ref: str
    chunk_count: int
    embedding_count: int
    embedding_ready: bool
    chunks: list[ChunkDebug] = Field(default_factory=list)
    embeddings: list[EmbeddingDebug] = Field(default_factory=list)


# ---------------------------------------------------------------------
# Sprint 2 comparison schemas
# ---------------------------------------------------------------------


class ComparisonSummary(BaseModel):
    """Count summary for Sprint 2 comparison outputs."""

    cosine_pair_count: int = 0
    bm25_pair_count: int = 0
    hybrid_pair_count: int = 0
    cross_mapping_count: int = 0
    relationship_count: int = 0


class CrossMappingItem(BaseModel):
    """Final A-B paragraph mapping selected after hybrid scoring."""

    a_chunk_id: str
    b_chunk_id: str

    a_chunk_index: int | None = None
    b_chunk_index: int | None = None
    a_paragraph_index: int | None = None
    b_paragraph_index: int | None = None
    a_article_ref: str | None = None
    b_article_ref: str | None = None

    cosine_score: float = 0.0
    bm25_score: float = 0.0
    bm25_raw_score: float = 0.0

    base_hybrid_score: float = 0.0
    hybrid_score: float = 0.0

    focus: str = "general"
    pair_focus_relevance: float = 0.0
    scale_factor: float = 1.0

    context_support: float = 0.0
    mapping_score: float = 0.0


class RelationshipItem(BaseModel):
    """Relationship classification for a mapped A-B paragraph pair."""

    a_chunk_id: str
    b_chunk_id: str

    a_chunk_index: int | None = None
    b_chunk_index: int | None = None
    a_paragraph_index: int | None = None
    b_paragraph_index: int | None = None
    a_article_ref: str | None = None
    b_article_ref: str | None = None

    label: Literal["aligned", "partially_aligned", "divergent"]
    confidence: Literal["high", "medium", "low"] | str = "medium"
    reason_code: str | None = None

    cosine_score: float = 0.0
    bm25_score: float = 0.0
    base_hybrid_score: float = 0.0
    hybrid_score: float = 0.0
    mapping_score: float = 0.0
    context_support: float = 0.0

    focus: str = "general"
    pair_focus_relevance: float = 0.0

    a_text_preview: str | None = None
    b_text_preview: str | None = None


class ComparisonDebug(BaseModel):
    """Optional Sprint 2 debug information."""

    top_hybrid_pair_scores: list[dict[str, Any]] = Field(default_factory=list)
    top_cross_mappings: list[CrossMappingItem] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    """Sprint 2 comparison result returned to the frontend."""

    focus: str = "general"
    summary: ComparisonSummary = Field(default_factory=ComparisonSummary)
    cross_mappings: list[CrossMappingItem] = Field(default_factory=list)
    relationships: list[RelationshipItem] = Field(default_factory=list)
    debug: ComparisonDebug | None = None


class CompareResponse(BaseModel):
    """Response for article processing and Sprint 2 comparison."""

    focus: ComparisonFocus
    articles: list[ProcessedArticle] = Field(default_factory=list)
    errors: list[StageError] = Field(default_factory=list)

    processing: ProcessingSummary | None = Field(
        default=None,
        description="English timing/progress summary for the frontend progress UI.",
    )

    nlp_debug: list[ArticleNLPDebug] = Field(
        default_factory=list,
        description=(
            "Debug output for verifying paragraph chunking and SBERT embedding "
            "generation. Full embedding vectors are not returned."
        ),
    )

    comparison: ComparisonResult | None = Field(
        default=None,
        description=(
            "Sprint 2 comparison output, including cross mappings and "
            "relationship classifications."
        ),
    )

    session_token: str | None = Field(
        default=None,
        description=(
            "Token identifying the stored comparison session. Null when "
            "persistence is disabled or unavailable."
        ),
    )


# ---------------------------------------------------------------------
# Legacy Sprint 2 schemas
# Keep these only if older files such as sprint2_stubs.py still import them.
# They are not used by the new separated pipeline.
# ---------------------------------------------------------------------


class Alignment(BaseModel):
    a_index: int
    b_index: int
    similarity: float


class Relationship(BaseModel):
    a_index: int
    b_index: int
    label: Literal["aligned", "partially_aligned", "divergent"]


class Explanation(BaseModel):
    a_index: int
    b_index: int
    text: str