# backend/app/services/final_cross_mapping_service.py

from __future__ import annotations

import logging
import math
from typing import Any


logger = logging.getLogger(__name__)


# Factor/focus fields belong only to the post-classification display-ranking
# stage. FinalCrossMappingService must neither use nor propagate them.
FACTOR_SCALING_FIELDS: frozenset[str] = frozenset(
    {
        "focus",
        "a_focus_relevance",
        "b_focus_relevance",
        "bilateral_focus_relevance",
        "pair_focus_relevance",
        "factor_relevance_score",
        "factor_rank",
        "focus_gate",
        "max_focus_boost",
        "effective_boost",
        "scale_factor",
        "factor_adjustment",
        "factor_adjustment_percent",
        "focus_adjusted_score",
        "focus_adjusted_hybrid_score",
        "hybrid_score",
    }
)


# Ordinary final mappings must reach this focus-independent mapping score.
DEFAULT_MIN_MAPPING_SCORE = 0.42

# A lower-score candidate may be rescued only when it retains at least this
# much unscaled content relevance.
DEFAULT_RESCUE_MIN_BASE_HYBRID_SCORE = 0.30

# Minimum bidirectional NLI evidence required for contradiction rescue.
DEFAULT_MIN_CONTRADICTION_SCORE = 0.70
DEFAULT_MIN_CONTRADICTION_MARGIN = 0.15


