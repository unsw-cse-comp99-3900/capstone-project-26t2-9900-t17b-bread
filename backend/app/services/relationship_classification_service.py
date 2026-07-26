# backend/app/services/relationship_classification_service.py

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Relatedness thresholds
# ---------------------------------------------------------------------------

# Keep these thresholds consistent with CrossMappingService.
# A pair that has already passed cross mapping should not be rejected again
# merely because contradictory wording lowers cosine similarity.
MIN_RELATED_MAPPING_SCORE = 0.42
MIN_RELATED_BASE_HYBRID_SCORE = 0.38
MIN_RELATED_COSINE_SCORE = 0.30
MIN_RELATED_BM25_SCORE = 0.12


# ---------------------------------------------------------------------------
# Divergence thresholds
# ---------------------------------------------------------------------------

# Divergent pairs may have lower cosine similarity because their predicates
# express opposing meanings, while still sharing the same subject and event.
MIN_DIVERGENT_MAPPING_SCORE = 0.42
MIN_DIVERGENT_COSINE_SCORE = 0.30

# Contradiction must be the dominant bidirectional NLI result.
MIN_CONTRADICTION_SCORE = 0.52
MIN_CONTRADICTION_MARGIN = 0.03

# Very strong contradiction can pass with only a small positive margin.
VERY_STRONG_CONTRADICTION_SCORE = 0.68

# Explicit factual conflicts such as:
#
#   "12 people were killed"
#   versus
#   "no one was killed"
#
# can pass with a lower general NLI threshold because a deterministic textual
# conflict has already been detected.
MIN_EXPLICIT_CONFLICT_SCORE = 0.55
MIN_EXPLICIT_CONFLICT_MARGIN = 0.05


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

# Very high similarity may still support alignment when one paragraph contains
# additional detail and NLI returns neutral.
VERY_STRONG_MAPPING_SCORE = 0.76
VERY_STRONG_COSINE_SCORE = 0.68


