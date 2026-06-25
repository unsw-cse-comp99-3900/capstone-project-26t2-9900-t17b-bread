"""Compare Controller (proposal p.19-20).

Single backend endpoint that drives the article-processing pipeline for a pair
of articles (PROJ-3 AC 3.4). In Sprint 1 it returns both articles processed
into comparison-ready form (sentences + structure). Sprint 2 will extend the
response with matched segments, relationship labels, explanations and a
high-level summary.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.article import ProcessedArticle
from app.schemas.compare import CompareRequest, CompareResponse, StageError
from app.services.pipeline import process_pair

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.post("", response_model=CompareResponse, summary="Process a pair of articles")
async def compare(payload: CompareRequest) -> CompareResponse:
    """Run the processing pipeline on both URLs and return structured output.

    Per-article failures are reported in ``errors`` (identifying the failing
    stage and article) while any successfully processed article is still
    returned, so the frontend can render partial results gracefully.
    """
    results = await process_pair(payload.article_a_url, payload.article_b_url)

    articles: list[ProcessedArticle] = []
    errors: list[StageError] = []
    for result in results:
        if result.ok and result.article is not None:
            articles.append(result.article)
        elif result.error is not None:
            errors.append(StageError(**result.error.to_dict()))

    return CompareResponse(focus=payload.focus, articles=articles, errors=errors)
