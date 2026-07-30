# backend/app/services/relationship_classification_service.py

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Divergence thresholds
# ---------------------------------------------------------------------------

# For normal final mappings, contradiction must be the dominant bidirectional
# NLI result. Contradiction-rescue mappings have already passed stricter
# thresholds in FinalCrossMappingService and are classified as divergent
# directly.
MIN_CONTRADICTION_SCORE = 0.52
MIN_CONTRADICTION_MARGIN = 0.03

# Very strong contradiction can pass with a smaller positive margin.
VERY_STRONG_CONTRADICTION_SCORE = 0.68
VERY_STRONG_CONTRADICTION_MARGIN = 0.02


# ---------------------------------------------------------------------------
# Alignment thresholds
# ---------------------------------------------------------------------------

# Strong semantic route.
MIN_ALIGNED_MAPPING_SCORE = 0.62
MIN_ALIGNED_BASE_HYBRID_SCORE = 0.54
MIN_ALIGNED_COSINE_SCORE = 0.56

# Balanced semantic and lexical route.
MIN_BALANCED_ALIGNED_MAPPING_SCORE = 0.58
MIN_BALANCED_ALIGNED_BASE_HYBRID_SCORE = 0.50
MIN_BALANCED_ALIGNED_COSINE_SCORE = 0.50
MIN_ALIGNED_BM25_SCORE = 0.16

# NLI thresholds.
MIN_ALIGNED_ENTAILMENT_SCORE = 0.45
MAX_ALIGNED_CONTRADICTION_SCORE = 0.45

# Very high similarity may support alignment when one paragraph contains
# additional detail and bidirectional NLI returns neutral.
VERY_STRONG_MAPPING_SCORE = 0.76
VERY_STRONG_COSINE_SCORE = 0.68


