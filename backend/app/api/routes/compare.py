"""Compare Controller (proposal p.19-20)."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from sqlalchemy import create_engine

from app.api.routes.auth import get_optional_user_from_header
from app.db import dal
from app.db.base import _normalize_url
from app.schemas.compare import (
    CompareRequest,
    CompareResponse,
    ComparisonFocus,
)
from app.config import get_settings
from app.services.article_input import ArticleInput
from app.services.pipeline import (
    ArticleResult,
    PairPipelineResult,
    process_pair_inputs_with_comparison,
)
from app.services.progress import ProgressTracker
from app.services.streaming import streaming_response_from_progress


load_dotenv()

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("SQLALCHEMY_DATABASE_URL")
    or "postgresql://postgres:postgres@localhost:5432/postgres"
)

engine = create_engine(
    _normalize_url(DATABASE_URL)
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compare", tags=["compare"])

COMPARISON_TIMEOUT_CODE = "comparison_timeout"
COMPARISON_TIMEOUT_MESSAGE = (
    "This comparison is taking too long. The articles may be too long for one run. "
    "Please split them into smaller sections and try again."
)


def _comparison_timeout_detail() -> dict[str, str]:
    return {
        "stage": "comparison",
        "code": COMPARISON_TIMEOUT_CODE,
        "message": COMPARISON_TIMEOUT_MESSAGE,
    }


async def _with_comparison_timeout(awaitable):
    try:
        return await asyncio.wait_for(
            awaitable,
            timeout=get_settings().comparison_timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=408,
            detail=_comparison_timeout_detail(),
        ) from exc


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


SCORE_SCALE_MIN = 0
SCORE_SCALE_MAX = 20

SPECIFIC_FACTOR_VALUES: frozenset[str] = frozenset(
    {
        "political",
        "sentiment",
        "economic",
        "social",
    }
)


def _safe_float(
    value: Any,
    *,
    default: float = 0.0,
) -> float:
    """Convert one value to a finite float."""

    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default

    if not (
        float("-inf")
        < converted
        < float("inf")
    ):
        return default

    return converted


def _clamp_unit_score(value: Any) -> float:
    """Clamp an internal model score to the inclusive range [0, 1]."""

    return max(
        0.0,
        min(
            1.0,
            _safe_float(value),
        ),
    )


def _to_public_score(value: Any) -> int:
    """
    Convert one internal [0, 1] score into the public 0-20 scale.

    Internal model scores remain available inside the pipeline, but the compare
    response exposes only the explicit, interpreted 0-20 score.
    """

    return int(
        round(
            _clamp_unit_score(value)
            * SCORE_SCALE_MAX
        )
    )


def _normalise_focus_value(value: Any) -> str:
    """Return a lowercase focus string for response construction."""

    if hasattr(value, "value"):
        value = value.value

    focus_value = str(value or "general").strip().lower()

    if focus_value not in {
        "general",
        "political",
        "sentiment",
        "economic",
        "social",
    }:
        return "general"

    return focus_value


def _match_strength_level(score: int) -> str:
    """Return the public level for Match Strength."""

    if score <= 4:
        return "very_low"
    if score <= 8:
        return "low"
    if score <= 12:
        return "moderate"
    if score <= 16:
        return "strong"
    return "very_strong"


def _factor_relevance_level(score: int) -> str:
    """Return the public level for Factor Relevance."""

    if score <= 4:
        return "very_low"
    if score <= 8:
        return "low"
    if score <= 12:
        return "moderate"
    if score <= 16:
        return "strong"
    return "very_strong"


def _stance_discrepancy_level(score: int) -> str:
    """Return the public level for Stance Discrepancy."""

    if score <= 4:
        return "none"
    if score <= 8:
        return "slight"
    if score <= 12:
        return "moderate"
    if score <= 16:
        return "strong"
    return "very_strong"


def _match_strength_interpretation(score: int) -> str:
    """Explain what one Match Strength score means for the user."""

    level = _match_strength_level(score)

    messages = {
        "very_low": (
            "The two paragraph chunks have very weak content correspondence "
            "and should not normally be treated as a direct comparison."
        ),
        "low": (
            "The paragraph chunks have limited content correspondence and may "
            "require manual review before direct comparison."
        ),
        "moderate": (
            "The paragraph chunks discuss a similar topic, but their direct "
            "correspondence is only moderate."
        ),
        "strong": (
            "The paragraph chunks discuss closely corresponding content and "
            "are suitable for direct comparison."
        ),
        "very_strong": (
            "The paragraph chunks have exceptionally strong content "
            "correspondence and should be prioritised as a matched pair."
        ),
    }

    return messages[level]


def _factor_relevance_interpretation(
    score: int,
    *,
    focus: str,
) -> str:
    """Explain relevance to the user's selected comparison factor."""

    focus_name = focus.capitalize()
    level = _factor_relevance_level(score)

    messages = {
        "very_low": (
            f"{focus_name} content is largely absent from this matched pair."
        ),
        "low": (
            f"{focus_name} content is mentioned only briefly in this matched "
            "pair."
        ),
        "moderate": (
            f"{focus_name} content forms a meaningful part of this matched "
            "pair, but is not its main focus."
        ),
        "strong": (
            f"{focus_name} content is an important part of this matched pair."
        ),
        "very_strong": (
            f"{focus_name} content is central to this matched pair."
        ),
    }

    return messages[level]


