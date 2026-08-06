# backend/app/services/focus_scaling_service.py

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from app.services.embedding_service import get_embedding_service


logger = logging.getLogger(__name__)


FOCUS_PROFILES: dict[str, tuple[str, ...]] = {
    "political": (
        "The government announced or implemented a policy, law, regulation, "
        "or official decision.",
        "Political leaders, parties, elections, ideology, political power, or "
        "public accountability are central to the report.",
        "The report concerns sanctions, diplomacy, international relations, "
        "conflict between states, military action, or national security.",
        "The passage examines governance, state institutions, civil rights, "
        "protests, public authority, or political responsibility.",
        "One government is attempting to pressure, control, punish, or change "
        "the behaviour of another country or political regime.",
    ),
    "sentiment": (
        "People express fear, anger, outrage, grief, sympathy, hope, distress, "
        "concern, or another explicit emotion.",
        "The wording praises, blames, criticises, condemns, reassures, or alarms "
        "the reader through emotionally charged language.",
        "The report emphasises suffering, tragedy, loss, danger, relief, or "
        "people's emotional reactions to an event.",
        "The passage has a strongly positive, negative, anxious, optimistic, "
        "or compassionate emotional tone.",
    ),
    "economic": (
        "The report concerns prices, markets, trade, tariffs, inflation, costs, "
        "financial conditions, or economic policy.",
        "The passage discusses businesses, employment, wages, investment, "
        "budgets, revenue, spending, or commercial activity.",
        "The report concerns production, supply, demand, resources, fuel, "
        "energy availability, shortages, or distribution.",
        "The passage explains economic consequences for a country, industry, "
        "organisation, household, or individual.",
    ),
    "social": (
        "The event affects civilians, families, communities, social groups, or "
        "people's everyday public life.",
        "The report concerns healthcare, education, housing, transport, public "
        "services, or access to essential needs.",
        "The passage discusses inequality, vulnerable groups, human welfare, "
        "social exclusion, or living conditions.",
        "The report concerns displacement, community disruption, social "
        "cohesion, collective behaviour, or broader societal consequences.",
    ),
}


# Fixed order used only as the final deterministic tie-breaker when two
# directions receive exactly the same pair relevance.
GENERAL_FOCUS_CANDIDATES: tuple[str, ...] = (
    "political",
    "sentiment",
    "economic",
    "social",
)


# General mode selects one factor for the whole article pair. Each article-side
# score is the mean of its strongest calibrated chunk relevances, which reduces
# dilution from long articles while preventing one isolated chunk from deciding
# the global factor.
GENERAL_SELECTION_TOP_FRACTION = 0.25
GENERAL_SELECTION_MAX_TOP_K = 12


FOCUS_MAX_BOOST: dict[str, float] = {
    "general": 0.0,
    "political": 0.15,
    "sentiment": 0.15,
    "economic": 0.15,
    "social": 0.15,
}


# Each focus is represented by several semantic prototypes. For every chunk,
# the raw focus similarity is the mean of its strongest prototype matches.
FOCUS_PROTOTYPE_TOP_K = 2

# Dynamic calibration is performed independently for each article side.
#
# article_minimum:
#   If every chunk in an article scores at or below this raw cosine value, the
#   whole article side is treated as unrelated to the selected focus.
#
# chunk_floor:
#   A chunk below this raw cosine value receives zero relevance even when the
#   article contains some focus-related content elsewhere.
#
# strong_reference:
#   A conservative raw cosine value representing strong absolute relevance.
#   It also prevents local min-max scaling from making a weak article appear
#   strongly relevant merely because one chunk is the local maximum.
#
# These values are operational defaults for all-MiniLM-L6-v2 and should be
# configurable through application settings if the embedding model changes.
FOCUS_CALIBRATION: dict[str, dict[str, float]] = {
    "political": {
        "article_minimum": 0.16,
        "chunk_floor": 0.08,
        "strong_reference": 0.35,
    },
    "sentiment": {
        "article_minimum": 0.14,
        "chunk_floor": 0.06,
        "strong_reference": 0.33,
    },
    "economic": {
        "article_minimum": 0.16,
        "chunk_floor": 0.08,
        "strong_reference": 0.35,
    },
    "social": {
        "article_minimum": 0.15,
        "chunk_floor": 0.07,
        "strong_reference": 0.34,
    },
}

