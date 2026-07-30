"""Schemas for processing progress reporting."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


StepStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
]


class ProcessingStep(BaseModel):
    """
    One recorded pipeline step in the final processing summary.

    ``step`` remains a plain string so the schema supports the current
    comparison pipeline and future stages without requiring another schema
    change.
    """

    step: str
    label: str
    status: StepStatus = "pending"

    elapsed_seconds: float | None = Field(
        default=None,
        ge=0.0,
    )

    article_ref: str | None = None


class ProcessingSummary(BaseModel):
    """Final timing and progress summary returned with CompareResponse."""

    total_elapsed_seconds: float = Field(
        ge=0.0,
    )

    message: str

    steps: list[ProcessingStep] = Field(
        default_factory=list
    )


class ProgressEvent(BaseModel):
    """
    Real-time progress event for SSE / streaming clients.

    The ``step`` value is intentionally not restricted to a Literal enum.
    Current comparison stages include:

        cosine_similarity
        bm25_scoring
        hybrid_scoring
        candidate_cross_mapping
        contradiction_detection
        final_cross_mapping
        relationship_classification
        focus_scaling
    """

    # ProgressTracker.emit() includes the tracker name in every SSE event.
    name: str = "processing"

    percent: int = Field(
        ...,
        ge=0,
        le=100,
    )

    message: str

    elapsed_seconds: float = Field(
        ge=0.0,
    )

    step: str | None = None
    article_ref: str | None = None
    status: StepStatus | None = None