def _stance_discrepancy_interpretation(score: int) -> str:
    """
    Explain model-detected contradiction strength.

    This score is not a factuality judgement and is not a calibrated
    probability.
    """

    level = _stance_discrepancy_level(score)

    messages = {
        "none": (
            "No meaningful stance discrepancy was detected between the "
            "paragraph chunks."
        ),
        "slight": (
            "The paragraph chunks mainly differ in wording, emphasis, or "
            "minor framing."
        ),
        "moderate": (
            "The paragraph chunks contain a noticeable difference in framing "
            "or claim direction."
        ),
        "strong": (
            "The paragraph chunks contain strong differences in viewpoint or "
            "factual claims."
        ),
        "very_strong": (
            "The paragraph chunks present directly opposing or highly "
            "incompatible claims."
        ),
    }

    return messages[level]


def _build_match_strength_score(
    mapping_score: Any,
) -> dict[str, Any]:
    """Build the public Match Strength score object."""

    score = _to_public_score(mapping_score)

    return {
        "score": score,
        "scale_min": SCORE_SCALE_MIN,
        "scale_max": SCORE_SCALE_MAX,
        "level": _match_strength_level(score),
        "interpretation": (
            _match_strength_interpretation(score)
        ),
    }


def _build_factor_relevance_score(
    factor_relevance_score: Any,
    *,
    focus: str,
    selected_factor: Any = None,
) -> dict[str, Any] | None:
    """
    Build the public Factor Relevance score object.

    Specific-focus mode:
        Return relevance to the explicitly requested factor.

    General mode:
        Return relevance to the one factor selected for the complete article
        pair by FocusScalingService.
    """

    focus_value = _normalise_focus_value(
        focus
    )

    if focus_value == "general":
        factor = str(
            selected_factor or ""
        ).strip().lower()
    else:
        factor = focus_value

    if factor not in SPECIFIC_FACTOR_VALUES:
        return None

    score = _to_public_score(
        factor_relevance_score
    )

    return {
        "factor": factor,
        "score": score,
        "scale_min": SCORE_SCALE_MIN,
        "scale_max": SCORE_SCALE_MAX,
        "level": _factor_relevance_level(score),
        "interpretation": (
            _factor_relevance_interpretation(
                score,
                focus=factor,
            )
        ),
    }


def _build_stance_discrepancy_score(
    contradiction_score: Any,
) -> dict[str, Any]:
    """Build the public Stance Discrepancy score object."""

    score = _to_public_score(
        contradiction_score
    )

    return {
        "score": score,
        "scale_min": SCORE_SCALE_MIN,
        "scale_max": SCORE_SCALE_MAX,
        "level": _stance_discrepancy_level(score),
        "interpretation": (
            _stance_discrepancy_interpretation(
                score
            )
        ),
        "disclaimer": (
            "This score represents model-detected contradiction strength. "
            "It is not a probability and does not determine which article "
            "is factually correct."
        ),
    }