# Robust local range. Quantiles are used instead of literal minimum and maximum
# so one outlier cannot define the entire article's score scale.
FOCUS_LOCAL_LOW_QUANTILE = 0.20
FOCUS_LOCAL_HIGH_QUANTILE = 0.90
FOCUS_LOCAL_MIN_SPAN = 0.06

# Final side relevance combines relative position within the article with
# absolute semantic evidence. The article-level confidence is applied after
# this mixture.
FOCUS_LOCAL_WEIGHT = 0.55
FOCUS_ABSOLUTE_WEIGHT = 0.45

# These gates affect only the focus-adjusted display score. They never affect:
#
# - candidate mapping;
# - NLI eligibility;
# - final mapping;
# - relationship classification.
#
# factor_relevance_score remains independent of this gate.
FOCUS_GATE_START_SCORE = 0.38
FOCUS_GATE_FULL_SCORE = 0.58


def _normalise_focus(focus: Any) -> str:
    """
    Convert a frontend string or enum value into a normalized focus name.
    """

    if focus is None:
        return "general"

    if hasattr(focus, "value"):
        focus = focus.value

    value = str(focus).strip().lower()

    if not value:
        return "general"

    if value not in FOCUS_PROFILES:
        return "general"

    return value


class FocusScalingService:
    """
    Add focus relevance and focus-based display ranking after classification.

    Recommended pipeline position:

        final_mappings
            -> relationships
            -> FocusScalingService.enrich_relationships(...)

    This service does not change whether a pair is mapped and does not change
    aligned / partially_aligned / divergent labels.

    Two different outputs are intentionally kept separate:

    1. factor_relevance_score

       Pure pair-level relevance to the selected focus, in [0, 1]. It is
       independent of base_hybrid_score and can be used directly for focus-only
       ranking.

       When the requested focus is ``general``, all four supported directions
       are evaluated across the complete article pair. One global factor is
       selected and then used to calculate factor relevance for every accepted
       relationship.

    2. focus_adjusted_score

       A bounded display score calculated by applying a small focus boost to
       base_hybrid_score. It can be used when the UI needs one score combining
       content similarity and focus preference.

       General mode remains non-boosting: it automatically selects one global
       direction but leaves focus_adjusted_score equal to base_hybrid_score.
    """

    def __init__(self) -> None:
        self._focus_embedding_cache: dict[str, np.ndarray] = {}

    def enrich_relationships(
        self,
        relationships: list[dict[str, Any]],
        *,
        embeddings_a: list[dict[str, Any]],
        embeddings_b: list[dict[str, Any]],
        focus: Any = "general",
        sort_by_factor_relevance: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Add focus fields to classified relationships.

        Every returned item includes:

            selected_factor
            factor_relevance_score
            factor_rank
            focus_adjusted_score
            factor_adjustment
            factor_adjustment_percent
            scale_factor

        General mode performs two distinct steps:

            1. Evaluate political, sentiment, economic, and social relevance
               across all chunks from both articles.
            2. Select one global factor and use that same factor for every
               accepted relationship.

        When sort_by_factor_relevance=True, results are returned in descending
        factor relevance. Otherwise, the original relationship order is
        preserved while factor_rank still records the factor-specific rank.
        """

        if not relationships:
            return []

        focus_value = _normalise_focus(focus)

        selected_factor: str | None
        selected_factor_global_score: float | None
        general_factor_scores: dict[str, float]
        general_factor_side_scores: dict[
            str,
            dict[str, float],
        ]

        if focus_value == "general":
            general_focus_lookups = {
                candidate_focus: (
                    self.compute_focus_relevance_lookup(
                        embeddings_a,
                        embeddings_b,
                        focus=candidate_focus,
                    )
                )
                for candidate_focus
                in GENERAL_FOCUS_CANDIDATES
            }

            (
                selected_factor,
                general_factor_scores,
                general_factor_side_scores,
            ) = self._select_global_factor(
                general_focus_lookups
            )

            if selected_factor is None:
                selected_factor_global_score = None
                focus_relevance_lookup = {
                    "a": {},
                    "b": {},
                }
            else:
                selected_factor_global_score = (
                    general_factor_scores.get(
                        selected_factor,
                        0.0,
                    )
                )
                focus_relevance_lookup = (
                    general_focus_lookups.get(
                        selected_factor,
                        {
                            "a": {},
                            "b": {},
                        },
                    )
                )

            logger.info(
                (
                    "General focus selection: selected_factor=%s "
                    "global_score=%s factor_scores=%s"
                ),
                selected_factor,
                (
                    f"{selected_factor_global_score:.4f}"
                    if selected_factor_global_score
                    is not None
                    else None
                ),
                {
                    factor_name: round(
                        factor_score,
                        4,
                    )
                    for factor_name, factor_score
                    in general_factor_scores.items()
                },
            )

        else:
            selected_factor = focus_value
            selected_factor_global_score = None
            general_factor_scores = {}
            general_factor_side_scores = {}
            focus_relevance_lookup = (
                self.compute_focus_relevance_lookup(
                    embeddings_a,
                    embeddings_b,
                    focus=focus_value,
                )
            )

        enriched_relationships: list[dict[str, Any]] = []

        for relationship in relationships:
            a_chunk_id = relationship.get("a_chunk_id")
            b_chunk_id = relationship.get("b_chunk_id")

            if not a_chunk_id or not b_chunk_id:
                continue

            base_hybrid_score = (
                self._get_required_bounded_score(
                    relationship,
                    "base_hybrid_score",
                )
            )

            if focus_value == "general":
                scaling_result = (
                    self._build_general_result_for_factor(
                        base_score=base_hybrid_score,
                        a_chunk_id=str(a_chunk_id),
                        b_chunk_id=str(b_chunk_id),
                        selected_factor=selected_factor,
                        focus_relevance_lookup=(
                            focus_relevance_lookup
                        ),
                        selected_factor_global_score=(
                            selected_factor_global_score
                        ),
                        general_factor_scores=(
                            general_factor_scores
                        ),
                        general_factor_side_scores=(
                            general_factor_side_scores
                        ),
                    )
                )
            else:
                scaling_result = self.apply_focus_scaling(
                    base_score=base_hybrid_score,
                    a_chunk_id=str(a_chunk_id),
                    b_chunk_id=str(b_chunk_id),
                    focus=focus_value,
                    focus_relevance_lookup=(
                        focus_relevance_lookup
                    ),
                )

            enriched = dict(relationship)

            enriched.update(
                {
                    "focus": scaling_result["focus"],

                    # General mode uses the same selected factor for every pair.
                    "selected_factor": (
                        scaling_result[
                            "selected_factor"
                        ]
                    ),

                    # Internal article-pair selection diagnostics.
                    "selected_factor_global_score": (
                        scaling_result.get(
                            "selected_factor_global_score"
                        )
                    ),
                    "general_factor_scores": (
                        scaling_result.get(
                            "general_factor_scores",
                            {},
                        )
                    ),
                    "general_factor_side_scores": (
                        scaling_result.get(
                            "general_factor_side_scores",
                            {},
                        )
                    ),

                    "a_focus_relevance": (
                        scaling_result[
                            "a_focus_relevance"
                        ]
                    ),
                    "b_focus_relevance": (
                        scaling_result[
                            "b_focus_relevance"
                        ]
                    ),
                    "bilateral_focus_relevance": (
                        scaling_result[
                            "bilateral_focus_relevance"
                        ]
                    ),

                    # Main score for focus-only ranking.
                    "factor_relevance_score": (
                        scaling_result[
                            "factor_relevance_score"
                        ]
                    ),

                    # Backward-compatible alias.
                    "pair_focus_relevance": (
                        scaling_result[
                            "factor_relevance_score"
                        ]
                    ),

                    "focus_gate": (
                        scaling_result["focus_gate"]
                    ),
                    "max_focus_boost": (
                        scaling_result[
                            "max_focus_boost"
                        ]
                    ),
                    "effective_boost": (
                        scaling_result[
                            "effective_boost"
                        ]
                    ),
                    "scale_factor": (
                        scaling_result["scale_factor"]
                    ),
                    "factor_adjustment": (
                        scaling_result[
                            "factor_adjustment"
                        ]
                    ),
                    "factor_adjustment_percent": (
                        scaling_result[
                            "factor_adjustment_percent"
                        ]
                    ),

                    # Combined content + focus display score.
                    "focus_adjusted_score": (
                        scaling_result[
                            "focus_adjusted_score"
                        ]
                    ),

                    # Explicit compatibility names for existing consumers.
                    "focus_adjusted_hybrid_score": (
                        scaling_result[
                            "focus_adjusted_score"
                        ]
                    ),
                    "hybrid_score": (
                        scaling_result[
                            "focus_adjusted_score"
                        ]
                    ),
                }
            )

            enriched_relationships.append(enriched)

        ranked_relationships = sorted(
            enriched_relationships,
            key=self._factor_ranking_key,
        )

        for factor_rank, relationship in enumerate(
            ranked_relationships,
            start=1,
        ):
            relationship["factor_rank"] = factor_rank

        if sort_by_factor_relevance:
            return ranked_relationships

        return enriched_relationships

    def compute_focus_relevance_lookup(
        self,
        embeddings_a: list[dict[str, Any]],
        embeddings_b: list[dict[str, Any]],
        *,
        focus: Any,
    ) -> dict[str, dict[str, float]]:
        """
        Compute calibrated focus relevance independently for each article.

        The two article sides use the same absolute focus configuration but
        derive their robust local ranges from their own chunk distributions.
        An absolute article-level gate prevents an unrelated article from being
        assigned artificial relevance by local normalization.
        """

        focus_value = _normalise_focus(focus)

        if focus_value == "general":
            return {
                "a": {},
                "b": {},
            }

        focus_vectors = self._get_focus_embeddings(
            focus_value
        )

        return {
            "a": self._compute_side_relevance(
                embeddings_a,
                focus_vectors=focus_vectors,
                focus=focus_value,
                side="a",
            ),
            "b": self._compute_side_relevance(
                embeddings_b,
                focus_vectors=focus_vectors,
                focus=focus_value,
                side="b",
            ),
        }

    def apply_focus_scaling(
        self,
        *,
        base_score: float,
        a_chunk_id: str,
        b_chunk_id: str,
        focus: Any,
        focus_relevance_lookup: dict[
            str,
            dict[str, float],
        ],
    ) -> dict[str, Any]:
        """
        Calculate focus relevance and a bounded focus-adjusted display score.

        factor_relevance_score is the pure focus relevance of the pair:

            0.80 * geometric_mean(a_relevance, b_relevance)
            + 0.20 * max(a_relevance, b_relevance)

        focus_adjusted_score is:

            base_score * (
                1
                + max_focus_boost
                * factor_relevance_score
                * focus_gate
            )

        The pure factor relevance is returned even when focus_gate is zero.
        Therefore, contradiction-rescue mappings with a lower base score can
        still be ranked accurately by their relevance to the selected focus.
        """

        focus_value = _normalise_focus(focus)
        base_score = self._clamp(base_score)

        if focus_value == "general":
            return self._general_result(
                base_score=base_score
            )

        a_relevance = self._clamp(
            focus_relevance_lookup
            .get("a", {})
            .get(str(a_chunk_id), 0.0)
        )

        b_relevance = self._clamp(
            focus_relevance_lookup
            .get("b", {})
            .get(str(b_chunk_id), 0.0)
        )

        # Geometric mean emphasizes bilateral focus relevance.
        bilateral_relevance = float(
            np.sqrt(
                a_relevance
                * b_relevance
            )
        )

        factor_relevance_score = self._clamp(
            0.80 * bilateral_relevance
            + 0.20
            * max(
                a_relevance,
                b_relevance,
            )
        )

        focus_gate = self._compute_focus_gate(
            base_score
        )

        max_focus_boost = FOCUS_MAX_BOOST.get(
            focus_value,
            0.0,
        )

        effective_boost = self._clamp(
            max_focus_boost
            * factor_relevance_score
            * focus_gate,
            minimum=0.0,
            maximum=max_focus_boost,
        )

        scale_factor = (
            1.0
            + effective_boost
        )

        focus_adjusted_score = self._clamp(
            base_score
            * scale_factor
        )

        factor_adjustment = (
            focus_adjusted_score
            - base_score
        )

        return {
            "focus": focus_value,
            "selected_factor": focus_value,
            "a_focus_relevance": a_relevance,
            "b_focus_relevance": b_relevance,
            "bilateral_focus_relevance": (
                bilateral_relevance
            ),

            # Pure focus score for factor-specific ranking.
            "factor_relevance_score": (
                factor_relevance_score
            ),

            # Backward-compatible alias.
            "pair_focus_relevance": (
                factor_relevance_score
            ),

            "focus_gate": focus_gate,
            "max_focus_boost": max_focus_boost,
            "effective_boost": effective_boost,
            "scale_factor": scale_factor,

            # Absolute increase on the 0-1 score scale.
            "factor_adjustment": factor_adjustment,

            # Relative multiplicative increase, expressed as percent.
            "factor_adjustment_percent": (
                effective_boost * 100.0
            ),

            "focus_adjusted_score": (
                focus_adjusted_score
            ),

            # Compatibility alias.
            "final_score": focus_adjusted_score,
        }

    def _compute_side_relevance(
        self,
        embeddings: list[dict[str, Any]],
        *,
        focus_vectors: np.ndarray,
        focus: str,
        side: str,
    ) -> dict[str, float]:
        """
        Compute article-local focus relevance for one article side.

        Processing order:

        1. Calculate each chunk's raw similarity against multiple focus
           prototypes.
        2. Reject the whole article side when its strongest chunk does not pass
           the absolute article minimum.
        3. Build a robust local range from article-level quantiles.
        4. Combine local relative relevance with absolute semantic relevance.
        5. Scale all results by article-level confidence.
        """

        raw_scores: dict[str, float] = {}

        for item in embeddings:
            chunk_id = item.get("chunk_id")
            vector = item.get("embedding")

            if chunk_id is None or vector is None:
                continue

            try:
                chunk_vector = np.asarray(
                    vector,
                    dtype=float,
                )
            except (TypeError, ValueError):
                continue

            if (
                chunk_vector.ndim != 1
                or chunk_vector.size == 0
                or not np.all(
                    np.isfinite(chunk_vector)
                )
            ):
                continue

            chunk_vector = self._safe_normalize_vector(
                chunk_vector
            )

            if chunk_vector.size != focus_vectors.shape[1]:
                raise ValueError(
                    "Chunk embedding dimension does not "
                    "match focus embedding dimension."
                )

            prototype_scores = (
                focus_vectors @ chunk_vector
            )

            top_k = min(
                FOCUS_PROTOTYPE_TOP_K,
                prototype_scores.size,
            )

            if top_k <= 0:
                continue

            strongest_scores = np.sort(
                prototype_scores
            )[-top_k:]

            raw_scores[str(chunk_id)] = float(
                np.mean(strongest_scores)
            )

        return self._calibrate_side_scores(
            raw_scores,
            focus=focus,
            side=side,
        )

    def _calibrate_side_scores(
        self,
        raw_scores: dict[str, float],
        *,
        focus: str,
        side: str,
    ) -> dict[str, float]:
        """
        Convert raw similarities into [0, 1] using an absolute gate plus a
        robust article-local range.

        Local scaling alone is unsafe because it always creates a local winner,
        even for an unrelated article. The article confidence term preserves
        the absolute strength of the evidence.
        """

        if not raw_scores:
            return {}

        config = FOCUS_CALIBRATION[focus]

        article_minimum = config["article_minimum"]
        chunk_floor = config["chunk_floor"]
        strong_reference = config["strong_reference"]

        values = np.asarray(
            list(raw_scores.values()),
            dtype=float,
        )

        article_max = float(np.max(values))

        if article_max <= article_minimum:
            logger.debug(
                "Focus side rejected: focus=%s side=%s "
                "article_max=%.4f minimum=%.4f",
                focus,
                side,
                article_max,
                article_minimum,
            )
            return {
                chunk_id: 0.0
                for chunk_id in raw_scores
            }

        confidence_denominator = (
            strong_reference
            - article_minimum
        )

        if confidence_denominator <= 0.0:
            raise ValueError(
                "strong_reference must be greater than "
                "article_minimum."
            )

        article_confidence = self._clamp(
            (
                article_max
                - article_minimum
            )
            / confidence_denominator
        )

        local_floor = max(
            chunk_floor,
            float(
                np.quantile(
                    values,
                    FOCUS_LOCAL_LOW_QUANTILE,
                )
            ),
        )

        local_ceiling = max(
            float(
                np.quantile(
                    values,
                    FOCUS_LOCAL_HIGH_QUANTILE,
                )
            ),
            local_floor + FOCUS_LOCAL_MIN_SPAN,
        )

        local_denominator = (
            local_ceiling
            - local_floor
        )

        absolute_denominator = (
            strong_reference
            - chunk_floor
        )

        if absolute_denominator <= 0.0:
            raise ValueError(
                "strong_reference must be greater than "
                "chunk_floor."
            )

        calibrated: dict[str, float] = {}

        for chunk_id, raw_similarity in raw_scores.items():
            if raw_similarity <= chunk_floor:
                calibrated[chunk_id] = 0.0
                continue

            local_score = self._clamp(
                (
                    raw_similarity
                    - local_floor
                )
                / local_denominator
            )

            absolute_score = self._clamp(
                (
                    raw_similarity
                    - chunk_floor
                )
                / absolute_denominator
            )

            combined_score = (
                FOCUS_LOCAL_WEIGHT
                * local_score
                + FOCUS_ABSOLUTE_WEIGHT
                * absolute_score
            )

            calibrated[chunk_id] = self._clamp(
                article_confidence
                * combined_score
            )

        logger.debug(
            "Focus calibration: focus=%s side=%s chunks=%d "
            "article_max=%.4f confidence=%.4f "
            "local_floor=%.4f local_ceiling=%.4f",
            focus,
            side,
            len(raw_scores),
            article_max,
            article_confidence,
            local_floor,
            local_ceiling,
        )

        return calibrated

    def _factor_ranking_key(
        self,
        relationship: dict[str, Any],
    ) -> tuple[Any, ...]:
        """
        Rank primarily by pure factor relevance.

        Mapping and base scores are used only as deterministic tie-breakers.
        """

        factor_relevance_score = self._safe_float(
            relationship.get(
                "factor_relevance_score"
            )
        )

        mapping_score = self._safe_float(
            relationship.get(
                "mapping_score"
            )
        )

        base_hybrid_score = self._safe_float(
            relationship.get(
                "base_hybrid_score"
            )
        )

        pair_number = self._safe_int(
            relationship.get("pair_number")
        )

        return (
            -factor_relevance_score,
            -mapping_score,
            -base_hybrid_score,
            pair_number,
        )

    def _select_global_factor(
        self,
        focus_relevance_lookups: dict[
            str,
            dict[str, dict[str, float]],
        ],
    ) -> tuple[
        str | None,
        dict[str, float],
        dict[str, dict[str, float]],
    ]:
        """
        Select one factor for the complete article pair.

        For each factor, both article sides receive an article-level score based
        on the strongest calibrated chunk relevances. The final global score
        uses the same bilateral formula as pair relevance:

            0.80 * geometric_mean(article_a_score, article_b_score)
            + 0.20 * max(article_a_score, article_b_score)

        This favours factors represented in both articles while retaining a
        small allowance when one article covers the factor more strongly.
        """

        factor_scores: dict[str, float] = {}
        factor_side_scores: dict[
            str,
            dict[str, float],
        ] = {}

        for candidate_focus in GENERAL_FOCUS_CANDIDATES:
            lookup = focus_relevance_lookups.get(
                candidate_focus,
                {
                    "a": {},
                    "b": {},
                },
            )

            article_a_score = (
                self._aggregate_article_side_relevance(
                    lookup.get("a", {})
                )
            )
            article_b_score = (
                self._aggregate_article_side_relevance(
                    lookup.get("b", {})
                )
            )

            bilateral_article_relevance = float(
                np.sqrt(
                    article_a_score
                    * article_b_score
                )
            )

            global_score = self._clamp(
                0.80 * bilateral_article_relevance
                + 0.20
                * max(
                    article_a_score,
                    article_b_score,
                )
            )

            factor_scores[candidate_focus] = (
                global_score
            )
            factor_side_scores[candidate_focus] = {
                "a": article_a_score,
                "b": article_b_score,
                "bilateral": (
                    bilateral_article_relevance
                ),
            }

        if not factor_scores:
            return None, {}, {}

        priority = {
            factor_name: index
            for index, factor_name in enumerate(
                GENERAL_FOCUS_CANDIDATES
            )
        }

        selected_factor = max(
            GENERAL_FOCUS_CANDIDATES,
            key=lambda factor_name: (
                factor_scores.get(
                    factor_name,
                    0.0,
                ),
                min(
                    factor_side_scores.get(
                        factor_name,
                        {},
                    ).get("a", 0.0),
                    factor_side_scores.get(
                        factor_name,
                        {},
                    ).get("b", 0.0),
                ),
                (
                    factor_side_scores.get(
                        factor_name,
                        {},
                    ).get("a", 0.0)
                    + factor_side_scores.get(
                        factor_name,
                        {},
                    ).get("b", 0.0)
                ),
                -priority.get(
                    factor_name,
                    len(priority),
                ),
            ),
        )

        return (
            selected_factor,
            factor_scores,
            factor_side_scores,
        )

    def _aggregate_article_side_relevance(
        self,
        relevance_lookup: dict[str, float],
    ) -> float:
        """
        Convert all calibrated chunk relevances from one article side into one
        robust article-level relevance score.

        The strongest quarter of chunks is averaged, capped at twelve chunks.
        This represents the article's dominant focus without allowing one
        isolated paragraph or a large number of unrelated paragraphs to decide
        the global factor.
        """

        values = np.asarray(
            [
                self._clamp(value)
                for value in relevance_lookup.values()
                if math.isfinite(
                    self._safe_float(value)
                )
            ],
            dtype=float,
        )

        if values.size == 0:
            return 0.0

        top_k = max(
            1,
            int(
                math.ceil(
                    values.size
                    * GENERAL_SELECTION_TOP_FRACTION
                )
            ),
        )

        top_k = min(
            top_k,
            GENERAL_SELECTION_MAX_TOP_K,
            values.size,
        )

        strongest_values = np.sort(
            values
        )[-top_k:]

        return self._clamp(
            float(
                np.mean(
                    strongest_values
                )
            )
        )

    def _build_general_result_for_factor(
        self,
        *,
        base_score: float,
        a_chunk_id: str,
        b_chunk_id: str,
        selected_factor: str | None,
        focus_relevance_lookup: dict[
            str,
            dict[str, float],
        ],
        selected_factor_global_score: float | None,
        general_factor_scores: dict[str, float],
        general_factor_side_scores: dict[
            str,
            dict[str, float],
        ],
    ) -> dict[str, Any]:
        """
        Calculate pair relevance using the one globally selected factor.

        General mode deliberately remains non-boosting. It changes only factor
        identification, factor relevance, and factor-specific ranking.
        """

        base_score = self._clamp(
            base_score
        )

        if (
            selected_factor
            not in GENERAL_FOCUS_CANDIDATES
        ):
            return self._general_result(
                base_score=base_score
            )

        a_relevance = self._clamp(
            focus_relevance_lookup
            .get("a", {})
            .get(str(a_chunk_id), 0.0)
        )

        b_relevance = self._clamp(
            focus_relevance_lookup
            .get("b", {})
            .get(str(b_chunk_id), 0.0)
        )

        bilateral_relevance = float(
            np.sqrt(
                a_relevance
                * b_relevance
            )
        )

        factor_relevance_score = self._clamp(
            0.80 * bilateral_relevance
            + 0.20
            * max(
                a_relevance,
                b_relevance,
            )
        )

        return {
            "focus": "general",
            "selected_factor": selected_factor,
            "selected_factor_global_score": (
                selected_factor_global_score
            ),
            "general_factor_scores": dict(
                general_factor_scores
            ),
            "general_factor_side_scores": {
                factor_name: dict(
                    side_scores
                )
                for factor_name, side_scores
                in general_factor_side_scores.items()
            },

            "a_focus_relevance": a_relevance,
            "b_focus_relevance": b_relevance,
            "bilateral_focus_relevance": (
                bilateral_relevance
            ),
            "factor_relevance_score": (
                factor_relevance_score
            ),
            "pair_focus_relevance": (
                factor_relevance_score
            ),

            # General mode remains non-boosting.
            "focus_gate": 0.0,
            "max_focus_boost": 0.0,
            "effective_boost": 0.0,
            "scale_factor": 1.0,
            "factor_adjustment": 0.0,
            "factor_adjustment_percent": 0.0,
            "focus_adjusted_score": base_score,
            "final_score": base_score,
        }

    def _general_result(
        self,
        *,
        base_score: float,
    ) -> dict[str, Any]:
        """Return a safe fallback when no focus result can be calculated."""

        return {
            "focus": "general",
            "selected_factor": None,
            "a_focus_relevance": 0.0,
            "b_focus_relevance": 0.0,
            "bilateral_focus_relevance": 0.0,
            "factor_relevance_score": 0.0,
            "pair_focus_relevance": 0.0,
            "focus_gate": 0.0,
            "max_focus_boost": 0.0,
            "effective_boost": 0.0,
            "scale_factor": 1.0,
            "factor_adjustment": 0.0,
            "factor_adjustment_percent": 0.0,
            "focus_adjusted_score": base_score,
            "final_score": base_score,
        }

    def _get_focus_embeddings(
        self,
        focus: str,
    ) -> np.ndarray:
        """
        Encode and cache all semantic prototypes for the selected focus.

        Return shape:

            (prototype_count, embedding_dimension)
        """

        if focus in self._focus_embedding_cache:
            return self._focus_embedding_cache[
                focus
            ]

        profiles = FOCUS_PROFILES[focus]

        embedding_service = get_embedding_service()

        vectors = embedding_service.model.encode(
            list(profiles),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        vectors = np.asarray(
            vectors,
            dtype=float,
        )

        if (
            vectors.ndim != 2
            or vectors.shape[0] == 0
            or vectors.shape[1] == 0
            or not np.all(np.isfinite(vectors))
        ):
            raise ValueError(
                "Focus embeddings must be a finite "
                "two-dimensional matrix."
            )

        normalized_vectors = np.vstack(
            [
                self._safe_normalize_vector(vector)
                for vector in vectors
            ]
        )

        self._focus_embedding_cache[focus] = (
            normalized_vectors
        )

        return normalized_vectors

    def _compute_focus_gate(
        self,
        base_score: float,
    ) -> float:
        """
        Control only the size of the focus-adjusted display-score boost.
        """

        if base_score <= FOCUS_GATE_START_SCORE:
            return 0.0

        if base_score >= FOCUS_GATE_FULL_SCORE:
            return 1.0

        denominator = (
            FOCUS_GATE_FULL_SCORE
            - FOCUS_GATE_START_SCORE
        )

        if denominator <= 0:
            raise ValueError(
                "FOCUS_GATE_FULL_SCORE must be greater "
                "than FOCUS_GATE_START_SCORE."
            )

        return self._clamp(
            (
                base_score
                - FOCUS_GATE_START_SCORE
            )
            / denominator
        )

    def _safe_normalize_vector(
        self,
        vector: np.ndarray,
    ) -> np.ndarray:
        norm = float(
            np.linalg.norm(vector)
        )

        if not math.isfinite(norm) or norm <= 0.0:
            return np.zeros_like(
                vector,
                dtype=float,
            )

        return vector / norm

    def _get_required_bounded_score(
        self,
        item: dict[str, Any],
        field_name: str,
    ) -> float:
        if field_name not in item:
            raise ValueError(
                "FocusScalingService requires "
                f"{field_name} for every relationship."
            )

        try:
            value = float(item[field_name])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be numeric."
            ) from exc

        if not math.isfinite(value):
            raise ValueError(
                f"{field_name} must be finite."
            )

        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{field_name} must be between 0.0 and 1.0."
            )

        return value

    def _safe_float(
        self,
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return default

        if not math.isfinite(numeric_value):
            return default

        return numeric_value

    def _safe_int(
        self,
        value: Any,
        *,
        default: int = 10**9,
    ) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _clamp(
        self,
        value: float,
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> float:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return minimum

        if not math.isfinite(numeric_value):
            return minimum

        return max(
            minimum,
            min(
                numeric_value,
                maximum,
            ),
        )


_focus_scaling_service = FocusScalingService()


def get_focus_scaling_service(
) -> FocusScalingService:
    return _focus_scaling_service