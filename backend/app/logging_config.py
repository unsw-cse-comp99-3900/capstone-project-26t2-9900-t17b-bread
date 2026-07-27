"""Structured logging configuration with in-memory ring buffer.

Provides:
- JSON or human-readable log format (controlled by LOG_FORMAT env var)
- In-memory ring buffer to expose recent logs via /debug/logs
- Correlation-ID propagation via contextvars
"""

from __future__ import annotations

import logging
import sys
import time
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_LOG_BUFFER: deque[dict[str, Any]] = deque(maxlen=500)


class RingBufferHandler(logging.Handler):
    """Append formatted log records to the in-memory ring buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record),
            "request_id": request_id_var.get(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        _LOG_BUFFER.append(entry)


class JSONFormatter(logging.Formatter):
    """Emit each log line as a single JSON object (for machine parsing)."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Readable coloured format for local development."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        rid = request_id_var.get()
        rid_tag = f" [{rid[:8]}]" if rid else ""
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%H:%M:%S.%f"
        )[:-3]
        msg = record.getMessage()
        base = f"{color}{ts} {record.levelname:<7}{self.RESET}{rid_tag} {record.name}: {msg}"
        if record.exc_info and record.exc_info[1]:
            base += f"\n  {self.formatException(record.exc_info)}"
        return base


def get_recent_logs(limit: int = 100, level: str | None = None) -> list[dict[str, Any]]:
    """Return the most recent log entries from the ring buffer."""
    entries = list(_LOG_BUFFER)
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]
    return entries[-limit:]


def setup_logging(*, log_level: str = "INFO", log_format: str = "human") -> None:
    """Configure the root logger with the chosen format and ring buffer."""
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # Remove any pre-existing handlers (uvicorn adds its own).
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level.upper())
    if log_format == "json":
        console.setFormatter(JSONFormatter())
    else:
        console.setFormatter(HumanFormatter())
    root.addHandler(console)

    # Ring buffer handler (always human-readable message)
    ring = RingBufferHandler()
    ring.setLevel(logging.DEBUG)
    ring.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(ring)

    # Quiet noisy third-party loggers
    for name in ("httpx", "httpcore", "watchfiles", "urllib3", "hpack", "filelock"):
        logging.getLogger(name).setLevel(logging.WARNING)
