"""User comparison history routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine

from app.api.routes.auth import DATABASE_URL, get_current_user_from_header
from app.db import dal
from app.db.base import _normalize_url

"""
User Comparison History Routes — High-Level Overview
----------------------------------------------------

This module provides the API endpoints that allow authenticated users to
save, list, and manage their personal comparison history. It acts as the
interface between:

    • The authentication system (session-token based)
    • The comparison result storage layer
    • The React frontend’s history panel

Key Responsibilities
--------------------
1. Authenticated Access
   - All routes require a valid session token.
   - Uses get_current_user_from_header() to enforce login and prevent
     cross-user access to history items.

2. History Listing
   - Retrieves all comparison results saved by the current user.
   - Converts raw database rows into structured, frontend-ready objects
     including titles, labels, focus, and comparison payload.

3. History Saving
   - Allows users to save a previously computed comparison result.
   - Validates that the comparison exists before saving.
   - Returns the newly saved item in a consistent shape.

4. History Deletion
   - Supports deleting a single history item or clearing all history
     for the authenticated user.
   - Ensures users can only delete their own history entries.

5. Payload Normalisation
   - _history_item() transforms stored JSON into a stable, predictable
     response format for the frontend.
   - Extracts article titles, focus mode, and comparison summary for
     display in the history list.

Architectural Role
------------------
This controller provides a simple persistence layer for user-specific
comparison results. It does not perform any NLP or comparison logic; instead,
it stores and retrieves the outputs produced by the Compare Controller.

By isolating history management in its own module, the system maintains:

    • Clear separation of concerns
    • Secure, user-scoped access to saved results
    • A clean API surface for the frontend’s history sidebar
    • Consistent formatting of saved comparison entries

The history system is intentionally lightweight: it stores only the final
comparison payload and metadata, allowing users to revisit past comparisons
without recomputing the NLP pipeline.
"""

# Force sync driver for SQLAlchemy
sync_url = DATABASE_URL

# Strip async driver prefixes
sync_url = sync_url.replace("postgresql+psycopg://", "postgresql://")
sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(sync_url)

router = APIRouter(prefix="/api/history", tags=["history"])


class SaveHistoryRequest(BaseModel):
    comparison_id: int


def _history_item(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("result_json") or {}
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)

    articles = payload.get("articles") or []
    comparison = payload.get("comparison")
    focus = payload.get("focus") or (
        comparison.get("focus") if isinstance(comparison, dict) else "general"
    )

    title_a = _article_title(articles, "A", "Article A")
    title_b = _article_title(articles, "B", "Article B")

    return {
        "id": str(row["history_id"]),
        "history_id": row["history_id"],
        "comparison_id": row["id"],
        "saved_at": row["saved_at"].isoformat() if row.get("saved_at") else None,
        "focus": focus,
        "label": f"{title_a} vs {title_b}",
        "description": f"{focus} - saved result",
        "articles": articles,
        "comparison": comparison,
    }


def _article_title(articles: list[dict[str, Any]], ref: str, fallback: str) -> str:
    for article in articles:
        if article.get("article_ref") == ref:
            return article.get("title") or article.get("source_domain") or fallback
    return fallback


@router.get("")
async def list_history(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = get_current_user_from_header(authorization)
    with engine.begin() as conn:
        rows = dal.get_history(conn, int(user["id"]))
    return {"items": [_history_item(row) for row in rows]}


@router.post("")
async def save_history(
    payload: SaveHistoryRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = get_current_user_from_header(authorization)
    with engine.begin() as conn:
        comparison = dal.get_comparison_result(conn, payload.comparison_id)
        if comparison is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comparison result was not found.",
            )
        history_id = dal.insert_history(conn, payload.comparison_id, int(user["id"]))
        row = dal.get_history(conn, int(user["id"]))

    saved = next((item for item in row if item["history_id"] == history_id), None)
    return {"item": _history_item(saved) if saved else None}


@router.delete("/{history_id}")
async def delete_history(
    history_id: int,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    user = get_current_user_from_header(authorization)
    with engine.begin() as conn:
        dal.delete_history_item(conn, history_id, int(user["id"]))
    return {"status": "ok"}


@router.delete("")
async def clear_history(authorization: str | None = Header(default=None)) -> dict[str, str]:
    user = get_current_user_from_header(authorization)
    with engine.begin() as conn:
        dal.clear_history(conn, int(user["id"]))
    return {"status": "ok"}
