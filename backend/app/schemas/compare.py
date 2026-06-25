"""Schemas for the comparison endpoint (Compare Controller)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.article import ProcessedArticle


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
    message: str
    article_ref: str | None = None
    url: str | None = None


class CompareResponse(BaseModel):
    """Sprint 1 response: both articles processed into comparison-ready form.

    The ``comparison`` field is reserved for Sprint 2 output (matched segments,
    relationship labels, explanations, summary).
    """

    focus: ComparisonFocus
    articles: list[ProcessedArticle] = Field(default_factory=list)
    errors: list[StageError] = Field(default_factory=list)
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
