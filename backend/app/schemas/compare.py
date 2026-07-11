"""Schemas for the comparison endpoint (Compare Controller)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.article import ProcessedArticle
from app.schemas.progress import ProcessingSummary


class ComparisonFocus(str, Enum):
    """User-selected comparison focus (Scaling & Scoring Service).

    Sprint 1 only records the chosen focus; the weighting it drives is
    implemented in Sprint 2.
    """

    GENERAL = "general"
    POLITICAL = "political"
    SENTIMENT = "sentiment"
    ECONOMIC = "economic"
    SOCIAL = "social"


class CompareRequest(BaseModel):
    """Request to run the article-processing pipeline on a pair of articles."""

    article_a_url: str = Field(..., description="HTTP/HTTPS URL of article A.")
    article_b_url: str = Field(..., description="HTTP/HTTPS URL of article B.")
    focus: ComparisonFocus = ComparisonFocus.GENERAL


class StageError(BaseModel):
    """A structured per-article error (PROJ-2 AC 2.5, PROJ-3 AC 3.3)."""

    stage: str
    code: str
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
    """Lightweight SBERT embedding information for frontend testing.

    The full embedding vector is not returned here because it is large and is
    mainly used internally by the backend comparison logic.
    """

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


class CompareResponse(BaseModel):
    """Sprint 1 response: both articles processed into comparison-ready form.

    The ``comparison`` field is reserved for Sprint 2 output (matched segments,
    relationship labels, explanations, summary).
    """

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
            "Sprint 1 debug output for verifying paragraph chunking and "
            "SBERT embedding generation. This does not return full vectors."
        ),
    )

    comparison: dict | None = Field(
        default=None,
        description="Reserved for Sprint 2 comparison results.",
    )
    session_token: str | None = Field(
        default=None,
        description=(
            "Token identifying the stored comparison session. Null when "
            "persistence is disabled or the database is unavailable."
        ),
    )

#sprint 2 

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
