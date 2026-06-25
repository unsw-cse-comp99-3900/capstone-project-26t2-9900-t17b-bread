"""Structured pipeline errors.

Every stage of the article-processing pipeline raises ``PipelineError`` so the
API layer can return a consistent, structured error response that identifies
which stage failed (PROJ-3, AC 3.3 / PROJ-2, AC 2.5).
"""

from __future__ import annotations

from enum import Enum


class PipelineStage(str, Enum):
    VALIDATION = "validation"
    FETCH = "fetch"
    EXTRACTION = "extraction"
    PREPROCESSING = "preprocessing"
    SENTENCE_PREPARATION = "sentence_preparation"


class PipelineError(Exception):
    """Raised when a pipeline stage fails for a specific article.

    Attributes:
        stage: The pipeline stage that failed.
        message: Human-readable description of the failure.
        article_ref: Optional identifier of the affected article (e.g. "A").
        url: Optional URL of the affected article.
    """

    def __init__(
        self,
        stage: PipelineStage,
        message: str,
        *,
        article_ref: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.article_ref = article_ref
        self.url = url

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "message": self.message,
            "article_ref": self.article_ref,
            "url": self.url,
        }
