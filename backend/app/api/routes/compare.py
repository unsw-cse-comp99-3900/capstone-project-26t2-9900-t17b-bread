"""Compare Controller (proposal p.19-20)."""

from __future__ import annotations

import asyncio
import logging

import os
import json
import uuid

from app.db import dal
from app.db.base import _normalize_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = os.getenv(
        "SQLALCHEMY_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres"
    )

engine = create_engine(_normalize_url(DATABASE_URL))

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.compare import CompareRequest, CompareResponse, ComparisonFocus
from app.services.article_input import ArticleInput
from app.services.pipeline import (
    ArticleResult,
    PairPipelineResult,
    process_pair_inputs_with_comparison,
)
from app.services.progress import ProgressTracker
from app.services.streaming import streaming_response_from_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compare", tags=["compare"])


def _compare_response_fields() -> set[str]:
    """Return fields supported by CompareResponse."""

    fields = getattr(CompareResponse, "model_fields", None)

    if fields is None:
        fields = getattr(CompareResponse, "__fields__", {})

    return set(fields.keys())


def _build_stage_error(result: ArticleResult) -> dict[str, Any] | None:
    """Convert a failed ArticleResult into API error payload."""

    if result.error is None:
        return None

    if hasattr(result.error, "to_dict"):
        return result.error.to_dict()

    return {
        "stage": "unknown",
        "code": None,
        "message": str(result.error),
        "article_ref": result.article_ref,
        "url": result.url,
    }


def _relationship_explanation(
    relationship: dict[str, Any],
) -> str:
    """Create a simple explanation for frontend display."""

    label = relationship.get("label")
    reason_code = relationship.get("reason_code")

    if label == "aligned":
        if reason_code == "strong_similarity_with_nli_entailment":
            return (
                "These paragraph chunks present strongly consistent content, "
                "supported by semantic similarity, lexical overlap, and NLI "
                "entailment evidence."
            )

        return (
            "These paragraph chunks discuss highly similar content with "
            "strong semantic and lexical support."
        )

    if label == "partially_aligned":
        if reason_code == "semantic_match_with_lexical_difference":
            return (
                "These paragraph chunks discuss related content, but use "
                "different wording or emphasize different details."
            )

        if reason_code == "lexical_overlap_with_semantic_difference":
            return (
                "These paragraph chunks share important terms or entities, "
                "but differ in semantic meaning or framing."
            )

        if reason_code == "related_content_with_nli_neutrality":
            return (
                "These paragraph chunks discuss related content, but neither "
                "clearly support nor contradict each other."
            )

        return (
            "These paragraph chunks are related, but differ in emphasis, "
            "detail, or framing."
        )

    if label == "divergent":
        return (
            "These paragraph chunks discuss the same or closely related "
            "subject, but contain strong contradiction evidence."
        )

    return (
        "These paragraph chunks do not contain enough shared content for "
        "a reliable relationship classification."
    )


def _build_frontend_matches(pair_result: PairPipelineResult) -> list[dict[str, Any]]:
    """
    Convert backend relationship results into chunk-level frontend matches.

    The comparison unit is paragraph chunk, not sentence.
    """

    if pair_result.comparison is None:
        return []

    matches: list[dict[str, Any]] = []

    for index, relationship in enumerate(pair_result.comparison.relationships):
        a_chunk_id = relationship.get("a_chunk_id")
        b_chunk_id = relationship.get("b_chunk_id")

        if not a_chunk_id or not b_chunk_id:
            continue

        mapping_score = relationship.get("mapping_score")
        hybrid_score = relationship.get("hybrid_score")
        base_hybrid_score = relationship.get("base_hybrid_score")

        score = float(hybrid_score) if hybrid_score is not None else 0.0
        
        matches.append(
            {
                "id": f"{a_chunk_id}-{b_chunk_id}-{index}",
                "a_chunk_id": a_chunk_id,
                "b_chunk_id": b_chunk_id,
                "a_paragraph_index": relationship.get("a_paragraph_index"),
                "b_paragraph_index": relationship.get("b_paragraph_index"),
                "a_chunk_index": relationship.get("a_chunk_index"),
                "b_chunk_index": relationship.get("b_chunk_index"),
                "label": relationship.get("label", "partially_aligned"),
                "score": float(score),
                "confidence": relationship.get("confidence", "medium"),
                "reason_code": relationship.get("reason_code"),
                "explanation": _relationship_explanation(relationship),
                "a_text_preview": relationship.get("a_text_preview"),
                "b_text_preview": relationship.get("b_text_preview"),
                "pair_number": relationship.get("pair_number"),
            }
        )

    return matches


