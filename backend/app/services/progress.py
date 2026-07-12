"""Processing progress tracking for long-running article pipelines."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass
class ProgressStep:
    step: str
    label: str
    status: StepStatus = "pending"
    article_ref: str | None = None
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def elapsed_seconds(self) -> float | None:
        if self.started_at is None:
            return None

        end = self.completed_at if self.completed_at is not None else time.perf_counter()
        return round(end - self.started_at, 2)

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
    """Tracks elapsed time and emits English progress events for the frontend."""

    name: str = "processing"
    started_at: float = field(default_factory=time.perf_counter)
    percent: int = 0
    message: str = "Starting article processing..."
    steps: list[ProgressStep] = field(default_factory=list)
    _callback: ProgressCallback | None = field(default=None, repr=False)

    def bind(self, callback: ProgressCallback | None) -> ProgressTracker:
        """Attach a callback used by SSE streaming."""
        self._callback = callback
        return self

    @property
    def elapsed_seconds(self) -> float:
        return round(time.perf_counter() - self.started_at, 2)

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
        Update progress state and optionally emit an event to the frontend.

        This tracker is generic. The pipeline decides which step names to emit,
        such as preprocessing, embedding, cosine_similarity, bm25_scoring,
        hybrid_scoring, cross_mapping, or relationship_classification.
        """

        if percent is not None:
            self.percent = self._clamp_percent(percent)

        if message is not None:
            self.message = message

        if step is not None:
            self._update_step(
                step=step,
                label=message or step,
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

    def to_summary(self, *, final_message: str | None = None) -> dict[str, Any]:
        """
        Convert progress tracking data into a response summary.

        This output should match the frontend progress summary structure.
        """
        total = self.elapsed_seconds
        message = final_message or self.message or f"Processing completed in {total} seconds."

        return {
            "total_elapsed_seconds": total,
            "message": message,
            "steps": [step.to_dict() for step in self.steps],
        }

    def _update_step(
        self,
        *,
        step: str,
        label: str,
        article_ref: str | None,
        status: StepStatus | None,
    ) -> None:
        """Create or update a tracked processing step."""

        existing = self._find_step(step=step, article_ref=article_ref)

        if existing is None:
            existing = ProgressStep(
                step=step,
                label=label,
                article_ref=article_ref,
            )
            self.steps.append(existing)

        existing.label = label

        if status == "running" and existing.started_at is None:
            existing.started_at = time.perf_counter()

        if status in {"completed", "failed", "skipped"}:
            existing.completed_at = time.perf_counter()

        if status is not None:
            existing.status = status

    def _find_step(
        self,
        *,
        step: str,
        article_ref: str | None,
    ) -> ProgressStep | None:
        """Find an existing step by step name and article reference."""

        return next(
            (
                item
                for item in self.steps
                if item.step == step and item.article_ref == article_ref
            ),
            None,
        )

    def _clamp_percent(self, percent: int) -> int:
        """Keep progress percentage inside 0-100."""
        return max(0, min(100, percent))