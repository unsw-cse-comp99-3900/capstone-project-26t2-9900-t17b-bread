"""Schemas for the comparison endpoint (Compare Controller)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.progress import ProcessingSummary


# ---------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------


class ComparisonFocus(str, Enum):
    """User-selected comparison focus."""

    GENERAL = "general"
    POLITICAL = "political"
    SENTIMENT = "sentiment"
    ECONOMIC = "economic"
    SOCIAL = "social"


class CompareRequest(BaseModel):
    """
    Request to run the article-processing and comparison pipeline.

    Each article can be supplied as either a URL or pasted text.
    Uploaded files are handled by the multipart compare routes.
    """

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

    @model_validator(mode="after")
    def _require_a_source_per_article(
        self,
    ) -> CompareRequest:
        """Ensure each article has at least a URL or pasted text."""

        if not (self.article_a_url or "").strip() and not (
            self.article_a_text or ""
        ).strip():
            raise ValueError(
                "Article A is missing. Provide article_a_url "
                "or article_a_text."
            )

        if not (self.article_b_url or "").strip() and not (
            self.article_b_text or ""
        ).strip():
            raise ValueError(
                "Article B is missing. Provide article_b_url "
                "or article_b_text."
            )

        return self


class StageError(BaseModel):
    """A structured per-article processing error."""

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

    Internal sentence objects, paragraph chunks, and embeddings are excluded.
    """

    article_ref: str
    url: str | None = None
    title: str | None = None
    source_domain: str | None = None
    source_type: str | None = None
    paragraphs: list[str] = Field(
        default_factory=list
    )
    summary: list[ArticleSummaryItem] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------
# Public, interpretable 0-20 score schemas
# ---------------------------------------------------------------------


MatchStrengthLevel = Literal[
    "very_low",
    "low",
    "moderate",
    "strong",
    "very_strong",
]

FactorRelevanceLevel = Literal[
    "very_low",
    "low",
    "moderate",
    "strong",
    "very_strong",
]

StanceDiscrepancyLevel = Literal[
    "none",
    "slight",
    "moderate",
    "strong",
    "very_strong",
]

SelectedFactor = Literal[
    "political",
    "sentiment",
    "economic",
    "social",
]


class MatchStrengthScore(BaseModel):
    """
    Public 0-20 score describing how closely two chunks correspond.

    This is derived from the internal focus-independent mapping score.
    """

    score: int = Field(
        ge=0,
        le=20,
    )
    scale_min: int = Field(
        default=0,
        ge=0,
        le=20,
    )
    scale_max: int = Field(
        default=20,
        ge=0,
        le=20,
    )
    level: MatchStrengthLevel
    interpretation: str

    @model_validator(mode="after")
    def _validate_scale(
        self,
    ) -> MatchStrengthScore:
        """Ensure the public score lies inside its declared scale."""

        if self.scale_max < self.scale_min:
            raise ValueError(
                "scale_max must be greater than or equal to scale_min."
            )

        if not self.scale_min <= self.score <= self.scale_max:
            raise ValueError(
                "score must lie between scale_min and scale_max."
            )

        return self


class FactorRelevanceScore(BaseModel):
    """
    Public 0-20 score describing relevance to the selected factor.

    This field is omitted when the comparison focus is general.
    """

    factor: SelectedFactor
    score: int = Field(
        ge=0,
        le=20,
    )
    scale_min: int = Field(
        default=0,
        ge=0,
        le=20,
    )
    scale_max: int = Field(
        default=20,
        ge=0,
        le=20,
    )
    level: FactorRelevanceLevel
    interpretation: str

    @model_validator(mode="after")
    def _validate_scale(
        self,
    ) -> FactorRelevanceScore:
        """Ensure the public score lies inside its declared scale."""

        if self.scale_max < self.scale_min:
            raise ValueError(
                "scale_max must be greater than or equal to scale_min."
            )

        if not self.scale_min <= self.score <= self.scale_max:
            raise ValueError(
                "score must lie between scale_min and scale_max."
            )

        return self


class StanceDiscrepancyScore(BaseModel):
    """
    Public 0-20 score describing model-detected stance discrepancy.

    It is not a probability and does not determine factual correctness.
    """

    score: int = Field(
        ge=0,
        le=20,
    )
    scale_min: int = Field(
        default=0,
        ge=0,
        le=20,
    )
    scale_max: int = Field(
        default=20,
        ge=0,
        le=20,
    )
    level: StanceDiscrepancyLevel
    interpretation: str
    disclaimer: str

    @model_validator(mode="after")
    def _validate_scale(
        self,
    ) -> StanceDiscrepancyScore:
        """Ensure the public score lies inside its declared scale."""

        if self.scale_max < self.scale_min:
            raise ValueError(
                "scale_max must be greater than or equal to scale_min."
            )

        if not self.scale_min <= self.score <= self.scale_max:
            raise ValueError(
                "score must lie between scale_min and scale_max."
            )

        return self


# ---------------------------------------------------------------------
# Fixed score-guide schemas
# ---------------------------------------------------------------------


class ScoreBand(BaseModel):
    """One fixed, actionable interpretation band on the 0-20 scale."""

    min: int = Field(
        ge=0,
        le=20,
    )
    max: int = Field(
        ge=0,
        le=20,
    )
    level: str
    interpretation: str

    @model_validator(mode="after")
    def _validate_band(
        self,
    ) -> ScoreBand:
        """Ensure the band has a valid lower and upper boundary."""

        if self.max < self.min:
            raise ValueError(
                "ScoreBand.max must be greater than or equal to "
                "ScoreBand.min."
            )

        return self