def _build_comparison_payload(
    pair_result: PairPipelineResult,
) -> dict[str, Any] | None:
    """
    Convert internal comparison result into final frontend comparison output.

    Only visible relationships are returned:
        aligned
        partially_aligned
        divergent
    """

    if pair_result.comparison is None:
        return None

    comparison = pair_result.comparison
    matches = _build_frontend_matches(pair_result)

    return {
        "focus": comparison.focus,
        "summary": {
            "match_count": len(matches),
            "aligned_count": sum(
                1
                for match in matches
                if match.get("label") == "aligned"
            ),
            "partially_aligned_count": sum(
                1
                for match in matches
                if match.get("label") == "partially_aligned"
            ),
            "divergent_count": sum(
                1
                for match in matches
                if match.get("label") == "divergent"
            ),
        },
        "matches": matches,
        "comparison_summary": comparison.comparison_summary,
    }


def _build_frontend_article(result: ArticleResult) -> dict[str, Any] | None:
    """
    Convert internal ArticleResult into a clean frontend article payload.

    Internal fields such as sentences, paragraph_chunks and embeddings
    are intentionally excluded.
    """

    article = result.article

    if article is None:
        return None

    # Support both Pydantic objects and dictionaries.
    if isinstance(article, dict):
        article_ref = article.get("article_ref", result.article_ref)
        url = article.get("url", result.url)
        title = article.get("title")
        source_domain = article.get("source_domain")
        source_type = article.get("source_type")
        paragraphs = article.get("paragraphs", [])
        summary = article.get("summary", [])
    else:
        article_ref = getattr(article, "article_ref", result.article_ref)
        url = getattr(article, "url", result.url)
        title = getattr(article, "title", None)
        source_domain = getattr(article, "source_domain", None)
        source_type = getattr(article, "source_type", None)
        paragraphs = getattr(article, "paragraphs", [])
        summary = getattr(article, "summary", [])

    return {
        "article_ref": article_ref,
        "url": url,
        "title": title,
        "source_domain": source_domain,
        "source_type": source_type,
        "paragraphs": paragraphs or [],
        "summary": summary or [],
    }

def _build_compare_response(
    *,
    focus: ComparisonFocus,
    pair_result: PairPipelineResult,
    progress: ProgressTracker | None = None,
    session_token: str | None = None,
) -> CompareResponse:
    """Build CompareResponse for all compare endpoints."""

    article_results = pair_result.articles

    articles = [
        article_payload
        for result in article_results
        if (article_payload := _build_frontend_article(result)) is not None
    ]

    errors = [
        error_payload
        for result in article_results
        if (error_payload := _build_stage_error(result)) is not None
    ]

    response_data: dict[str, Any] = {
        "focus": focus,
        "articles": articles,
        "errors": errors,

        "relevant": pair_result.relevant,
        "relevance_score": pair_result.relevance_score,
        "cosine_relevance_score": pair_result.cosine_relevance_score,
        "bm25_relevance_score": pair_result.bm25_relevance_score,
        "relevance_threshold": pair_result.relevance_threshold,
        "message": pair_result.message,

        "comparison": _build_comparison_payload(pair_result),
        "session_token": session_token,
    }

    supported_fields = _compare_response_fields()

    if progress is not None:
        progress_summary = progress.to_summary(
            final_message="Comparison finished."
        )

        if "processing" in supported_fields:
            response_data["processing"] = progress_summary
        elif "progress" in supported_fields:
            response_data["progress"] = progress_summary

    if supported_fields:
        response_data = {
            key: value
            for key, value in response_data.items()
            if key in supported_fields
        }

    return CompareResponse(**response_data)


