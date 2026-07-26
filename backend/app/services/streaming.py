"""Helpers for SSE progress streaming."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi.responses import StreamingResponse


def sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_with_progress(
    runner: Callable[[], Awaitable[Any]],
    *,
    progress_queue: asyncio.Queue[dict[str, Any] | None],
) -> AsyncIterator[str]:
    """Yield SSE progress events, then a terminal ``result`` (or ``error``) event.

    The runner is expected to always push ``None`` into ``progress_queue`` when it
    finishes (usually via ``finally``). If the runner raises, we still emit a
    terminal ``error`` event so the client stops waiting instead of hanging.
    """
    task = asyncio.create_task(runner())

    while True:
        item = await progress_queue.get()
        if item is None:
            break
        yield sse_event("progress", item)

    try:
        result = await task
    except Exception as exc:  # noqa: BLE001 - surface any runner failure to client
        yield sse_event(
            "error",
            {
                "message": (
                    "The server could not complete the request. "
                    f"{type(exc).__name__}: {exc}"
                ),
            },
        )
        return

    yield sse_event("result", result)


def streaming_response_from_progress(
    runner: Callable[[], Awaitable[dict[str, Any]]],
    *,
    progress_queue: asyncio.Queue[dict[str, Any] | None],
) -> StreamingResponse:
    return StreamingResponse(
        stream_with_progress(runner, progress_queue=progress_queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
