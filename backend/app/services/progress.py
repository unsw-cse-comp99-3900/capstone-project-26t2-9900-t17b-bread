"""Processing progress tracking for long-running article pipelines."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal


StepStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
]

ProgressCallback = Callable[
    [dict[str, Any]],
    Awaitable[None] | None,
]


# Informational only. ProgressTracker remains generic and does not reject
# unknown step names.
#
# The comparison-stage order now matches:
#
# cosine + BM25
#     -> base hybrid scoring
#     -> candidate cross mapping
#     -> bidirectional NLI
#     -> final cross mapping
#     -> relationship classification
#     -> focus scaling and factor ranking
KNOWN_PIPELINE_STEPS: frozenset[str] = frozenset(
    {
        # Overall lifecycle.
        "start",
        "comparison",
        "finalize",
        "complete",

        # Single-article processing.
        "article_input",
        "preprocessing",
        "summarization",
        "chunking",
        "embedding",

        # Pair-level comparison.
        "cosine_similarity",
        "bm25_scoring",
        "hybrid_scoring",
        "candidate_cross_mapping",
        "contradiction_detection",
        "final_cross_mapping",
        "relationship_classification",
        "focus_scaling",
    }
)


@dataclass
class ProgressStep:
    """State and timing information for one pipeline step."""

    step: str
    label: str
    status: StepStatus = "pending"
    article_ref: str | None = None
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def elapsed_seconds(self) -> float | None:
        """
        Return elapsed time for this step.

        A running step is measured against the current time. A completed,
        failed, or skipped step is measured against completed_at.
        """

        if self.started_at is None:
            return None

        end = (
            self.completed_at
            if self.completed_at is not None
            else time.perf_counter()
        )

        return round(
            max(0.0, end - self.started_at),
            2,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert one progress step into frontend-friendly data."""

        return {
            "step": self.step,
            "label": self.label,
            "status": self.status,
            "elapsed_seconds": self.elapsed_seconds,
            "article_ref": self.article_ref,
        }


@dataclass
class ProgressTracker:
    """
    Track elapsed time and emit progress events for the frontend.

    The tracker remains pipeline-agnostic. The article pipeline decides which
    step names and progress percentages to emit.

    Current pair-comparison stages include:

        cosine_similarity
        bm25_scoring
        hybrid_scoring
        candidate_cross_mapping
        contradiction_detection
        final_cross_mapping
        relationship_classification
        focus_scaling
    """

    name: str = "processing"
    started_at: float = field(
        default_factory=time.perf_counter
    )
    percent: int = 0
    message: str = "Starting article processing..."
    steps: list[ProgressStep] = field(
        default_factory=list
    )

    _callback: ProgressCallback | None = field(
        default=None,
        repr=False,
    )

    def bind(
        self,
        callback: ProgressCallback | None,
    ) -> ProgressTracker:
        """Attach the callback used by SSE streaming."""

        self._callback = callback
        return self

    @property
    def elapsed_seconds(self) -> float:
        """Return total elapsed processing time."""

        return round(
            max(
                0.0,
                time.perf_counter()
                - self.started_at,
            ),
            2,
        )

    async def emit(
        self,
        *,
        percent: int | None = None,
        message: str | None = None,
        step: str | None = None,
        article_ref: str | None = None,
        status: StepStatus | None = None,
    ) -> None:
        """
        Update tracker state and optionally emit an event to the frontend.

        Examples of current comparison steps:

            hybrid_scoring
                Calculates only base_hybrid_score.

            candidate_cross_mapping
                Builds permissive candidate mappings and mapping_score.

            contradiction_detection
                Runs bidirectional NLI on candidate mappings.

            final_cross_mapping
                Applies normal mapping or contradiction rescue and strict 1v1
                final selection.

            relationship_classification
                Assigns aligned, partially_aligned, or divergent.

            focus_scaling
                Adds factor_relevance_score and factor-based display ranking
                after relationship classification.

        Unknown step names remain valid because this tracker is generic.
        """

        if percent is not None:
            self.percent = self._clamp_percent(
                percent
            )

        if message is not None:
            self.message = str(message)

        if step is not None:
            self._update_step(
                step=str(step),
                label=(
                    str(message)
                    if message is not None
                    else str(step)
                ),
                article_ref=article_ref,
                status=status,
            )

        if self._callback is None:
            return

        payload = {
            "name": self.name,
            "percent": self.percent,
            "message": self.message,
            "elapsed_seconds": self.elapsed_seconds,
            "step": step,
            "article_ref": article_ref,
            "status": status,
        }

        result = self._callback(payload)

        if result is not None:
            await result

    def to_summary(
        self,
        *,
        final_message: str | None = None,
    ) -> dict[str, Any]:
        """
        Convert progress tracking data into a response summary.

        The output preserves the existing frontend structure.
        """

        total = self.elapsed_seconds

        message = (
            final_message
            or self.message
            or (
                "Processing completed in "
                f"{total} seconds."
            )
        )

        return {
            "total_elapsed_seconds": total,
            "message": message,
            "steps": [
                step.to_dict()
                for step in self.steps
            ],
        }

    def _update_step(
        self,
        *,
        step: str,
        label: str,
        article_ref: str | None,
        status: StepStatus | None,
    ) -> None:
        """Create or update one tracked processing step."""

        existing = self._find_step(
            step=step,
            article_ref=article_ref,
        )

        if existing is None:
            existing = ProgressStep(
                step=step,
                label=label,
                article_ref=article_ref,
            )
            self.steps.append(existing)

        existing.label = label

        now = time.perf_counter()

        if (
            status == "running"
            and existing.started_at is None
        ):
            existing.started_at = now

        if status in {
            "completed",
            "failed",
            "skipped",
        }:
            # Keep elapsed time valid even when a caller emits a terminal status
            # without first emitting "running".
            if existing.started_at is None:
                existing.started_at = now

            existing.completed_at = now

        if status is not None:
            existing.status = status

    def _find_step(
        self,
        *,
        step: str,
        article_ref: str | None,
    ) -> ProgressStep | None:
        """
        Find an existing step by step name and article reference.

        Comparison steps normally have article_ref=None. Per-article steps are
        tracked separately for Article A and Article B.
        """

        return next(
            (
                item
                for item in self.steps
                if (
                    item.step == step
                    and item.article_ref
                    == article_ref
                )
            ),
            None,
        )

    def _clamp_percent(
        self,
        percent: int,
    ) -> int:
        """Keep progress percentage inside 0-100."""

        try:
            numeric_percent = int(percent)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "percent must be an integer."
            ) from exc

        return max(
            0,
            min(
                100,
                numeric_percent,
            ),
        )