def _relationship_explanation(
    relationship: dict[str, Any],
) -> str:
    """Create a concise frontend explanation from the reason code."""

    label = relationship.get("label")
    reason_code = relationship.get("reason_code")

    if label == "aligned":
        aligned_messages = {
            "strong_similarity_with_nli_entailment": (
                "These paragraph chunks present strongly consistent content."
            ),
            "strong_shared_content_with_additional_detail": (
                "These paragraph chunks share the same core content, while "
                "one side includes additional detail."
            ),
            "strong_similarity_with_partial_nli_support": (
                "These paragraph chunks are strongly similar and receive "
                "partial support from bidirectional NLI."
            ),
            "strong_similarity_without_meaningful_contradiction": (
                "These paragraph chunks are strongly similar and contain no "
                "meaningful contradiction evidence."
            ),
        }

        return aligned_messages.get(
            reason_code,
            (
                "These paragraph chunks present strongly aligned content "
                "across the two articles."
            ),
        )

    if label == "partially_aligned":
        partial_messages = {
            "semantic_match_with_lexical_difference": (
                "These paragraph chunks discuss related content using "
                "different wording or lexical choices."
            ),
            "related_content_with_nli_neutrality": (
                "These paragraph chunks discuss related content, but neither "
                "clearly support nor contradict each other."
            ),
            "partial_support_with_additional_information": (
                "These paragraph chunks share part of the same claim, while "
                "one side contains additional or narrower information."
            ),
            "accepted_mapping_with_moderate_alignment": (
                "These paragraph chunks are valid mapped counterparts with "
                "moderate alignment in content or framing."
            ),
        }

        return partial_messages.get(
            reason_code,
            (
                "These paragraph chunks are related, but differ in emphasis, "
                "detail, or framing."
            ),
        )

    if label == "divergent":
        if (
            reason_code
            == "contradiction_rescue_with_strong_bidirectional_nli"
        ):
            return (
                "These paragraph chunks were retained because the model found "
                "strong opposing claims despite lower similarity."
            )

        return (
            "These paragraph chunks discuss the same or closely related "
            "subject, but contain strong contradiction evidence."
        )

    return "No supported relationship classification is available."