class RelationshipClassificationService:
    """
    Classify final cross-article paragraph-chunk mappings.

    This service runs after:

        1. cosine similarity
        2. BM25 scoring
        3. hybrid scoring
        4. cross mapping
        5. contradiction/NLI analysis

    Public labels:

        - aligned
        - partially_aligned
        - divergent

    Internally unrelated mappings are discarded from the final output.

    Classification uses semantic/lexical relatedness together with
    bidirectional NLI. Numeric differences and scope heuristics are ignored.
    """

    def classify_mappings(
        self,
        cross_mappings: list[dict[str, Any]],
        *,
        chunks_a: list[dict[str, Any]] | None = None,
        chunks_b: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Classify every cross mapping and return visible relationships only.
        """

        if not cross_mappings:
            return []

        text_lookup = self._build_text_lookup(
            chunks_a or [],
            chunks_b or [],
        )

        relationships: list[dict[str, Any]] = []

        for mapping in cross_mappings:
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

            relationship = {
                "pair_number": None,

                "a_chunk_id": a_chunk_id,
                "b_chunk_id": b_chunk_id,

                "a_chunk_index": mapping.get("a_chunk_index"),
                "b_chunk_index": mapping.get("b_chunk_index"),

                "a_paragraph_index": mapping.get(
                    "a_paragraph_index"
                ),
                "b_paragraph_index": mapping.get(
                    "b_paragraph_index"
                ),

                "a_article_ref": mapping.get("a_article_ref"),
                "b_article_ref": mapping.get("b_article_ref"),

                "label": label,
                "confidence": confidence,
                "reason_code": reason_code,

                # Similarity and mapping evidence.
                "cosine_score": self._safe_float(
                    mapping.get("cosine_score")
                ),
                "bm25_score": self._safe_float(
                    mapping.get("bm25_score")
                ),
                "base_hybrid_score": self._get_base_hybrid_score(
                    mapping
                ),
                "hybrid_score": self._safe_float(
                    mapping.get("hybrid_score")
                ),
                "mapping_score": self._get_mapping_score(
                    mapping
                ),
                "context_support": self._safe_float(
                    mapping.get("context_support")
                ),

                "focus": mapping.get("focus", "general"),
                "pair_focus_relevance": self._safe_float(
                    mapping.get("pair_focus_relevance")
                ),

                # Combined NLI evidence.
                "nli_evaluated": bool(
                    mapping.get("nli_evaluated", False)
                ),
                "nli_label": mapping.get(
                    "nli_label",
                    "not_evaluated",
                ),
                "entailment_score": self._safe_float(
                    mapping.get("entailment_score")
                ),
                "neutral_score": self._safe_float(
                    mapping.get("neutral_score")
                ),
                "contradiction_score": self._safe_float(
                    mapping.get("contradiction_score")
                ),
                "contradiction_margin": self._get_contradiction_margin(
                    mapping
                ),
                "contradiction_is_dominant": bool(
                    mapping.get(
                        "contradiction_is_dominant",
                        False,
                    )
                ),

                # Directional NLI evidence.
                "forward_entailment_score": self._safe_float(
                    mapping.get("forward_entailment_score")
                ),
                "forward_neutral_score": self._safe_float(
                    mapping.get("forward_neutral_score")
                ),
                "forward_contradiction_score": self._safe_float(
                    mapping.get("forward_contradiction_score")
                ),
                "reverse_entailment_score": self._safe_float(
                    mapping.get("reverse_entailment_score")
                ),
                "reverse_neutral_score": self._safe_float(
                    mapping.get("reverse_neutral_score")
                ),
                "reverse_contradiction_score": self._safe_float(
                    mapping.get("reverse_contradiction_score")
                ),

                # Scope and numeric evidence generated by the contradiction
                # detection service.
                "scope_mismatch": bool(
                    mapping.get("scope_mismatch", False)
                ),
                "has_numeric_difference": bool(
                    mapping.get(
                        "has_numeric_difference",
                        False,
                    )
                ),
                "casualty_numeric_difference": bool(
                    mapping.get(
                        "casualty_numeric_difference",
                        False,
                    )
                ),
                "explicit_casualty_conflict": bool(
                    mapping.get(
                        "explicit_casualty_conflict",
                        False,
                    )
                ),

                "a_numbers": list(
                    mapping.get("a_numbers") or []
                ),
                "b_numbers": list(
                    mapping.get("b_numbers") or []
                ),

                "a_zero_casualty_claim": bool(
                    mapping.get(
                        "a_zero_casualty_claim",
                        False,
                    )
                ),
                "b_zero_casualty_claim": bool(
                    mapping.get(
                        "b_zero_casualty_claim",
                        False,
                    )
                ),
                "a_positive_casualty_claim": bool(
                    mapping.get(
                        "a_positive_casualty_claim",
                        False,
                    )
                ),
                "b_positive_casualty_claim": bool(
                    mapping.get(
                        "b_positive_casualty_claim",
                        False,
                    )
                ),

                "a_text_preview": self._preview(
                    text_lookup.get(str(a_chunk_id), "")
                ),
                "b_text_preview": self._preview(
                    text_lookup.get(str(b_chunk_id), "")
                ),
            }

            relationships.append(relationship)

        visible_relationships = [
            relationship
            for relationship in relationships
            if relationship["label"] in {
                "aligned",
                "partially_aligned",
                "divergent",
            }
        ]

        for pair_number, relationship in enumerate(
            visible_relationships,
            start=1,
        ):
            relationship["pair_number"] = pair_number

        return visible_relationships

    def _classify_single_mapping(
        self,
        mapping: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Return the relationship label and reason code.

        Decision order:

            1. unrelated when shared content is insufficient;
            2. divergent when bidirectional NLI shows a dominant contradiction;
            3. aligned when similarity is strong and contradiction does not block;
            4. partially_aligned for the remaining related mappings.

        Numeric differences and scope heuristics do not affect classification.
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

        nli_evaluated = bool(
            mapping.get("nli_evaluated", False)
        )
        entailment_score = self._safe_float(
            mapping.get("entailment_score")
        )
        neutral_score = self._safe_float(
            mapping.get("neutral_score")
        )
        contradiction_score = self._safe_float(
            mapping.get("contradiction_score")
        )
        contradiction_margin = self._get_contradiction_margin(
            mapping
        )
        contradiction_is_dominant = bool(
            mapping.get(
                "contradiction_is_dominant",
                contradiction_score
                > max(entailment_score, neutral_score),
            )
        )

        if not self._is_related_pair(
            cosine_score=cosine_score,
            bm25_score=bm25_score,
            base_hybrid_score=base_hybrid_score,
            mapping_score=mapping_score,
        ):
            return (
                "unrelated",
                "insufficient_shared_content",
            )

        if self._has_strong_contradiction(
            nli_evaluated=nli_evaluated,
            contradiction_score=contradiction_score,
            contradiction_margin=contradiction_margin,
            contradiction_is_dominant=contradiction_is_dominant,
            mapping_score=mapping_score,
            cosine_score=cosine_score,
        ):
            return (
                "divergent",
                "same_claim_with_bidirectional_nli_contradiction",
            )

        alignment_reason = self._get_alignment_reason(
            nli_evaluated=nli_evaluated,
            entailment_score=entailment_score,
            neutral_score=neutral_score,
            contradiction_score=contradiction_score,
            contradiction_margin=contradiction_margin,
            contradiction_is_dominant=contradiction_is_dominant,
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

        if (
            nli_evaluated
            and neutral_score
            >= max(entailment_score, contradiction_score)
        ):
            return (
                "partially_aligned",
                "related_content_with_nli_neutrality",
            )

        if (
            nli_evaluated
            and entailment_score > contradiction_score
        ):
            return (
                "partially_aligned",
                "partial_support_with_additional_information",
            )

        if (
            cosine_score >= 0.56
            and bm25_score < MIN_ALIGNED_BM25_SCORE
        ):
            return (
                "partially_aligned",
                "semantic_match_with_lexical_difference",
            )

        return (
            "partially_aligned",
            "moderate_related_content",
        )
    def _has_strong_contradiction(
        self,
        *,
        nli_evaluated: bool,
        contradiction_score: float,
        contradiction_margin: float,
        contradiction_is_dominant: bool,
        mapping_score: float,
        cosine_score: float,
    ) -> bool:
        """
        Return True when bidirectional NLI provides strong contradiction evidence.

        No numeric, casualty, or scope heuristics are used.
        """

        if not nli_evaluated:
            return False

        if mapping_score < MIN_DIVERGENT_MAPPING_SCORE:
            return False

        if cosine_score < MIN_DIVERGENT_COSINE_SCORE:
            return False

        if not contradiction_is_dominant:
            return False

        if (
            contradiction_score
            >= VERY_STRONG_CONTRADICTION_SCORE
        ):
            return contradiction_margin >= 0.02

        return (
            contradiction_score >= MIN_CONTRADICTION_SCORE
            and contradiction_margin
            >= MIN_CONTRADICTION_MARGIN
        )
    def _get_alignment_reason(
        self,
        *,
        nli_evaluated: bool,
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
        Return an alignment reason when similarity is sufficiently strong and
        bidirectional NLI does not show a meaningful contradiction.

        Numeric differences and scope heuristics are ignored.
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
            nli_evaluated
            and contradiction_is_dominant
            and contradiction_score >= 0.50
            and contradiction_margin >= 0.03
        )

        if contradiction_blocks_alignment:
            return None

        if not nli_evaluated:
            if very_strong_similarity:
                return "very_strong_similarity_without_nli"

            return "strong_similarity_without_nli_contradiction"

        if contradiction_score > MAX_ALIGNED_CONTRADICTION_SCORE:
            return None

        if (
            entailment_score >= MIN_ALIGNED_ENTAILMENT_SCORE
            and entailment_score > contradiction_score
        ):
            return "strong_similarity_with_nli_entailment"

        if (
            neutral_score >= entailment_score
            and contradiction_score < 0.35
            and (
                very_strong_similarity
                or strong_semantic_alignment
                or balanced_alignment
            )
        ):
            return "strong_shared_content_with_additional_detail"

        if (
            entailment_score >= 0.35
            and entailment_score > contradiction_score
            and (
                strong_semantic_alignment
                or balanced_alignment
            )
        ):
            return "strong_similarity_with_partial_nli_support"

        if (
            contradiction_score < 0.30
            and (
                very_strong_similarity
                or strong_semantic_alignment
            )
        ):
            return "strong_similarity_without_meaningful_contradiction"

        return None
    def _is_related_pair(
        self,
        *,
        cosine_score: float,
        bm25_score: float,
        base_hybrid_score: float,
        mapping_score: float,
    ) -> bool:
        """
        Determine whether two chunks discuss sufficiently related content.
        """

        strong_semantic_relation = (
            mapping_score >= MIN_RELATED_MAPPING_SCORE
            and cosine_score >= MIN_RELATED_COSINE_SCORE
        )

        if strong_semantic_relation:
            return True

        balanced_hybrid_relation = (
            mapping_score >= MIN_RELATED_MAPPING_SCORE
            and base_hybrid_score
            >= MIN_RELATED_BASE_HYBRID_SCORE
            and (
                cosine_score >= MIN_RELATED_COSINE_SCORE
                or bm25_score >= MIN_RELATED_BM25_SCORE
            )
        )

        if balanced_hybrid_relation:
            return True

        lexical_relation = (
            bm25_score >= 0.38
            and cosine_score >= 0.38
            and mapping_score >= 0.48
        )

        if lexical_relation:
            return True

        return False

    def _estimate_confidence(
        self,
        mapping: dict[str, Any],
        *,
        label: str,
        reason_code: str,
    ) -> str:
        """
        Estimate categorical confidence for the assigned relationship.

        This is an evidence-strength estimate, not a calibrated probability.
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

        context_support = self._safe_float(
            mapping.get("context_support")
        )

        entailment_score = self._safe_float(
            mapping.get("entailment_score")
        )

        neutral_score = self._safe_float(
            mapping.get("neutral_score")
        )

        contradiction_score = self._safe_float(
            mapping.get("contradiction_score")
        )

        contradiction_margin = max(
            0.0,
            self._get_contradiction_margin(mapping),
        )

        nli_evaluated = bool(
            mapping.get("nli_evaluated", False)
        )

        scope_mismatch = bool(
            mapping.get("scope_mismatch", False)
        )

        explicit_casualty_conflict = bool(
            mapping.get(
                "explicit_casualty_conflict",
                False,
            )
        )

        has_numeric_difference = bool(
            mapping.get(
                "has_numeric_difference",
                False,
            )
        )

        casualty_numeric_difference = bool(
            mapping.get(
                "casualty_numeric_difference",
                False,
            )
        )

        if label == "divergent":
            if not nli_evaluated:
                return "low"

            evidence_score = (
                0.50 * contradiction_score
                + 0.20 * mapping_score
                + 0.15 * cosine_score
                + 0.15 * min(
                    1.0,
                    contradiction_margin * 2.5,
                )
            )

            if explicit_casualty_conflict:
                evidence_score += 0.08

            if scope_mismatch:
                evidence_score -= 0.20

        elif label == "aligned":
            similarity_evidence = (
                0.35 * mapping_score
                + 0.30 * cosine_score
                + 0.20 * base_hybrid_score
                + 0.15 * bm25_score
            )

            if nli_evaluated:
                nli_alignment_support = max(
                    entailment_score,
                    1.0 - contradiction_score,
                )

                evidence_score = (
                    0.75 * similarity_evidence
                    + 0.25 * nli_alignment_support
                )
            else:
                evidence_score = similarity_evidence

            if scope_mismatch:
                evidence_score -= 0.15

            if (
                casualty_numeric_difference
                and contradiction_score >= 0.55
            ):
                evidence_score -= 0.10

        elif label == "partially_aligned":
            relation_evidence = (
                0.40 * mapping_score
                + 0.30 * cosine_score
                + 0.15 * base_hybrid_score
                + 0.15 * bm25_score
            )

            if nli_evaluated:
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
            else:
                evidence_score = relation_evidence

            if reason_code in {
                "numeric_difference_with_scope_mismatch",
                "related_reports_with_different_scope",
            }:
                evidence_score = max(
                    evidence_score,
                    0.62,
                )

            if reason_code == "related_reports_with_numeric_update":
                evidence_score = min(
                    max(evidence_score, 0.58),
                    0.76,
                )

            if (
                reason_code == "moderate_related_content"
                and evidence_score > 0.76
            ):
                evidence_score = 0.76

        else:
            relatedness_score = (
                0.40 * mapping_score
                + 0.30 * cosine_score
                + 0.15 * bm25_score
                + 0.10 * base_hybrid_score
                + 0.05 * context_support
            )

            evidence_score = 1.0 - relatedness_score

        evidence_score = self._clamp(
            evidence_score
        )

        if evidence_score >= 0.80:
            return "high"

        if evidence_score >= 0.60:
            return "medium"

        return "low"

    def _get_contradiction_margin(
        self,
        mapping: dict[str, Any],
    ) -> float:
        """
        Return the stored contradiction margin when available.

        For backward compatibility, calculate it from the NLI scores when the
        contradiction detection service did not provide the field.
        """

        if "contradiction_margin" in mapping:
            return self._safe_float(
                mapping.get("contradiction_margin")
            )

        contradiction_score = self._safe_float(
            mapping.get("contradiction_score")
        )

        entailment_score = self._safe_float(
            mapping.get("entailment_score")
        )

        neutral_score = self._safe_float(
            mapping.get("neutral_score")
        )

        return (
            contradiction_score
            - max(
                entailment_score,
                neutral_score,
            )
        )

    def _get_mapping_score(
        self,
        mapping: dict[str, Any],
    ) -> float:
        """
        Return mapping_score, falling back to hybrid_score only when absent.

        A valid value of 0.0 is preserved.
        """

        if "mapping_score" in mapping:
            return self._safe_float(
                mapping.get("mapping_score")
            )

        return self._safe_float(
            mapping.get("hybrid_score")
        )

    def _get_base_hybrid_score(
        self,
        mapping: dict[str, Any],
    ) -> float:
        """
        Return base_hybrid_score, falling back to hybrid_score only when absent.
        """

        if "base_hybrid_score" in mapping:
            return self._safe_float(
                mapping.get("base_hybrid_score")
            )

        return self._safe_float(
            mapping.get("hybrid_score")
        )

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
            cleaned_text[: max_chars - 3].rstrip()
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
    Return the shared relationship-classification service.
    """

    return _relationship_classification_service