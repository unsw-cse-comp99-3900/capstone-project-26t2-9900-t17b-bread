# backend/app/services/contradiction_detection_service.py

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sentence_transformers import CrossEncoder


logger = logging.getLogger(__name__)


DEFAULT_NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-base"


class ContradictionDetectionService:
    """
    Run bidirectional Natural Language Inference on candidate mappings.

    CandidateCrossMappingService has already performed the permissive
    relevance screening and calculated mapping_score. This service does not
    apply another score threshold.

    Every candidate mapping with valid text is evaluated in both directions:

        Article A -> Article B
        Article B -> Article A

    The service preserves all candidate-mapping metadata and adds directional
    and combined NLI scores. Numeric differences, casualty rules, and scope
    heuristics are intentionally ignored.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_NLI_MODEL_NAME,
    ) -> None:
        self.model_name = model_name

        self.model = CrossEncoder(
            model_name,
            activation_fn=None,
        )

        self.label_names = self._resolve_label_names()

    def analyse_mappings(
        self,
        candidate_mappings: list[dict[str, Any]],
        *,
        chunks_a: list[dict[str, Any]],
        chunks_b: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Add bidirectional NLI scores to every candidate mapping.

        CandidateCrossMappingService has already:

        1. applied permissive content-relevance screening;
        2. retained ordinary and strong-signal candidates;
        3. calculated context_support, context_boost, and mapping_score.

        This service therefore does not use mapping_score,
        base_hybrid_score, hybrid_score, cosine_score, or bm25_score as an
        additional NLI eligibility gate.

        Every candidate mapping with resolvable text is evaluated in both
        directions. A candidate remains in the output with
        ``nli_evaluated=False`` only when one or both chunk texts cannot be
        resolved.
        """

        if not candidate_mappings:
            return []

        text_lookup = self._build_text_lookup(
            chunks_a,
            chunks_b,
        )

        # Copy each candidate so the input collection is not mutated.
        # All CandidateCrossMappingService metadata is preserved.
        enriched_candidates = [
            dict(mapping)
            for mapping in candidate_mappings
        ]

        directional_pairs: list[tuple[str, str]] = []
        evaluated_indexes: list[int] = []

        missing_text_count = 0

        for index, mapping in enumerate(enriched_candidates):
            self._initialise_nli_fields(mapping)

            a_chunk_id = mapping.get("a_chunk_id")
            b_chunk_id = mapping.get("b_chunk_id")

            a_text = text_lookup.get(str(a_chunk_id), "")
            b_text = text_lookup.get(str(b_chunk_id), "")

            if not a_text or not b_text:
                mapping["nli_skip_reason"] = "missing_chunk_text"
                missing_text_count += 1
                continue

            # Every item reaching this service has already passed the
            # permissive candidate-mapping stage. Run NLI for all candidates
            # with valid text, including low mapping-score candidates retained
            # through the strong-signal path.
            directional_pairs.extend(
                [
                    (a_text, b_text),
                    (b_text, a_text),
                ]
            )

            evaluated_indexes.append(index)

        logger.info(
            (
                "Candidate NLI preparation: total_candidates=%d, "
                "evaluated_candidates=%d, directional_pairs=%d, "
                "missing_text=%d"
            ),
            len(enriched_candidates),
            len(evaluated_indexes),
            len(directional_pairs),
            missing_text_count,
        )

        if not directional_pairs:
            return enriched_candidates

        logits = self.model.predict(
            directional_pairs,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        probabilities = self._softmax(logits)

        expected_prediction_count = (
            len(evaluated_indexes) * 2
        )

        if len(probabilities) != expected_prediction_count:
            raise RuntimeError(
                "The NLI model returned an unexpected number of predictions: "
                f"expected {expected_prediction_count}, "
                f"received {len(probabilities)}."
            )

        for evaluated_position, mapping_index in enumerate(
            evaluated_indexes
        ):
            forward_scores = self._scores_by_label(
                probabilities[evaluated_position * 2]
            )

            reverse_scores = self._scores_by_label(
                probabilities[evaluated_position * 2 + 1]
            )

            mapping = enriched_candidates[mapping_index]

            self._apply_bidirectional_nli_scores(
                mapping,
                forward_scores=forward_scores,
                reverse_scores=reverse_scores,
            )

            mapping["nli_evaluated"] = True
            mapping["nli_skip_reason"] = None

            logger.debug(
                (
                    "Candidate NLI result: "
                    "a_chunk_id=%s, b_chunk_id=%s, "
                    "candidate_reason=%s, "
                    "base_hybrid_score=%.4f, mapping_score=%.4f, "
                    "cosine_score=%.4f, bm25_score=%.4f, "
                    "forward_contradiction=%.4f, "
                    "reverse_contradiction=%.4f, "
                    "combined_contradiction=%.4f, "
                    "combined_entailment=%.4f, "
                    "combined_neutral=%.4f, "
                    "contradiction_margin=%.4f, "
                    "nli_label=%s"
                ),
                mapping.get("a_chunk_id"),
                mapping.get("b_chunk_id"),
                mapping.get("candidate_reason"),
                self._safe_float(
                    mapping.get("base_hybrid_score")
                ),
                self._safe_float(
                    mapping.get("mapping_score")
                ),
                self._safe_float(
                    mapping.get("cosine_score")
                ),
                self._safe_float(
                    mapping.get("bm25_score")
                ),
                mapping["forward_contradiction_score"],
                mapping["reverse_contradiction_score"],
                mapping["contradiction_score"],
                mapping["entailment_score"],
                mapping["neutral_score"],
                mapping["contradiction_margin"],
                mapping["nli_label"],
            )

        return enriched_candidates

    def _apply_bidirectional_nli_scores(
        self,
        mapping: dict[str, Any],
        *,
        forward_scores: dict[str, float],
        reverse_scores: dict[str, float],
    ) -> None:
        """
        Store directional scores and calculate combined bidirectional scores.

        Both directions receive equal weight through an arithmetic mean.
        """

        mapping["forward_entailment_score"] = (
            forward_scores["entailment"]
        )
        mapping["forward_neutral_score"] = (
            forward_scores["neutral"]
        )
        mapping["forward_contradiction_score"] = (
            forward_scores["contradiction"]
        )

        mapping["reverse_entailment_score"] = (
            reverse_scores["entailment"]
        )
        mapping["reverse_neutral_score"] = (
            reverse_scores["neutral"]
        )
        mapping["reverse_contradiction_score"] = (
            reverse_scores["contradiction"]
        )

        combined_entailment = (
            forward_scores["entailment"]
            + reverse_scores["entailment"]
        ) / 2.0

        combined_neutral = (
            forward_scores["neutral"]
            + reverse_scores["neutral"]
        ) / 2.0

        combined_contradiction = (
            forward_scores["contradiction"]
            + reverse_scores["contradiction"]
        ) / 2.0

        strongest_non_contradiction = max(
            combined_entailment,
            combined_neutral,
        )

        contradiction_margin = (
            combined_contradiction
            - strongest_non_contradiction
        )

        combined_scores = {
            "entailment": combined_entailment,
            "neutral": combined_neutral,
            "contradiction": combined_contradiction,
        }

        mapping["entailment_score"] = combined_entailment
        mapping["neutral_score"] = combined_neutral
        mapping["contradiction_score"] = (
            combined_contradiction
        )

        mapping["contradiction_margin"] = (
            contradiction_margin
        )

        mapping["contradiction_is_dominant"] = (
            combined_contradiction
            > combined_entailment
            and combined_contradiction
            > combined_neutral
        )

        mapping["nli_label"] = max(
            combined_scores,
            key=combined_scores.get,
        )

    def _initialise_nli_fields(
        self,
        mapping: dict[str, Any],
    ) -> None:
        """
        Initialise all NLI fields.

        Compatibility flags remain present and are always false so existing
        downstream code does not fail, but no numeric or scope logic is used.
        """

        mapping["entailment_score"] = 0.0
        mapping["neutral_score"] = 0.0
        mapping["contradiction_score"] = 0.0

        mapping["forward_entailment_score"] = 0.0
        mapping["forward_neutral_score"] = 0.0
        mapping["forward_contradiction_score"] = 0.0

        mapping["reverse_entailment_score"] = 0.0
        mapping["reverse_neutral_score"] = 0.0
        mapping["reverse_contradiction_score"] = 0.0

        mapping["contradiction_margin"] = 0.0
        mapping["contradiction_is_dominant"] = False

        mapping["has_numeric_difference"] = False
        mapping["casualty_numeric_difference"] = False
        mapping["explicit_casualty_conflict"] = False
        mapping["scope_mismatch"] = False

        mapping["nli_label"] = "not_evaluated"
        mapping["nli_evaluated"] = False
        mapping["nli_skip_reason"] = None

    def _resolve_label_names(
        self,
    ) -> list[str]:
        """
        Resolve the NLI model output-label order.
        """

        config = self.model.model.config

        id_to_label = getattr(
            config,
            "id2label",
            {},
        )

        if not id_to_label:
            raise ValueError(
                "The NLI model does not expose id2label metadata."
            )

        labels: list[str] = []

        for index in range(len(id_to_label)):
            raw_label = str(
                id_to_label.get(
                    index,
                    id_to_label.get(str(index), ""),
                )
            ).strip().lower()

            if "contradiction" in raw_label:
                labels.append("contradiction")
            elif "entailment" in raw_label:
                labels.append("entailment")
            elif "neutral" in raw_label:
                labels.append("neutral")
            else:
                raise ValueError(
                    f"Unsupported NLI label: {raw_label!r}"
                )

        required_labels = {
            "contradiction",
            "entailment",
            "neutral",
        }

        if set(labels) != required_labels:
            raise ValueError(
                "The selected NLI model must expose contradiction, "
                "entailment, and neutral labels."
            )

        if len(labels) != len(required_labels):
            raise ValueError(
                "The selected NLI model exposes duplicate or unexpected "
                "output labels."
            )

        return labels

    def _scores_by_label(
        self,
        probability_vector: np.ndarray,
    ) -> dict[str, float]:
        """
        Convert one probability vector into named NLI scores.
        """

        vector = np.asarray(
            probability_vector,
            dtype=float,
        )

        if vector.ndim != 1:
            raise ValueError(
                "Expected a one-dimensional NLI probability vector."
            )

        if len(vector) != len(self.label_names):
            raise ValueError(
                "The NLI probability vector does not match the "
                "configured label count."
            )

        scores = {
            "contradiction": 0.0,
            "entailment": 0.0,
            "neutral": 0.0,
        }

        for index, label in enumerate(
            self.label_names
        ):
            scores[label] = float(vector[index])

        return scores

    def _softmax(
        self,
        logits: np.ndarray,
    ) -> np.ndarray:
        """
        Convert raw model logits into probability distributions.
        """

        logits_array = np.asarray(
            logits,
            dtype=float,
        )

        if logits_array.ndim == 1:
            logits_array = logits_array.reshape(
                1,
                -1,
            )

        if logits_array.ndim != 2:
            raise ValueError(
                "Expected NLI logits to be a one- or "
                "two-dimensional array."
            )

        if (
            logits_array.shape[1]
            != len(self.label_names)
        ):
            raise ValueError(
                "The NLI logits do not match the configured label count."
            )

        shifted = logits_array - np.max(
            logits_array,
            axis=1,
            keepdims=True,
        )

        exponentials = np.exp(shifted)

        denominator = np.sum(
            exponentials,
            axis=1,
            keepdims=True,
        )

        if np.any(denominator == 0):
            raise ValueError(
                "Unable to normalise NLI logits because the "
                "softmax denominator is zero."
            )

        return exponentials / denominator

    def _build_text_lookup(
        self,
        chunks_a: list[dict[str, Any]],
        chunks_b: list[dict[str, Any]],
    ) -> dict[str, str]:
        """
        Build a chunk-ID-to-clean-text lookup.
        """

        lookup: dict[str, str] = {}

        for chunk in chunks_a + chunks_b:
            chunk_id = chunk.get("chunk_id")

            text = " ".join(
                str(
                    chunk.get("text", "")
                ).split()
            )

            if chunk_id is not None and text:
                lookup[str(chunk_id)] = text

        return lookup

    def _safe_float(
        self,
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        """
        Safely convert a value to a finite float.
        """

        try:
            converted = float(value)
        except (TypeError, ValueError):
            return default

        if not np.isfinite(converted):
            return default

        return converted


_contradiction_detection_service: (
    ContradictionDetectionService | None
) = None


def get_contradiction_detection_service(
) -> ContradictionDetectionService:
    """
    Return the shared contradiction-detection service instance.
    """

    global _contradiction_detection_service

    if _contradiction_detection_service is None:
        _contradiction_detection_service = (
            ContradictionDetectionService()
        )

    return _contradiction_detection_service