def _safe_order(value: Any) -> int:
    """Convert one article-order value into a stable sorting integer."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return 10**9


def _build_frontend_matches(
    pair_result: PairPipelineResult,
) -> list[dict[str, Any]]:
    """
    Convert final relationships into transparent frontend scores.

    The route uses internal scores only as conversion inputs. Raw cosine, BM25,
    hybrid, mapping, NLI, confidence, and factor-adjustment values are not
    exposed in the public response.

    In general mode, factor_relevance contains the strongest factor selected
    independently for each relationship by FocusScalingService.
    """

    if pair_result.comparison is None:
        return []

    focus = _normalise_focus_value(
        pair_result.comparison.focus
    )

    matches: list[dict[str, Any]] = []

    for index, relationship in enumerate(
        pair_result.comparison.relationships
    ):
        a_chunk_id = relationship.get("a_chunk_id")
        b_chunk_id = relationship.get("b_chunk_id")

        if not a_chunk_id or not b_chunk_id:
            continue

        match_strength = (
            _build_match_strength_score(
                relationship.get("mapping_score")
            )
        )

        factor_relevance = (
            _build_factor_relevance_score(
                relationship.get(
                    "factor_relevance_score"
                ),
                focus=focus,
                selected_factor=relationship.get(
                    "selected_factor"
                ),
            )
        )

        stance_discrepancy = (
            _build_stance_discrepancy_score(
                relationship.get(
                    "contradiction_score"
                )
            )
        )

        matches.append(
            {
                "id": (
                    f"{a_chunk_id}-"
                    f"{b_chunk_id}-"
                    f"{index}"
                ),
                "a_chunk_id": a_chunk_id,
                "b_chunk_id": b_chunk_id,
                "a_paragraph_index": relationship.get(
                    "a_paragraph_index"
                ),
                "b_paragraph_index": relationship.get(
                    "b_paragraph_index"
                ),
                "a_chunk_index": relationship.get(
                    "a_chunk_index"
                ),
                "b_chunk_index": relationship.get(
                    "b_chunk_index"
                ),

                "label": relationship.get(
                    "label",
                    "partially_aligned",
                ),
                "reason_code": relationship.get(
                    "reason_code"
                ),
                "explanation": (
                    _relationship_explanation(
                        relationship
                    )
                ),

                "match_strength": match_strength,
                "factor_relevance": factor_relevance,
                "stance_discrepancy": (
                    stance_discrepancy
                ),

                "a_text_preview": relationship.get(
                    "a_text_preview"
                ),
                "b_text_preview": relationship.get(
                    "b_text_preview"
                ),
                "pair_number": relationship.get(
                    "pair_number"
                ),
            }
        )

    # The default response order is Best Match. The frontend may re-sort the
    # same list by factor_relevance.score, stance_discrepancy.score, or article
    # order without requiring another API call.
    matches.sort(
        key=lambda match: (
            -int(
                match["match_strength"]["score"]
            ),
            _safe_order(
                match.get("a_chunk_index")
            ),
            _safe_order(
                match.get("b_chunk_index")
            ),
        )
    )

    return matches


def _build_score_guides(
    focus: str,
    *,
    selected_factor: Any = None,
) -> dict[str, Any]:
    """Return fixed, actionable score ranges for frontend tooltips."""

    guides: dict[str, Any] = {
        "match_strength": {
            "title": "Match Strength",
            "question": (
                "How closely do these paragraph chunks correspond in content?"
            ),
            "scale_min": SCORE_SCALE_MIN,
            "scale_max": SCORE_SCALE_MAX,
            "bands": [
                {
                    "min": 0,
                    "max": 4,
                    "level": "very_low",
                    "interpretation": (
                        "Very weak correspondence; normally not suitable for "
                        "direct comparison."
                    ),
                },
                {
                    "min": 5,
                    "max": 8,
                    "level": "low",
                    "interpretation": (
                        "Limited correspondence; manual review is recommended."
                    ),
                },
                {
                    "min": 9,
                    "max": 12,
                    "level": "moderate",
                    "interpretation": (
                        "Similar topic with moderate direct correspondence."
                    ),
                },
                {
                    "min": 13,
                    "max": 16,
                    "level": "strong",
                    "interpretation": (
                        "Closely corresponding content suitable for direct "
                        "comparison."
                    ),
                },
                {
                    "min": 17,
                    "max": 20,
                    "level": "very_strong",
                    "interpretation": (
                        "Exceptionally strong correspondence; prioritise this "
                        "matched pair."
                    ),
                },
            ],
        },
        "stance_discrepancy": {
            "title": "Stance Discrepancy",
            "question": (
                "How strongly do the paragraph chunks differ in claim or "
                "stance?"
            ),
            "scale_min": SCORE_SCALE_MIN,
            "scale_max": SCORE_SCALE_MAX,
            "disclaimer": (
                "This is model-detected contradiction strength, not a "
                "probability or factuality judgement."
            ),
            "bands": [
                {
                    "min": 0,
                    "max": 4,
                    "level": "none",
                    "interpretation": (
                        "No meaningful stance discrepancy detected."
                    ),
                },
                {
                    "min": 5,
                    "max": 8,
                    "level": "slight",
                    "interpretation": (
                        "Mainly wording, emphasis, or minor framing differences."
                    ),
                },
                {
                    "min": 9,
                    "max": 12,
                    "level": "moderate",
                    "interpretation": (
                        "Noticeable difference in framing or claim direction."
                    ),
                },
                {
                    "min": 13,
                    "max": 16,
                    "level": "strong",
                    "interpretation": (
                        "Strong differences in viewpoint or factual claims."
                    ),
                },
                {
                    "min": 17,
                    "max": 20,
                    "level": "very_strong",
                    "interpretation": (
                        "Directly opposing or highly incompatible claims."
                    ),
                },
            ],
        },
    }

    effective_factor = (
        str(
            selected_factor or ""
        ).strip().lower()
        if focus == "general"
        else focus
    )

    if effective_factor in SPECIFIC_FACTOR_VALUES:
        factor_name = (
            effective_factor.capitalize()
        )

        if focus == "general":
            question = (
                "How strongly is this matched pair related to the "
                f"automatically selected {factor_name.lower()} factor?"
            )
            disclaimer = (
                f"{factor_name} was selected once for the complete article "
                "pair and is applied consistently to every matched pair."
            )
        else:
            question = (
                "How strongly is this matched pair related to the selected "
                f"{factor_name.lower()} factor?"
            )
            disclaimer = None

        guides["factor_relevance"] = {
            "title": f"{factor_name} Relevance",
            "question": question,
            "factor": effective_factor,
            "scale_min": SCORE_SCALE_MIN,
            "scale_max": SCORE_SCALE_MAX,
            "disclaimer": disclaimer,
            "bands": [
                {
                    "min": 0,
                    "max": 4,
                    "level": "very_low",
                    "interpretation": (
                        f"{factor_name} content is largely absent."
                    ),
                },
                {
                    "min": 5,
                    "max": 8,
                    "level": "low",
                    "interpretation": (
                        f"{factor_name} content is mentioned only briefly."
                    ),
                },
                {
                    "min": 9,
                    "max": 12,
                    "level": "moderate",
                    "interpretation": (
                        f"{factor_name} content is meaningful but not central."
                    ),
                },
                {
                    "min": 13,
                    "max": 16,
                    "level": "strong",
                    "interpretation": (
                        f"{factor_name} content is an important part of the pair."
                    ),
                },
                {
                    "min": 17,
                    "max": 20,
                    "level": "very_strong",
                    "interpretation": (
                        f"{factor_name} content is central to the pair."
                    ),
                },
            ],
        }

    return guides


def _build_sorting_metadata(
    focus: str,
    *,
    selected_factor: Any = None,
) -> dict[str, Any]:
    """Describe sorting choices supported directly by the response."""

    options: list[dict[str, Any]] = [
        {
            "key": "best_match",
            "label": "Best Match",
            "score_path": "match_strength.score",
            "direction": "descending",
            "description": (
                "Show the most strongly corresponding paragraph pairs first."
            ),
        },
    ]

    effective_factor = (
        str(
            selected_factor or ""
        ).strip().lower()
        if focus == "general"
        else focus
    )

    if effective_factor in SPECIFIC_FACTOR_VALUES:
        factor_name = (
            effective_factor.capitalize()
        )

        options.append(
            {
                "key": "selected_factor",
                "label": (
                    f"Most Relevant to {factor_name}"
                ),
                "score_path": (
                    "factor_relevance.score"
                ),
                "secondary_score_path": (
                    "match_strength.score"
                ),
                "direction": "descending",
                "description": (
                    f"Show pairs most relevant to the {factor_name.lower()} "
                    "factor first. Match Strength is used as the tie-breaker."
                ),
            }
        )

    options.extend(
        [
            {
                "key": "most_divergent",
                "label": "Most Divergent",
                "score_path": (
                    "stance_discrepancy.score"
                ),
                "secondary_score_path": (
                    "match_strength.score"
                ),
                "direction": "descending",
                "description": (
                    "Show pairs with the strongest model-detected stance "
                    "difference first."
                ),
            },
            {
                "key": "article_order",
                "label": "Article Order",
                "score_path": None,
                "direction": "ascending",
                "description": (
                    "Show pairs in their original article order."
                ),
            },
        ]
    )

    return {
        "default": "best_match",
        "options": options,
    }


def _mean_public_score(
    matches: list[dict[str, Any]],
    *path: str,
) -> float | None:
    """Calculate the mean of one nested public score."""

    values: list[int] = []

    for match in matches:
        current: Any = match

        for key in path:
            if not isinstance(current, dict):
                current = None
                break

            current = current.get(key)

        if current is None:
            continue

        try:
            values.append(int(current))
        except (TypeError, ValueError):
            continue

    if not values:
        return None

    return round(
        sum(values) / len(values),
        2,
    )


def _build_comparison_payload(
    pair_result: PairPipelineResult,
) -> dict[str, Any] | None:
    """
    Build the final public comparison payload.

    Raw internal model scores are intentionally excluded.
    """

    if pair_result.comparison is None:
        return None

    comparison = pair_result.comparison
    focus = _normalise_focus_value(
        comparison.focus
    )
    matches = _build_frontend_matches(
        pair_result
    )

    selected_factor: str | None = None

    if focus != "general":
        selected_factor = focus
    else:
        for match in matches:
            factor_relevance = match.get(
                "factor_relevance"
            )

            if not isinstance(
                factor_relevance,
                dict,
            ):
                continue

            candidate_factor = str(
                factor_relevance.get(
                    "factor",
                    "",
                )
            ).strip().lower()

            if candidate_factor in SPECIFIC_FACTOR_VALUES:
                selected_factor = candidate_factor
                break

    summary: dict[str, Any] = {
        "match_count": len(matches),
        "aligned_count": sum(
            1
            for match in matches
            if match.get("label") == "aligned"
        ),
        "partially_aligned_count": sum(
            1
            for match in matches
            if (
                match.get("label")
                == "partially_aligned"
            )
        ),
        "divergent_count": sum(
            1
            for match in matches
            if match.get("label") == "divergent"
        ),
        "average_match_strength": (
            _mean_public_score(
                matches,
                "match_strength",
                "score",
            )
            or 0.0
        ),
        "average_stance_discrepancy": (
            _mean_public_score(
                matches,
                "stance_discrepancy",
                "score",
            )
            or 0.0
        ),
    }

    average_factor_relevance = (
        _mean_public_score(
            matches,
            "factor_relevance",
            "score",
        )
    )

    if average_factor_relevance is not None:
        summary["average_factor_relevance"] = (
            average_factor_relevance
        )

    return {
        "focus": focus,
        "selected_factor": selected_factor,
        "summary": summary,
        "score_guides": _build_score_guides(
            focus,
            selected_factor=selected_factor,
        ),
        "sorting": _build_sorting_metadata(
            focus,
            selected_factor=selected_factor,
        ),
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
    comparison_id: int | None = None,
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
        "comparison_id": comparison_id,
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
    user_id: int | None = None,
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

    frontend_matches = _build_frontend_matches(
        pair_result
    )

    average_match_strength = (
        _mean_public_score(
            frontend_matches,
            "match_strength",
            "score",
        )
        or 0.0
    )

    average_factor_relevance = (
        _mean_public_score(
            frontend_matches,
            "factor_relevance",
            "score",
        )
    )

    average_stance_discrepancy = (
        _mean_public_score(
            frontend_matches,
            "stance_discrepancy",
            "score",
        )
        or 0.0
    )

    comparison_id: int | None = None

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
                    "focus": focus.value if hasattr(focus, "value") else str(focus),
                    "articles": [
                        article_payload
                        for result in pair_result.articles
                        if (article_payload := _build_frontend_article(result)) is not None
                    ],
                    "comparison": _build_comparison_payload(
                        pair_result
                    ),
                    "matches": frontend_matches,

                    # Public 0-20 aggregate scores. Raw model scores remain
                    # inside the pipeline and are not persisted in the public
                    # result payload.
                    "average_match_strength": (
                        average_match_strength
                    ),
                    "average_factor_relevance": (
                        average_factor_relevance
                    ),
                    "average_stance_discrepancy": (
                        average_stance_discrepancy
                    ),
                    "session_token": session_token,
                }
                
                comparison_id = dal.insert_comparison_result(conn, db_id_a, db_id_b, result_payload)
                
                if comparison_id and user_id is not None:
                    dal.insert_history(conn, comparison_id, user_id)
                    logger.info(
                        "[DB Sync] Logged user history for comparison ID: %s",
                        comparison_id,
                    )
                
        logger.info("[DB Sync Success] Interpretable 0-20 comparison scores and final matches persisted.")
        
    except Exception as db_err:
        logger.critical(f"[CRITICAL DB ERROR]: {db_err}")
        session_token = f"fallback-{uuid.uuid4()}"

    return _build_compare_response(
        focus=focus,
        pair_result=pair_result,
        progress=progress,
        session_token=session_token,
        comparison_id=comparison_id,
    )


@router.post(
    "",
    response_model=CompareResponse,
    summary="Compare a pair of articles from URLs and/or pasted text",
)
async def compare(
    payload: CompareRequest,
    authorization: str | None = Header(default=None),
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
    user = get_optional_user_from_header(authorization)

    return await _with_comparison_timeout(
        _run_compare_inputs(
            article_a,
            article_b,
            payload.focus,
            progress=progress,
            user_id=int(user["id"]) if user else None,
        )
    )


@router.post(
    "/stream",
    summary="Compare two articles (URL and/or pasted text) with live English progress (SSE)",
)
async def compare_stream(
    payload: CompareRequest,
    authorization: str | None = Header(default=None),
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
    user = get_optional_user_from_header(authorization)

    async def runner() -> dict:
        try:
            article_a, article_b = _build_json_article_inputs(payload)

            response = await _with_comparison_timeout(
                _run_compare_inputs(
                    article_a,
                    article_b,
                    payload.focus,
                    progress=progress,
                    user_id=int(user["id"]) if user else None,
                )
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
    authorization: str | None = Header(default=None),
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
    user = get_optional_user_from_header(authorization)

    return await _with_comparison_timeout(
        _run_compare_inputs(
            article_a,
            article_b,
            focus,
            progress=progress,
            user_id=int(user["id"]) if user else None,
        )
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
    authorization: str | None = Header(default=None),
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
    user = get_optional_user_from_header(authorization)

    async def runner() -> dict:
        try:
            response = await _with_comparison_timeout(
                _run_compare_inputs(
                    article_a,
                    article_b,
                    focus,
                    progress=progress,
                    user_id=int(user["id"]) if user else None,
                )
            )

            return response.model_dump(exclude_none=True)
        finally:
            await progress_queue.put(None)

    return streaming_response_from_progress(
        runner,
        progress_queue=progress_queue,
    )
