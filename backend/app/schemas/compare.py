"""Schemas for the comparison endpoint (Compare Controller)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

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


# ---------------------------------------------------------------------
# Final comparison result schemas
# ---------------------------------------------------------------------


class ComparisonSummary(BaseModel):
    """Summary of final comparison output."""

    match_count: int = 0


class ComparisonMatch(BaseModel):
    """
    Final chunk-level comparison match returned to the frontend.

    The backend compares paragraph chunks, so the frontend should use
    a_paragraph_index and b_paragraph_index for paragraph-level highlighting.
    """

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
    """Final Sprint 2 comparison result returned to the frontend."""

    focus: str = "general"
    summary: ComparisonSummary = Field(default_factory=ComparisonSummary)
    matches: list[ComparisonMatch] = Field(default_factory=list)


class CompareResponse(BaseModel):
    """Response for article processing and final comparison result."""

    focus: ComparisonFocus

    articles: list[ProcessedArticle] = Field(default_factory=list)

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