class ScoreGuide(BaseModel):
    """Frontend guide explaining one public score and its fixed bands."""

    title: str
    question: str
    scale_min: int = Field(
        default=0,
        ge=0,
        le=20,
    )
    scale_max: int = Field(
        default=20,
        ge=0,
        le=20,
    )
    bands: list[ScoreBand] = Field(
        default_factory=list
    )
    disclaimer: str | None = None
    factor: SelectedFactor | None = None

    @model_validator(mode="after")
    def _validate_scale_and_bands(
        self,
    ) -> ScoreGuide:
        """Validate the declared scale and each score band."""

        if self.scale_max < self.scale_min:
            raise ValueError(
                "scale_max must be greater than or equal to scale_min."
            )

        for band in self.bands:
            if (
                band.min < self.scale_min
                or band.max > self.scale_max
            ):
                raise ValueError(
                    "Every score band must lie inside the guide scale."
                )

        return self


class ScoreGuides(BaseModel):
    """
    Fixed score definitions returned for frontend labels and tooltips.

    factor_relevance is null/omitted for general-focus comparisons.
    """

    match_strength: ScoreGuide
    stance_discrepancy: ScoreGuide
    factor_relevance: ScoreGuide | None = None


# ---------------------------------------------------------------------
# Frontend sorting metadata
# ---------------------------------------------------------------------


SortKey = Literal[
    "best_match",
    "selected_factor",
    "most_divergent",
    "article_order",
]

SortDirection = Literal[
    "ascending",
    "descending",
]


class SortOption(BaseModel):
    """One sorting option supported by the returned match data."""

    key: SortKey
    label: str
    score_path: str | None = None
    secondary_score_path: str | None = None
    direction: SortDirection
    description: str


class SortingMetadata(BaseModel):
    """Sorting configuration returned to the frontend."""

    default: Literal["best_match"] = "best_match"
    options: list[SortOption] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------
# Final comparison result schemas
# ---------------------------------------------------------------------


class ComparisonSummary(BaseModel):
    """
    Counts and aggregate public scores for visible matched pairs.

    All averages use the public 0-20 scale.
    """

    match_count: int = Field(
        default=0,
        ge=0,
    )
    aligned_count: int = Field(
        default=0,
        ge=0,
    )
    partially_aligned_count: int = Field(
        default=0,
        ge=0,
    )
    divergent_count: int = Field(
        default=0,
        ge=0,
    )

    average_match_strength: float = Field(
        default=0.0,
        ge=0.0,
        le=20.0,
    )
    average_stance_discrepancy: float = Field(
        default=0.0,
        ge=0.0,
        le=20.0,
    )
    average_factor_relevance: float | None = Field(
        default=None,
        ge=0.0,
        le=20.0,
    )


class ComparisonMatch(BaseModel):
    """
    Final chunk-level comparison match returned to the frontend.

    Raw cosine, BM25, hybrid, mapping, NLI probability, confidence, and
    factor-adjustment values are intentionally excluded.
    """

    id: str

    a_chunk_id: str
    b_chunk_id: str

    a_paragraph_index: int | None = None
    b_paragraph_index: int | None = None
    a_chunk_index: int | None = None
    b_chunk_index: int | None = None

    label: Literal[
        "aligned",
        "partially_aligned",
        "divergent",
    ]

    reason_code: str | None = None
    explanation: str | None = None

    match_strength: MatchStrengthScore

    factor_relevance: FactorRelevanceScore | None = Field(
        default=None,
        description=(
            "Relevance to the selected non-general factor. "
            "Null for general-focus comparisons."
        ),
    )

    stance_discrepancy: StanceDiscrepancyScore

    a_text_preview: str | None = None
    b_text_preview: str | None = None

    pair_number: int | None = Field(
        default=None,
        ge=1,
    )


class ComparisonResult(BaseModel):
    """Final comparison output returned to the frontend."""

    focus: ComparisonFocus = ComparisonFocus.GENERAL

    summary: ComparisonSummary = Field(
        default_factory=ComparisonSummary
    )

    score_guides: ScoreGuides

    sorting: SortingMetadata

    matches: list[ComparisonMatch] = Field(
        default_factory=list
    )


class CompareResponse(BaseModel):
    """Response for article processing and final comparison results."""

    focus: ComparisonFocus

    articles: list[CompareArticle] = Field(
        default_factory=list
    )

    errors: list[StageError] = Field(
        default_factory=list
    )

    processing: ProcessingSummary | None = Field(
        default=None,
        description=(
            "Timing and progress summary for the frontend progress UI."
        ),
    )

    comparison: ComparisonResult | None = Field(
        default=None,
        description=(
            "Final comparison result containing interpretable 0-20 scores, "
            "fixed score guides, sorting metadata, and chunk-level matches."
        ),
    )

    session_token: str | None = Field(
        default=None,
        description=(
            "Token identifying the stored comparison session. "
            "Null when persistence is disabled or unavailable."
        ),
    )

    comparison_id: int | None = Field(
        default=None,
        description=(
            "Database identifier for the persisted comparison result. "
            "Null when persistence is disabled or unavailable."
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
    label: Literal[
        "aligned",
        "partially_aligned",
        "divergent",
    ]


class Explanation(BaseModel):
    a_index: int
    b_index: int
    text: str