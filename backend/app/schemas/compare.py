"""Schemas for the comparison endpoint (Compare Controller)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

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

    article_a_url: str | None = Field(
        default=None,
        description="HTTP/HTTPS URL of article A.",
    )
    article_b_url: str | None = Field(
        default=None,
        description="HTTP/HTTPS URL of article B.",
    )
    article_a_text: str | None = Field(
        default=None,
        description="Pasted plain-text body for article A.",
    )
    article_b_text: str | None = Field(
        default=None,
        description="Pasted plain-text body for article B.",
    )
    focus: ComparisonFocus = ComparisonFocus.GENERAL


class StageError(BaseModel):
    """A structured per-article error."""

    stage: str
    code: str | None = None
    message: str
    article_ref: str | None = None
    url: str | None = None


# ---------------------------------------------------------------------
# Public article response schemas
# ---------------------------------------------------------------------


class ArticleSummaryItem(BaseModel):
    """One extractive summary sentence returned to the frontend."""

    sentence_id: str | None = None
    article_ref: str | None = None
    text: str
    paragraph_index: int | None = None
    sentence_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    score: float | None = None


class CompareArticle(BaseModel):
    """
    Clean article payload returned by the comparison endpoint.

    Internal fields such as sentences, paragraph_chunks and embeddings
    are intentionally excluded.
    """

    article_ref: str
    url: str | None = None
    title: str | None = None
    source_domain: str | None = None
    source_type: str | None = None
    paragraphs: list[str] = Field(default_factory=list)
    summary: list[ArticleSummaryItem] = Field(default_factory=list)


# ---------------------------------------------------------------------
# Final comparison result schemas
# ---------------------------------------------------------------------


class ComparisonSummary(BaseModel):
    """Summary of final comparison output."""

    match_count: int = 0


class ComparisonMatch(BaseModel):
    """Final chunk-level comparison match returned to the frontend."""

    id: str

    a_chunk_id: str
    b_chunk_id: str

    a_paragraph_index: int | None = None
    b_paragraph_index: int | None = None
    a_chunk_index: int | None = None
    b_chunk_index: int | None = None

    label: Literal["aligned", "partially_aligned", "divergent"]
    score: float = 0.0

    confidence: str | None = None
    reason_code: str | None = None
    explanation: str | None = None

    a_text_preview: str | None = None
    b_text_preview: str | None = None


class ComparisonResult(BaseModel):
    """Final comparison result returned to the frontend."""

    focus: ComparisonFocus = ComparisonFocus.GENERAL
    summary: ComparisonSummary = Field(default_factory=ComparisonSummary)
    matches: list[ComparisonMatch] = Field(default_factory=list)


class CompareResponse(BaseModel):
    """Response for article processing and final comparison result."""

    focus: ComparisonFocus

    articles: list[CompareArticle] = Field(default_factory=list)

    errors: list[StageError] = Field(default_factory=list)

    processing: ProcessingSummary | None = Field(
        default=None,
        description="Timing and progress summary for the frontend progress UI.",
    )

    comparison: ComparisonResult | None = Field(
        default=None,
        description="Final comparison result with chunk-level matches.",
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