class RelationshipClassificationService:
    """
    Classify accepted final one-to-one cross-article mappings.

    This service runs after:

        1. cosine similarity;
        2. BM25 similarity;
        3. base hybrid scoring;
        4. candidate cross mapping;
        5. bidirectional contradiction/NLI detection;
        6. final cross mapping with strict one-to-one selection.

    Every input pair has already been accepted by FinalCrossMappingService
    through either:

        - normal_mapping; or
        - contradiction_rescue.

    This service only assigns one public relationship label:

        - aligned;
        - partially_aligned;
        - divergent.

    It does not reject mappings, does not produce an unrelated label, and
    neither calculates, uses, nor propagates factor/focus-scaling data.
    """

    def classify_mappings(
        self,
        final_mappings: list[dict[str, Any]],
        *,
        chunks_a: list[dict[str, Any]] | None = None,
        chunks_b: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Classify every accepted final mapping.

        Input order is preserved. FinalCrossMappingService is responsible for
        acceptance and strict one-to-one selection; this method does not perform
        another relevance filter.
        """

        if not final_mappings:
            return []

        text_lookup = self._build_text_lookup(
            chunks_a or [],
            chunks_b or [],
        )

        relationships: list[dict[str, Any]] = []

        for pair_number, mapping in enumerate(
            final_mappings,
            start=1,
        ):
            self._validate_final_mapping(mapping)

            label, reason_code = self._classify_single_mapping(
                mapping
            )

            confidence = self._estimate_confidence(
                mapping,
                label=label,
                reason_code=reason_code,
            )

            a_chunk_id = mapping.get("a_chunk_id")
            b_chunk_id = mapping.get("b_chunk_id")

            base_hybrid_score = self._get_base_hybrid_score(
                mapping
            )
            mapping_score = self._get_mapping_score(
                mapping
            )
            relationship = {
                "pair_number": pair_number,

                "a_chunk_id": a_chunk_id,
                "b_chunk_id": b_chunk_id,

                "a_chunk_index": mapping.get(
                    "a_chunk_index"
                ),
                "b_chunk_index": mapping.get(
                    "b_chunk_index"
                ),

                "a_paragraph_index": mapping.get(
                    "a_paragraph_index"
                ),
                "b_paragraph_index": mapping.get(
                    "b_paragraph_index"
                ),

                "a_article_ref": mapping.get(
                    "a_article_ref"
                ),
                "b_article_ref": mapping.get(
                    "b_article_ref"
                ),

                "label": label,
                "confidence": confidence,
                "reason_code": reason_code,

                # Final mapping provenance.
                "normal_mapping": bool(
                    mapping.get("normal_mapping", False)
                ),
                "contradiction_rescue": bool(
                    mapping.get(
                        "contradiction_rescue",
                        False,
                    )
                ),
                "final_mapping_reason": mapping.get(
                    "final_mapping_reason"
                ),
                "final_mapping_accepted": bool(
                    mapping.get(
                        "final_mapping_accepted",
                        True,
                    )
                ),
                "final_selection_rank": mapping.get(
                    "final_selection_rank"
                ),

                # Candidate provenance.
                "candidate_reason": mapping.get(
                    "candidate_reason"
                ),
                "ordinary_candidate": bool(
                    mapping.get(
                        "ordinary_candidate",
                        False,
                    )
                ),
                "strong_signal_candidate": bool(
                    mapping.get(
                        "strong_signal_candidate",
                        False,
                    )
                ),

                # Similarity and mapping evidence.
                "cosine_score": self._safe_float(
                    mapping.get("cosine_score")
                ),
                "bm25_score": self._safe_float(
                    mapping.get("bm25_score")
                ),
                "bm25_raw_score": self._safe_float(
                    mapping.get("bm25_raw_score")
                ),
                "base_hybrid_score": base_hybrid_score,

                "mapping_score": mapping_score,
                "context_support": self._safe_float(
                    mapping.get("context_support")
                ),
                "context_boost": self._safe_float(
                    mapping.get("context_boost")
                ),

                # Combined bidirectional NLI evidence.
                "nli_evaluated": True,
                "nli_label": mapping.get(
                    "nli_label",
                    "not_evaluated",
                ),
                "entailment_score": (
                    self._get_required_bounded_score(
                        mapping,
                        "entailment_score",
                    )
                ),
                "neutral_score": (
                    self._get_required_bounded_score(
                        mapping,
                        "neutral_score",
                    )
                ),
                "contradiction_score": (
                    self._get_required_bounded_score(
                        mapping,
                        "contradiction_score",
                    )
                ),
                "contradiction_margin": (
                    self._get_contradiction_margin(
                        mapping
                    )
                ),
                "contradiction_is_dominant": bool(
                    mapping.get(
                        "contradiction_is_dominant",
                        False,
                    )
                ),

                # Directional NLI evidence.
                "forward_entailment_score": (
                    self._safe_float(
                        mapping.get(
                            "forward_entailment_score"
                        )
                    )
                ),
                "forward_neutral_score": (
                    self._safe_float(
                        mapping.get(
                            "forward_neutral_score"
                        )
                    )
                ),
                "forward_contradiction_score": (
                    self._safe_float(
                        mapping.get(
                            "forward_contradiction_score"
                        )
                    )
                ),
                "reverse_entailment_score": (
                    self._safe_float(
                        mapping.get(
                            "reverse_entailment_score"
                        )
                    )
                ),
                "reverse_neutral_score": (
                    self._safe_float(
                        mapping.get(
                            "reverse_neutral_score"
                        )
                    )
                ),
                "reverse_contradiction_score": (
                    self._safe_float(
                        mapping.get(
                            "reverse_contradiction_score"
                        )
                    )
                ),

                "a_text_preview": self._preview(
                    text_lookup.get(
                        str(a_chunk_id),
                        "",
                    )
                ),
                "b_text_preview": self._preview(
                    text_lookup.get(
                        str(b_chunk_id),
                        "",
                    )
                ),
            }

            relationships.append(relationship)

        return relationships

    def _classify_single_mapping(
        self,
        mapping: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Classify one already accepted final mapping.

        Decision order:

            1. contradiction rescue -> divergent;
            2. other strong bidirectional contradiction -> divergent;
            3. strong similarity with compatible NLI -> aligned;
            4. every remaining accepted final mapping -> partially_aligned.
        """

        cosine_score = self._safe_float(
            mapping.get("cosine_score")
        )
        bm25_score = self._safe_float(
            mapping.get("bm25_score")
        )
        base_hybrid_score = self._get_base_hybrid_score(
            mapping
        )
        mapping_score = self._get_mapping_score(
            mapping
        )

        entailment_score = self._get_required_bounded_score(
            mapping,
            "entailment_score",
        )
        neutral_score = self._get_required_bounded_score(
            mapping,
            "neutral_score",
        )
        contradiction_score = (
            self._get_required_bounded_score(
                mapping,
                "contradiction_score",
            )
        )
        contradiction_margin = (
            self._get_contradiction_margin(
                mapping
            )
        )

        contradiction_is_dominant = bool(
            mapping.get(
                "contradiction_is_dominant",
                contradiction_score
                > max(
                    entailment_score,
                    neutral_score,
                ),
            )
        )

        # FinalCrossMappingService has already validated the stricter rescue
        # conditions. Do not re-apply a mapping-score or cosine-score gate.
        if bool(
            mapping.get(
                "contradiction_rescue",
                False,
            )
        ):
            return (
                "divergent",
                (
                    "contradiction_rescue_with_"
                    "strong_bidirectional_nli"
                ),
            )

        if self._has_strong_contradiction(mapping):
            return (
                "divergent",
                (
                    "same_claim_with_"
                    "bidirectional_nli_contradiction"
                ),
            )

        alignment_reason = self._get_alignment_reason(
            entailment_score=entailment_score,
            neutral_score=neutral_score,
            contradiction_score=contradiction_score,
            contradiction_margin=contradiction_margin,
            contradiction_is_dominant=(
                contradiction_is_dominant
            ),
            mapping_score=mapping_score,
            base_hybrid_score=base_hybrid_score,
            cosine_score=cosine_score,
            bm25_score=bm25_score,
        )

        if alignment_reason is not None:
            return (
                "aligned",
                alignment_reason,
            )

        if neutral_score >= max(
            entailment_score,
            contradiction_score,
        ):
            return (
                "partially_aligned",
                "related_content_with_nli_neutrality",
            )

        if entailment_score > contradiction_score:
            return (
                "partially_aligned",
                (
                    "partial_support_with_"
                    "additional_information"
                ),
            )

        if (
            cosine_score >= MIN_ALIGNED_COSINE_SCORE
            and bm25_score < MIN_ALIGNED_BM25_SCORE
        ):
            return (
                "partially_aligned",
                (
                    "semantic_match_with_"
                    "lexical_difference"
                ),
            )

        return (
            "partially_aligned",
            "accepted_mapping_with_moderate_alignment",
        )

    def _has_strong_contradiction(
        self,
        mapping: dict[str, Any],
    ) -> bool:
        """
        Return True when NLI provides strong contradiction evidence.

        FinalCrossMappingService has already established that the pair is a
        valid final mapping. This method therefore does not apply another
        mapping-score, cosine-score, BM25-score, or base-score threshold.
        """

        if not bool(
            mapping.get("nli_evaluated", False)
        ):
            return False

        # A rescued candidate has already passed the stricter contradiction
        # thresholds in FinalCrossMappingService.
        if bool(
            mapping.get(
                "contradiction_rescue",
                False,
            )
        ):
            return True

        contradiction_score = (
            self._get_required_bounded_score(
                mapping,
                "contradiction_score",
            )
        )
        contradiction_margin = (
            self._get_contradiction_margin(
                mapping
            )
        )

        entailment_score = self._get_required_bounded_score(
            mapping,
            "entailment_score",
        )
        neutral_score = self._get_required_bounded_score(
            mapping,
            "neutral_score",
        )

        contradiction_is_dominant = bool(
            mapping.get(
                "contradiction_is_dominant",
                contradiction_score
                > max(
                    entailment_score,
                    neutral_score,
                ),
            )
        )

        if not contradiction_is_dominant:
            return False

        if (
            contradiction_score
            >= VERY_STRONG_CONTRADICTION_SCORE
        ):
            return (
                contradiction_margin
                >= VERY_STRONG_CONTRADICTION_MARGIN
            )

        return (
            contradiction_score
            >= MIN_CONTRADICTION_SCORE
            and contradiction_margin
            >= MIN_CONTRADICTION_MARGIN
        )

    def _get_alignment_reason(
        self,
        *,
        entailment_score: float,
        neutral_score: float,
        contradiction_score: float,
        contradiction_margin: float,
        contradiction_is_dominant: bool,
        mapping_score: float,
        base_hybrid_score: float,
        cosine_score: float,
        bm25_score: float,
    ) -> str | None:
        """
        Return an alignment reason when similarity is strong and NLI does not
        provide meaningful contradiction evidence.
        """

        strong_semantic_alignment = (
            mapping_score >= MIN_ALIGNED_MAPPING_SCORE
            and base_hybrid_score
            >= MIN_ALIGNED_BASE_HYBRID_SCORE
            and cosine_score >= MIN_ALIGNED_COSINE_SCORE
        )

        balanced_alignment = (
            mapping_score
            >= MIN_BALANCED_ALIGNED_MAPPING_SCORE
            and base_hybrid_score
            >= MIN_BALANCED_ALIGNED_BASE_HYBRID_SCORE
            and cosine_score
            >= MIN_BALANCED_ALIGNED_COSINE_SCORE
            and bm25_score >= MIN_ALIGNED_BM25_SCORE
        )

        very_strong_similarity = (
            mapping_score >= VERY_STRONG_MAPPING_SCORE
            and cosine_score >= VERY_STRONG_COSINE_SCORE
        )

        if not (
            strong_semantic_alignment
            or balanced_alignment
            or very_strong_similarity
        ):
            return None

        contradiction_blocks_alignment = (
            contradiction_is_dominant
            and contradiction_score >= 0.50
            and contradiction_margin >= 0.03
        )

        if contradiction_blocks_alignment:
            return None

        if (
            contradiction_score
            > MAX_ALIGNED_CONTRADICTION_SCORE
        ):
            return None

        if (
            entailment_score
            >= MIN_ALIGNED_ENTAILMENT_SCORE
            and entailment_score > contradiction_score
        ):
            return (
                "strong_similarity_with_nli_entailment"
            )

        if (
            neutral_score >= entailment_score
            and contradiction_score < 0.35
            and (
                very_strong_similarity
                or strong_semantic_alignment
                or balanced_alignment
            )
        ):
            return (
                "strong_shared_content_with_"
                "additional_detail"
            )

        if (
            entailment_score >= 0.35
            and entailment_score > contradiction_score
            and (
                strong_semantic_alignment
                or balanced_alignment
            )
        ):
            return (
                "strong_similarity_with_"
                "partial_nli_support"
            )

        if (
            contradiction_score < 0.30
            and (
                very_strong_similarity
                or strong_semantic_alignment
            )
        ):
            return (
                "strong_similarity_without_"
                "meaningful_contradiction"
            )

        return None

    def _estimate_confidence(
        self,
        mapping: dict[str, Any],
        *,
        label: str,
        reason_code: str,
    ) -> str:
        """
        Estimate categorical evidence strength for the assigned label.

        This is not a calibrated probability.
        """

        mapping_score = self._get_mapping_score(
            mapping
        )
        cosine_score = self._safe_float(
            mapping.get("cosine_score")
        )
        bm25_score = self._safe_float(
            mapping.get("bm25_score")
        )
        base_hybrid_score = self._get_base_hybrid_score(
            mapping
        )

        entailment_score = self._get_required_bounded_score(
            mapping,
            "entailment_score",
        )
        neutral_score = self._get_required_bounded_score(
            mapping,
            "neutral_score",
        )
        contradiction_score = (
            self._get_required_bounded_score(
                mapping,
                "contradiction_score",
            )
        )
        contradiction_margin = max(
            0.0,
            self._get_contradiction_margin(mapping),
        )

        if label == "divergent":
            margin_support = self._clamp(
                contradiction_margin / 0.40
            )

            if bool(
                mapping.get(
                    "contradiction_rescue",
                    False,
                )
            ):
                evidence_score = (
                    0.65 * contradiction_score
                    + 0.20 * margin_support
                    + 0.10 * base_hybrid_score
                    + 0.05
                    * max(
                        cosine_score,
                        bm25_score,
                    )
                )
            else:
                evidence_score = (
                    0.55 * contradiction_score
                    + 0.20 * margin_support
                    + 0.15 * mapping_score
                    + 0.10 * base_hybrid_score
                )

        elif label == "aligned":
            similarity_evidence = (
                0.35 * mapping_score
                + 0.30 * cosine_score
                + 0.20 * base_hybrid_score
                + 0.15 * bm25_score
            )

            nli_alignment_support = max(
                entailment_score,
                1.0 - contradiction_score,
            )

            evidence_score = (
                0.75 * similarity_evidence
                + 0.25 * nli_alignment_support
            )

        elif label == "partially_aligned":
            relation_evidence = (
                0.40 * mapping_score
                + 0.30 * cosine_score
                + 0.15 * base_hybrid_score
                + 0.15 * bm25_score
            )

            partiality_evidence = max(
                neutral_score,
                min(
                    entailment_score,
                    1.0 - contradiction_score,
                ),
            )

            evidence_score = (
                0.70 * relation_evidence
                + 0.30 * partiality_evidence
            )

            if (
                reason_code
                == "accepted_mapping_with_moderate_alignment"
                and evidence_score > 0.76
            ):
                evidence_score = 0.76

        else:
            raise ValueError(
                f"Unsupported relationship label: {label!r}"
            )

        evidence_score = self._clamp(
            evidence_score
        )

        if evidence_score >= 0.80:
            return "high"

        if evidence_score >= 0.60:
            return "medium"

        return "low"

    def _validate_final_mapping(
        self,
        mapping: dict[str, Any],
    ) -> None:
        """
        Validate the minimum contract expected from FinalCrossMappingService.
        """

        if not mapping.get("a_chunk_id"):
            raise ValueError(
                "Every final mapping requires a_chunk_id."
            )

        if not mapping.get("b_chunk_id"):
            raise ValueError(
                "Every final mapping requires b_chunk_id."
            )

        if (
            "final_mapping_accepted" in mapping
            and not bool(
                mapping.get("final_mapping_accepted")
            )
        ):
            raise ValueError(
                "RelationshipClassificationService received "
                "a mapping that was not finally accepted."
            )

        if not bool(
            mapping.get("nli_evaluated", False)
        ):
            raise ValueError(
                "RelationshipClassificationService requires "
                "nli_evaluated=True for every final mapping."
            )

        self._get_mapping_score(mapping)
        self._get_base_hybrid_score(mapping)

        self._get_required_bounded_score(
            mapping,
            "entailment_score",
        )
        self._get_required_bounded_score(
            mapping,
            "neutral_score",
        )
        self._get_required_bounded_score(
            mapping,
            "contradiction_score",
        )
        self._get_contradiction_margin(mapping)

    def _get_contradiction_margin(
        self,
        mapping: dict[str, Any],
    ) -> float:
        """
        Return the required finite contradiction margin in [-1, 1].
        """

        if "contradiction_margin" not in mapping:
            raise ValueError(
                "RelationshipClassificationService requires "
                "contradiction_margin for every final mapping."
            )

        try:
            value = float(
                mapping["contradiction_margin"]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "contradiction_margin must be numeric."
            ) from exc

        if not math.isfinite(value):
            raise ValueError(
                "contradiction_margin must be finite."
            )

        if not -1.0 <= value <= 1.0:
            raise ValueError(
                "contradiction_margin must be between "
                "-1.0 and 1.0."
            )

        return value

    def _get_mapping_score(
        self,
        mapping: dict[str, Any],
    ) -> float:
        """
        Return required focus-independent mapping_score.

        This method never falls back to focus-adjusted hybrid_score.
        """

        return self._get_required_bounded_score(
            mapping,
            "mapping_score",
        )

    def _get_base_hybrid_score(
        self,
        mapping: dict[str, Any],
    ) -> float:
        """
        Return required unscaled base_hybrid_score.

        This method never falls back to focus-adjusted hybrid_score.
        """

        return self._get_required_bounded_score(
            mapping,
            "base_hybrid_score",
        )

    def _get_required_bounded_score(
        self,
        mapping: dict[str, Any],
        field_name: str,
    ) -> float:
        """
        Return a required finite score in the inclusive range [0, 1].
        """

        if field_name not in mapping:
            raise ValueError(
                "RelationshipClassificationService requires "
                f"{field_name} for every final mapping."
            )

        try:
            value = float(mapping[field_name])
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

    def _preview(
        self,
        text: str,
        *,
        max_chars: int = 220,
    ) -> str:
        """
        Return a shortened cleaned-text preview.
        """

        cleaned_text = " ".join(
            str(text).split()
        )

        if len(cleaned_text) <= max_chars:
            return cleaned_text

        return (
            cleaned_text[
                : max_chars - 3
            ].rstrip()
            + "..."
        )

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

        if not math.isfinite(converted):
            return default

        return converted

    def _clamp(
        self,
        value: float,
        *,
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> float:
        """
        Clamp a numeric value to the requested range.
        """

        return max(
            minimum,
            min(maximum, value),
        )


_relationship_classification_service = (
    RelationshipClassificationService()
)


def get_relationship_classification_service(
) -> RelationshipClassificationService:
    """
    Return the shared relationship-classification service instance.
    """

    return _relationship_classification_service