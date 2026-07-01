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
        if percent is not None:
            self.percent = max(0, min(100, percent))
        if message is not None:
            self.message = message

        if step is not None:
            existing = next((s for s in self.steps if s.step == step and s.article_ref == article_ref), None)
            if existing is None:
                existing = ProgressStep(step=step, label=message or step, article_ref=article_ref)
                self.steps.append(existing)
            if message is not None:
                existing.label = message
            if status == "running" and existing.started_at is None:
                existing.started_at = time.perf_counter()
            if status in {"completed", "failed", "skipped"}:
                existing.completed_at = time.perf_counter()
            if status is not None:
                existing.status = status

        if self._callback is None:
            return

        payload = {
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
        total = self.elapsed_seconds
        message = final_message or f"Processing completed in {total} seconds."
        return {
            "total_elapsed_seconds": total,
            "message": message,
            "steps": [
                {
                    "step": step.step,
                    "label": step.label,
                    "status": step.status,
                    "elapsed_seconds": step.elapsed_seconds,
                    "article_ref": step.article_ref,
                }
                for step in self.steps
            ],
        }
