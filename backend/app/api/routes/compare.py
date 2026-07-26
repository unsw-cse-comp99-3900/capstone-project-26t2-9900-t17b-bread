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


def _build_nlp_debug(result: ArticleResult) -> dict[str, Any] | None:
    """
    Build lightweight NLP debug information.

    This does not return full embedding vectors.
    """

    if not result.ok:
        return None

    paragraph_chunks = result.paragraph_chunks or []
    chunk_embeddings = result.chunk_embeddings or []

    chunks: list[dict[str, Any]] = []

    for chunk in paragraph_chunks:
        text = str(chunk.get("text", "")).strip()

        chunks.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "article_ref": chunk.get("article_ref", result.article_ref),
                "chunk_type": chunk.get("chunk_type", "paragraph"),
                "chunk_index": chunk.get("chunk_index"),
                "paragraph_index": chunk.get("paragraph_index"),
                "text_preview": text[:200],
                "word_count": chunk.get("word_count"),
                "sentence_ids": chunk.get("sentence_ids", []),
                "char_start": chunk.get("char_start"),
                "char_end": chunk.get("char_end"),
            }
        )

    embeddings: list[dict[str, Any]] = []

    for item in chunk_embeddings:
        vector = item.get("embedding") or []

        if not isinstance(vector, list):
            vector = []

        dimension = item.get("dimension")
        vector_length = len(vector)

        embeddings.append(
            {
                "chunk_id": item.get("chunk_id"),
                "article_ref": item.get("article_ref", result.article_ref),
                "model_name": item.get("model_name"),
                "dimension": dimension,
                "vector_length": vector_length,
                "vector_preview": vector[:5],
                "ok": vector_length > 0 and dimension == vector_length,
            }
        )

    embedding_ready = (
        len(paragraph_chunks) > 0
        and len(paragraph_chunks) == len(chunk_embeddings)
        and all(item["ok"] for item in embeddings)
    )

    return {
        "article_ref": result.article_ref,
        "chunk_count": len(paragraph_chunks),
        "embedding_count": len(chunk_embeddings),
        "embedding_ready": embedding_ready,
        "chunks": chunks,
        "embeddings": embeddings,
    }


def _relationship_explanation(relationship: dict[str, Any]) -> str:
    """Create a simple explanation for frontend display."""

    label = relationship.get("label")
    reason_code = relationship.get("reason_code")

    if label == "aligned":
        return (
            "These paragraph chunks discuss highly similar content with strong "
            "semantic and lexical support."
        )

    if label == "partially_aligned":
        if reason_code == "semantic_match_with_lexical_difference":
            return (
                "These paragraph chunks discuss related content, but use different "
                "wording or emphasize different details."
            )

        if reason_code == "lexical_overlap_with_semantic_difference":
            return (
                "These paragraph chunks share important terms or entities, but "
                "frame the issue differently."
            )

        return (
            "These paragraph chunks are related, but differ in emphasis, detail, "
            "or framing."
        )

    return (
        "These paragraph chunks are weakly related or show a clear difference "
        "in coverage."
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

        score = (
            relationship.get("mapping_score")
            or relationship.get("hybrid_score")
            or relationship.get("base_hybrid_score")
            or 0.0
        )

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
            }
        )

    return matches


def _build_comparison_payload(pair_result: PairPipelineResult) -> dict[str, Any] | None:
    """
    Convert internal comparison result into final frontend comparison output.

    This only returns the final comparison result.
    It does not return debug scores or intermediate pipeline outputs.
    """

    if pair_result.comparison is None:
        return None

    comparison = pair_result.comparison
    matches = _build_frontend_matches(pair_result)

    return {
        "focus": comparison.focus,
        "summary": {
            "match_count": len(matches),
        },
        "matches": matches,
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
        result.article
        for result in article_results
        if result.article is not None
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
        "comparison": _build_comparison_payload(pair_result),
        "session_token": session_token,
    }

    supported_fields = _compare_response_fields()

    if progress is not None:
        progress_summary = progress.to_summary(
            final_message="Comparison finished."
        )

        if "progress" in supported_fields:
            response_data["progress"] = progress_summary
        elif "processing" in supported_fields:
            response_data["processing"] = progress_summary

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
    upload: UploadFile | None,
) -> ArticleInput:
    """Build ArticleInput from either URL or uploaded file."""

    url_value = (url or "").strip()
    has_file = upload is not None and upload.filename

    if url_value and has_file:
        raise ValueError(
            f"Provide either a URL or a file for article {article_ref}, not both."
        )

    if not url_value and not has_file:
        raise ValueError(
            f"Article {article_ref} is missing. Provide a URL or upload a PDF/Word file."
        )

    if has_file:
        content = await upload.read()
        return ArticleInput.from_upload(
            content,
            upload.filename,
            article_ref,
        )

    return ArticleInput.from_url(
        url_value,
        article_ref,
    )


