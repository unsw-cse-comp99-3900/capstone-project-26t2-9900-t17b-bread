"""Schemas for processing progress reporting."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]


class ProcessingStep(BaseModel):
    step: str
    label: str
    status: StepStatus = "pending"
    elapsed_seconds: float | None = None
    article_ref: str | None = None


class ProcessingSummary(BaseModel):
    total_elapsed_seconds: float
    message: str
    steps: list[ProcessingStep] = Field(default_factory=list)


class ProgressEvent(BaseModel):
    """Real-time progress event for SSE / streaming clients."""

    percent: int = Field(..., ge=0, le=100)
    message: str
    elapsed_seconds: float
    step: str | None = None
    article_ref: str | None = None
    status: StepStatus | None = None