class FinalCrossMappingService:
    """
    Select final one-to-one mappings after bidirectional NLI analysis.

    Input:
        Analysed candidate mappings produced by:

            CandidateCrossMappingService
                -> ContradictionDetectionService

    Final acceptance has two independent paths:

    1. Normal mapping

        mapping_score >= min_mapping_score

    2. Contradiction rescue

        mapping_score < min_mapping_score
        and base_hybrid_score >= rescue_min_base_hybrid_score
        and the candidate came from the strong-signal candidate path
        and bidirectional NLI was evaluated
        and contradiction is the dominant NLI relation
        and contradiction_score >= min_contradiction_score
        and contradiction_margin >= min_contradiction_margin

    After acceptance, this service applies a strict one-to-one rule:

        - each Article A chunk can appear at most once;
        - each Article B chunk can appear at most once.

    Normal mappings are selected before contradiction-rescue mappings.
    This is intentionally conservative: a lower-relevance contradiction
    rescue cannot replace an already accepted ordinary mapping that uses
    the same A or B chunk.

    Factor/focus-scaling fields are neither used nor propagated. They belong
    only to the post-classification display-ranking stage.
    """

    def build_final_mappings(
        self,
        analysed_candidates: list[dict[str, Any]],
        *,
        min_mapping_score: float = DEFAULT_MIN_MAPPING_SCORE,
        rescue_min_base_hybrid_score: float = (
            DEFAULT_RESCUE_MIN_BASE_HYBRID_SCORE
        ),
        min_contradiction_score: float = (
            DEFAULT_MIN_CONTRADICTION_SCORE
        ),
        min_contradiction_margin: float = (
            DEFAULT_MIN_CONTRADICTION_MARGIN
        ),
        max_mappings: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build final strict one-to-one mappings.

        Normal mapping rule:

            mapping_score >= min_mapping_score

        Contradiction rescue rule:

            mapping_score < min_mapping_score
            and base_hybrid_score >= rescue_min_base_hybrid_score
            and strong_signal_candidate is true
            and nli_evaluated is true
            and nli_label == "contradiction"
            and contradiction_is_dominant is true
            and contradiction_score >= min_contradiction_score
            and contradiction_margin >= min_contradiction_margin

        Candidates that pass neither rule are removed.

        Candidates that pass an acceptance rule may still be removed by the
        final strict one-to-one selection when their A or B chunk has already
        been assigned to a higher-priority candidate.
        """

        if not analysed_candidates:
            return []

        self._validate_parameters(
            min_mapping_score=min_mapping_score,
            rescue_min_base_hybrid_score=(
                rescue_min_base_hybrid_score
            ),
            min_contradiction_score=min_contradiction_score,
            min_contradiction_margin=min_contradiction_margin,
            max_mappings=max_mappings,
        )

        accepted_candidates: list[dict[str, Any]] = []

        normal_count = 0
        rescued_count = 0
        not_evaluated_count = 0
        rejected_count = 0

        for raw_candidate in analysed_candidates:
            # Remove any factor/focus fields that may have leaked from an
            # upstream caller. Final mapping must be completely independent
            # of factor scaling.
            candidate = self._strip_factor_scaling_fields(
                raw_candidate
            )

            a_chunk_id = candidate.get("a_chunk_id")
            b_chunk_id = candidate.get("b_chunk_id")

            if not a_chunk_id or not b_chunk_id:
                rejected_count += 1
                continue

            mapping_score = self._get_required_bounded_score(
                candidate,
                "mapping_score",
            )
            base_hybrid_score = self._get_required_bounded_score(
                candidate,
                "base_hybrid_score",
            )

            nli_evaluated = bool(
                candidate.get("nli_evaluated", False)
            )

            # Final mapping occurs after the NLI stage. A candidate whose text
            # could not be evaluated is not allowed into the final result.
            if not nli_evaluated:
                not_evaluated_count += 1
                continue

            contradiction_score = self._get_required_bounded_score(
                candidate,
                "contradiction_score",
            )
            contradiction_margin = self._get_required_margin(
                candidate,
                "contradiction_margin",
            )

            contradiction_is_dominant = bool(
                candidate.get(
                    "contradiction_is_dominant",
                    False,
                )
            )

            nli_label = str(
                candidate.get("nli_label", "")
            ).strip().lower()

            strong_signal_candidate = bool(
                candidate.get(
                    "strong_signal_candidate",
                    False,
                )
                or candidate.get(
                    "potential_contradiction_candidate",
                    False,
                )
            )

            normal_mapping = (
                mapping_score >= min_mapping_score
            )

            contradiction_rescue = (
                not normal_mapping
                and base_hybrid_score
                >= rescue_min_base_hybrid_score
                and strong_signal_candidate
                and nli_label == "contradiction"
                and contradiction_is_dominant
                and contradiction_score
                >= min_contradiction_score
                and contradiction_margin
                >= min_contradiction_margin
            )

            if not normal_mapping and not contradiction_rescue:
                rejected_count += 1
                continue

            accepted = dict(candidate)
            accepted["normal_mapping"] = normal_mapping
            accepted["contradiction_rescue"] = (
                contradiction_rescue
            )
            accepted["final_mapping_reason"] = (
                "normal_mapping"
                if normal_mapping
                else "contradiction_rescue"
            )
            accepted["final_mapping_accepted"] = True

            accepted_candidates.append(accepted)

            if normal_mapping:
                normal_count += 1
            else:
                rescued_count += 1

        if not accepted_candidates:
            logger.info(
                (
                    "Final mapping selection: candidates=%d, "
                    "accepted_before_1v1=0, final_mappings=0, "
                    "normal=0, contradiction_rescue=0, "
                    "nli_not_evaluated=%d, rejected=%d"
                ),
                len(analysed_candidates),
                not_evaluated_count,
                rejected_count,
            )
            return []

        # Conservative strict 1v1 ranking:
        #
        # 1. Normal mappings are considered before contradiction rescues.
        # 2. Normal mappings are ranked primarily by mapping_score.
        # 3. Rescued mappings are ranked primarily by contradiction_score and
        #    contradiction_margin, then by their remaining mapping evidence.
        #
        # No arithmetic mixture of mapping_score and contradiction_score is
        # created because they represent different concepts.
        ranked_candidates = sorted(
            accepted_candidates,
            key=self._selection_key,
        )

        final_mappings: list[dict[str, Any]] = []
        used_a: set[str] = set()
        used_b: set[str] = set()

        conflict_rejected_count = 0

        for candidate in ranked_candidates:
            a_chunk_id = candidate.get("a_chunk_id")
            b_chunk_id = candidate.get("b_chunk_id")

            a_key = str(a_chunk_id)
            b_key = str(b_chunk_id)

            # Strict 1v1:
            # both sides must still be unused.
            if a_key in used_a or b_key in used_b:
                conflict_rejected_count += 1
                continue

            # Sanitize once more before returning the selected mapping.
            selected = self._strip_factor_scaling_fields(
                candidate
            )
            selected["final_selection_rank"] = (
                len(final_mappings) + 1
            )

            final_mappings.append(selected)
            used_a.add(a_key)
            used_b.add(b_key)

            if (
                max_mappings is not None
                and len(final_mappings) >= max_mappings
            ):
                break

        # Restore Article A/B order for frontend display after the strict 1v1
        # decision has been completed.
        final_mappings.sort(
            key=lambda item: (
                self._safe_int(
                    item.get("a_chunk_index")
                ),
                self._safe_int(
                    item.get("b_chunk_index")
                ),
            )
        )

        logger.info(
            (
                "Final mapping selection: candidates=%d, "
                "accepted_before_1v1=%d, final_mappings=%d, "
                "normal=%d, contradiction_rescue=%d, "
                "nli_not_evaluated=%d, rule_rejected=%d, "
                "one_to_one_conflicts=%d"
            ),
            len(analysed_candidates),
            len(accepted_candidates),
            len(final_mappings),
            normal_count,
            rescued_count,
            not_evaluated_count,
            rejected_count,
            conflict_rejected_count,
        )

        return final_mappings

    def _selection_key(
        self,
        candidate: dict[str, Any],
    ) -> tuple[Any, ...]:
        """
        Return a deterministic ranking key for strict one-to-one selection.

        Normal mappings receive the first priority tier.

        Within the normal tier:
            1. higher mapping_score;
            2. higher base_hybrid_score;
            3. higher contradiction_score as a deterministic tie-breaker.

        Within the contradiction-rescue tier:
            1. higher contradiction_score;
            2. higher contradiction_margin;
            3. higher mapping_score;
            4. higher base_hybrid_score.

        Article order is used only as the final deterministic tie-breaker.
        """

        normal_mapping = bool(
            candidate.get("normal_mapping", False)
        )

        mapping_score = self._safe_float(
            candidate.get("mapping_score")
        )
        base_hybrid_score = self._safe_float(
            candidate.get("base_hybrid_score")
        )
        contradiction_score = self._safe_float(
            candidate.get("contradiction_score")
        )
        contradiction_margin = self._safe_float(
            candidate.get("contradiction_margin"),
            default=-1.0,
        )

        a_order = self._safe_int(
            candidate.get("a_chunk_index")
        )
        b_order = self._safe_int(
            candidate.get("b_chunk_index")
        )

        if normal_mapping:
            return (
                0,
                -mapping_score,
                -base_hybrid_score,
                -contradiction_score,
                a_order,
                b_order,
            )

        return (
            1,
            -contradiction_score,
            -contradiction_margin,
            -mapping_score,
            -base_hybrid_score,
            a_order,
            b_order,
        )

    def _strip_factor_scaling_fields(
        self,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Return a copy without any factor/focus-scaling fields.

        This is a defensive boundary. Under the intended pipeline, these
        fields do not exist yet because factor scaling runs only after
        relationship classification.
        """

        return {
            key: value
            for key, value in candidate.items()
            if key not in FACTOR_SCALING_FIELDS
        }

    def _get_required_bounded_score(
        self,
        candidate: dict[str, Any],
        field_name: str,
    ) -> float:
        """
        Return a required finite score in the inclusive range [0, 1].
        """

        if field_name not in candidate:
            raise ValueError(
                "FinalCrossMappingService requires "
                f"{field_name} for every analysed candidate."
            )

        value = self._get_required_float(
            candidate,
            field_name,
        )

        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{field_name} must be between 0.0 and 1.0."
            )

        return value

    def _get_required_margin(
        self,
        candidate: dict[str, Any],
        field_name: str,
    ) -> float:
        """
        Return a required finite NLI margin in the range [-1, 1].
        """

        if field_name not in candidate:
            raise ValueError(
                "FinalCrossMappingService requires "
                f"{field_name} for every NLI-evaluated candidate."
            )

        value = self._get_required_float(
            candidate,
            field_name,
        )

        if not -1.0 <= value <= 1.0:
            raise ValueError(
                f"{field_name} must be between -1.0 and 1.0."
            )

        return value

    def _get_required_float(
        self,
        candidate: dict[str, Any],
        field_name: str,
    ) -> float:
        try:
            value = float(candidate[field_name])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be numeric."
            ) from exc

        if not math.isfinite(value):
            raise ValueError(
                f"{field_name} must be finite."
            )

        return value

    def _validate_parameters(
        self,
        *,
        min_mapping_score: float,
        rescue_min_base_hybrid_score: float,
        min_contradiction_score: float,
        min_contradiction_margin: float,
        max_mappings: int | None,
    ) -> None:
        bounded_values = {
            "min_mapping_score": min_mapping_score,
            "rescue_min_base_hybrid_score": (
                rescue_min_base_hybrid_score
            ),
            "min_contradiction_score": (
                min_contradiction_score
            ),
            "min_contradiction_margin": (
                min_contradiction_margin
            ),
        }

        for name, value in bounded_values.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be between 0.0 and 1.0."
                )

        if (
            rescue_min_base_hybrid_score
            > min_mapping_score
        ):
            raise ValueError(
                "rescue_min_base_hybrid_score must be less than "
                "or equal to min_mapping_score."
            )

        if max_mappings is not None and max_mappings <= 0:
            raise ValueError(
                "max_mappings must be a positive integer or None."
            )

    def _safe_float(
        self,
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError):
            return default

        if not math.isfinite(converted):
            return default

        return converted

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


_final_cross_mapping_service = FinalCrossMappingService()


def get_final_cross_mapping_service(
) -> FinalCrossMappingService:
    return _final_cross_mapping_service