async def _build_article_input(
    article_ref: str,
    url: str | None,
    text: str | None,
    upload: UploadFile | None,
) -> ArticleInput:
    """Build ArticleInput from a URL, pasted text, or an uploaded file."""

    url_value = (url or "").strip()
    text_value = (text or "").strip()
    has_file = upload is not None and upload.filename

    provided = sum(1 for value in (url_value, text_value, has_file) if value)

    if provided > 1:
        raise ValueError(
            f"Provide only one of URL, text, or file for article {article_ref}."
        )

    if provided == 0:
        raise ValueError(
            f"Article {article_ref} is missing. Provide a URL, pasted text, "
            "or upload a PDF/Word file."
        )

    if has_file:
        content = await upload.read()
        return ArticleInput.from_upload(
            content,
            upload.filename,
            article_ref,
        )

    if text_value:
        return ArticleInput.from_text(
            text_value,
            article_ref,
        )

    return ArticleInput.from_url(
        url_value,
        article_ref,
    )


def _build_json_article_inputs(payload: CompareRequest) -> tuple[ArticleInput, ArticleInput]:
    """Build ArticleInput objects from the JSON payload (URL or pasted text)."""

    return (
        _build_json_article_input("A", payload.article_a_url, payload.article_a_text),
        _build_json_article_input("B", payload.article_b_url, payload.article_b_text),
    )


def _build_json_article_input(
    article_ref: str,
    url: str | None,
    text: str | None,
) -> ArticleInput:
    """Prefer pasted text over URL for one article in a JSON request."""

    if (text or "").strip():
        return ArticleInput.from_text(text, article_ref)

    return ArticleInput.from_url(url, article_ref)


async def _run_compare_inputs(
    article_a: ArticleInput,
    article_b: ArticleInput,
    focus: ComparisonFocus,
    *,
    progress: ProgressTracker | None = None,
) -> CompareResponse:
    """
    Shared core controller logic.

    All four endpoints eventually call this function.
    """

    pair_result = await process_pair_inputs_with_comparison(
        article_a,
        article_b,
        focus=focus,
        progress=progress,
    )
    
    session_token = str(uuid.uuid4())

    frontend_matches = _build_frontend_matches(pair_result)
    scores = [m.get("score", 0.0) for m in frontend_matches]
    similarity_score = sum(scores) / len(scores) if scores else 0.0

    try:
        with engine.begin() as conn:
            article_db_ids = {}
            for res in pair_result.articles:
                if res.article is None:
                    continue

                art = res.article
                title = art.get("title") if isinstance(art, dict) else getattr(art, "title", None)
                url = art.get("url", res.url) if isinstance(art, dict) else getattr(art, "url", res.url)
                source_domain = art.get("source_domain") if isinstance(art, dict) else getattr(art, "source_domain", None)

                paragraphs = art.get("paragraphs", []) if isinstance(art, dict) else getattr(art, "paragraphs", [])
                main_body = "\n\n".join(paragraphs) if paragraphs else "No content available."

                tgt_url = url or f"pasted_text_{res.article_ref.lower()}_{session_token[:8]}"
                tgt_title = title or f"Pasted Article {res.article_ref}"
                tgt_domain = source_domain or "local.pasted"

                current_art_id = dal.insert_article(conn, tgt_url, tgt_title, tgt_domain, main_body)
                article_db_ids[res.article_ref] = current_art_id

                chunks = res.paragraph_chunks or []
                embeddings_by_chunk_id = {
                    item.get("chunk_id"): item
                    for item in (res.chunk_embeddings or [])
                }

                for idx, chunk in enumerate(chunks):
                    chunk_text = chunk.get("text", "") if isinstance(chunk, dict) else getattr(chunk, "text", "")
                    if not chunk_text:
                        continue

                    chunk_id = dal.insert_chunk(conn, current_art_id, idx, chunk_text)

                    chunk_key = chunk.get("chunk_id") if isinstance(chunk, dict) else getattr(chunk, "chunk_id", None)
                    embedding_item = embeddings_by_chunk_id.get(chunk_key)

                    if chunk_id and embedding_item:
                        vector = embedding_item.get("embedding")
                        if vector:
                            dal.insert_embedding(
                                conn,
                                chunk_id,
                                vector,
                                embedding_item.get("model_name"),
                            )

            db_id_a = article_db_ids.get("A")
            db_id_b = article_db_ids.get("B")

            if db_id_a and db_id_b:
                result_payload = {
                    "matches": frontend_matches,
                    "similarity_score": round(similarity_score, 2),
                    "session_token": session_token
                }
                
                comparison_id = dal.insert_comparison_result(conn, db_id_a, db_id_b, result_payload)
                
                if comparison_id:
                    dal.insert_history(conn, comparison_id)
                    logger.info(f"[DB Sync] Automatically logged history for comparison ID: {comparison_id}")
                
        logger.info("[DB Sync Success] Sprint 2 pipeline alignment successfully coordinated.")
        
    except Exception as db_err:
        logger.critical(f"[CRITICAL DB ERROR]: {db_err}")
        session_token = f"fallback-{uuid.uuid4()}"

    return _build_compare_response(
        focus=focus,
        pair_result=pair_result,
        progress=progress,
        session_token=session_token,
    )


