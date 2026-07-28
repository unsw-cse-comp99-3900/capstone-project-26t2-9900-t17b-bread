"""User comparison history routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine

from app.api.routes.auth import DATABASE_URL, get_current_user_from_header
from app.db import dal
from app.db.base import _normalize_url

engine = create_engine(_normalize_url(DATABASE_URL))

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