def _build_url_article_inputs(payload: CompareRequest) -> tuple[ArticleInput, ArticleInput]:
    """Build ArticleInput objects from the URL-only JSON payload."""

    article_a = ArticleInput.from_url(
        payload.article_a_url,
        "A",
    )

    article_b = ArticleInput.from_url(
        payload.article_b_url,
        "B",
    )

    return article_a, article_b


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
    alignment_matrix_json = json.dumps(frontend_matches)
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

                chunks = art.get("paragraph_chunks", []) if isinstance(art, dict) else getattr(art, "paragraph_chunks", [])
                
                if chunks:
                    from sentence_transformers import SentenceTransformer
                    try:
                        local_model = SentenceTransformer("all-MiniLM-L6-v2", model_kwargs={"low_cpu_mem_usage": False})
                    except Exception as mod_err:
                        logger.error(f"Failed to initialize embedding model: {mod_err}")
                        local_model = None
                    
                    for idx, chunk in enumerate(chunks):
                        chunk_text = chunk.get("text", "") if isinstance(chunk, dict) else getattr(chunk, "text", "")
                        if not chunk_text:
                            continue
                        
                        chunk_id = dal.insert_chunk(conn, current_art_id, idx, chunk_text)
                        
                        if local_model and chunk_id:
                            try:
                                chunk_emb = local_model.encode([chunk_text])[0]
                                if hasattr(chunk_emb, "tolist"):
                                    chunk_emb = chunk_emb.tolist()
                                dal.insert_embedding(conn, chunk_id, chunk_emb, "all-MiniLM-L6-v2")
                            except Exception as enc_err:
                                logger.error(f"Chunk embedding encoding failed: {enc_err}")

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


@router.post("", response_model=CompareResponse, summary="Compare a pair of article URLs")
async def compare(
    payload: CompareRequest,
) -> CompareResponse:
    """
    URL-only comparison.

    Request type:
    JSON

    Response type:
    normal JSON
    """

    article_a, article_b = _build_url_article_inputs(payload)

    progress = ProgressTracker(name="compare")

    return await _run_compare_inputs(
        article_a,
        article_b,
        payload.focus,
        progress=progress,
    )


@router.post("/stream", summary="Compare two URLs with live English progress (SSE)")
async def compare_stream(
    payload: CompareRequest,
):
    """
    URL-only comparison.

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
            article_a, article_b = _build_url_article_inputs(payload)

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
    summary="Compare two articles from URLs and/or uploaded PDF/Word files",
)
async def compare_files(
    article_a_url: str | None = Form(default=None),
    article_b_url: str | None = Form(default=None),
    article_a_file: UploadFile | None = File(default=None),
    article_b_file: UploadFile | None = File(default=None),
    focus: ComparisonFocus = Form(default=ComparisonFocus.GENERAL),
) -> CompareResponse:
    """
    Mixed URL/file comparison.

    Request type:
    multipart/form-data

    Response type:
    normal JSON
    """

    try:
        article_a = await _build_article_input(
            "A",
            article_a_url,
            article_a_file,
        )

        article_b = await _build_article_input(
            "B",
            article_b_url,
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
    summary="Compare mixed URL/file inputs with live English progress (SSE)",
)
async def compare_files_stream(
    article_a_url: str | None = Form(default=None),
    article_b_url: str | None = Form(default=None),
    article_a_file: UploadFile | None = File(default=None),
    article_b_file: UploadFile | None = File(default=None),
    focus: ComparisonFocus = Form(default=ComparisonFocus.GENERAL),
):
    """
    Mixed URL/file comparison.

    Request type:
    multipart/form-data

    Response type:
    SSE stream
    """

    try:
        article_a = await _build_article_input(
            "A",
            article_a_url,
            article_a_file,
        )

        article_b = await _build_article_input(
            "B",
            article_b_url,
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