@router.post(
    "",
    response_model=CompareResponse,
    summary="Compare a pair of articles from URLs and/or pasted text",
)
async def compare(
    payload: CompareRequest,
) -> CompareResponse:
    """
    URL and/or pasted-text comparison.

    Request type:
    JSON

    Response type:
    normal JSON
    """

    article_a, article_b = _build_json_article_inputs(payload)

    progress = ProgressTracker(name="compare")

    return await _run_compare_inputs(
        article_a,
        article_b,
        payload.focus,
        progress=progress,
    )


@router.post(
    "/stream",
    summary="Compare two articles (URL and/or pasted text) with live English progress (SSE)",
)
async def compare_stream(
    payload: CompareRequest,
):
    """
    URL and/or pasted-text comparison.

    Request type:
    JSON

    Response type:
    SSE stream
    """

    progress_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_progress(event: dict) -> None:
        await progress_queue.put(event)

    progress = ProgressTracker(name="compare").bind(on_progress)

    async def runner() -> dict:
        try:
            article_a, article_b = _build_json_article_inputs(payload)

            response = await _run_compare_inputs(
                article_a,
                article_b,
                payload.focus,
                progress=progress,
            )

            return response.model_dump(exclude_none=True)
        finally:
            await progress_queue.put(None)

    return streaming_response_from_progress(
        runner,
        progress_queue=progress_queue,
    )


@router.post(
    "/files",
    response_model=CompareResponse,
    summary="Compare two articles from URLs, pasted text, and/or uploaded PDF/Word files",
)
async def compare_files(
    article_a_url: str | None = Form(default=None),
    article_b_url: str | None = Form(default=None),
    article_a_text: str | None = Form(default=None),
    article_b_text: str | None = Form(default=None),
    article_a_file: UploadFile | None = File(default=None),
    article_b_file: UploadFile | None = File(default=None),
    focus: ComparisonFocus = Form(default=ComparisonFocus.GENERAL),
) -> CompareResponse:
    """
    Mixed URL / pasted-text / file comparison.

    Request type:
    multipart/form-data

    Response type:
    normal JSON
    """

    try:
        article_a = await _build_article_input(
            "A",
            article_a_url,
            article_a_text,
            article_a_file,
        )

        article_b = await _build_article_input(
            "B",
            article_b_url,
            article_b_text,
            article_b_file,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    progress = ProgressTracker(name="compare")

    return await _run_compare_inputs(
        article_a,
        article_b,
        focus,
        progress=progress,
    )


@router.post(
    "/files/stream",
    summary="Compare mixed URL / pasted-text / file inputs with live English progress (SSE)",
)
async def compare_files_stream(
    article_a_url: str | None = Form(default=None),
    article_b_url: str | None = Form(default=None),
    article_a_text: str | None = Form(default=None),
    article_b_text: str | None = Form(default=None),
    article_a_file: UploadFile | None = File(default=None),
    article_b_file: UploadFile | None = File(default=None),
    focus: ComparisonFocus = Form(default=ComparisonFocus.GENERAL),
):
    """
    Mixed URL / pasted-text / file comparison.

    Request type:
    multipart/form-data

    Response type:
    SSE stream
    """

    try:
        article_a = await _build_article_input(
            "A",
            article_a_url,
            article_a_text,
            article_a_file,
        )

        article_b = await _build_article_input(
            "B",
            article_b_url,
            article_b_text,
            article_b_file,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    progress_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_progress(event: dict) -> None:
        await progress_queue.put(event)

    progress = ProgressTracker(name="compare").bind(on_progress)

    async def runner() -> dict:
        try:
            response = await _run_compare_inputs(
                article_a,
                article_b,
                focus,
                progress=progress,
            )

            return response.model_dump(exclude_none=True)
        finally:
            await progress_queue.put(None)

    return streaming_response_from_progress(
        runner,
        progress_queue=progress_queue,
    )