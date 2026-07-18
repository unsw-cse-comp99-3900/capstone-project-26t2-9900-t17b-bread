# backend/app/services/relationship_classification_service.py

from __future__ import annotations

from typing import Any


class RelationshipClassificationService:
    """
    Classify the relationship between mapped paragraph chunks.

    This service works after cross mapping.
    It does not compute similarity scores and does not decide alignment.
    """

    def classify_mappings(
        self,
        cross_mappings: list[dict[str, Any]],
        *,
        chunks_a: list[dict[str, Any]] | None = None,
        chunks_b: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Classify each final cross mapping into a relationship label.

        Labels:
            aligned:
                The two chunks discuss highly similar content with strong
                semantic and lexical support.

            partially_aligned:
                The two chunks discuss related content, but may differ in
                emphasis, details, framing, or wording.

            divergent:
                The two chunks are weakly related or show clear difference.
        """

        if not cross_mappings:
            return []

        text_lookup = self._build_text_lookup(chunks_a or [], chunks_b or [])

        relationships: list[dict[str, Any]] = []

        for mapping in cross_mappings:
            label, reason_code = self._classify_single_mapping(mapping)
            confidence = self._estimate_confidence(mapping)

            a_chunk_id = mapping.get("a_chunk_id")
            b_chunk_id = mapping.get("b_chunk_id")

            relationships.append(
                {
                    "pair_number": None,
                    "a_chunk_id": a_chunk_id,
                    "b_chunk_id": b_chunk_id,
                    "a_chunk_index": mapping.get("a_chunk_index"),
                    "b_chunk_index": mapping.get("b_chunk_index"),
                    "a_paragraph_index": mapping.get("a_paragraph_index"),
                    "b_paragraph_index": mapping.get("b_paragraph_index"),
                    "a_article_ref": mapping.get("a_article_ref"),
                    "b_article_ref": mapping.get("b_article_ref"),

                    "label": label,
                    "confidence": confidence,
                    "reason_code": reason_code,

                    "cosine_score": self._safe_float(mapping.get("cosine_score")),
                    "bm25_score": self._safe_float(mapping.get("bm25_score")),
                    "base_hybrid_score": self._safe_float(
                        mapping.get("base_hybrid_score")
                    ),
                    "hybrid_score": self._safe_float(mapping.get("hybrid_score")),
                    "mapping_score": self._safe_float(mapping.get("mapping_score")),
                    "context_support": self._safe_float(
                        mapping.get("context_support")
                    ),

                    "focus": mapping.get("focus", "general"),
                    "pair_focus_relevance": self._safe_float(
                        mapping.get("pair_focus_relevance")
                    ),

                    "a_text_preview": self._preview(text_lookup.get(a_chunk_id, "")),
                    "b_text_preview": self._preview(text_lookup.get(b_chunk_id, "")),
                }
            )

        #Number only highlighted relationships
        pair_number = 1
        for rel in relationships:
            if rel["label"] in ("aligned", "partially_aligned", "divergent"):
                rel["pair_number"] = pair_number
                pair_number += 1

        return relationships

    def _classify_single_mapping(
        self,
        mapping: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Return:
            (relationship_label, reason_code)
        """

        cosine_score = self._safe_float(mapping.get("cosine_score"))
        bm25_score = self._safe_float(mapping.get("bm25_score"))

        # base_hybrid_score is preferred because it is not affected by focus scaling.
        base_hybrid_score = self._safe_float(
            mapping.get("base_hybrid_score"),
            default=self._safe_float(mapping.get("hybrid_score")),
        )

        mapping_score = self._safe_float(
            mapping.get("mapping_score"),
            default=self._safe_float(mapping.get("hybrid_score")),
        )

        score_gap = abs(cosine_score - bm25_score)

        # Strong semantic match + reasonable lexical match.
        # This means the two chunks likely discuss the same event or idea
        # with comparable details.
        if (
            mapping_score >= 0.78
            and base_hybrid_score >= 0.72
            and cosine_score >= 0.72
            and bm25_score >= 0.35
            and score_gap <= 0.50
        ):
            return "aligned", "strong_semantic_and_lexical_match"

        # Strong semantic similarity but weaker lexical overlap.
        # This often means same topic/event but different wording, emphasis,
        # or level of detail.
        if cosine_score >= 0.68 and bm25_score < 0.35:
            return "partially_aligned", "semantic_match_with_lexical_difference"

        # Good lexical overlap but weaker semantic similarity.
        # This may happen when the two chunks share names, places, or keywords,
        # but frame the issue differently.
        if bm25_score >= 0.45 and cosine_score < 0.68:
            return "partially_aligned", "lexical_overlap_with_semantic_difference"

        # Moderate hybrid/mapping score.
        # The pair is related enough to be mapped, but not strong enough
        # to be treated as fully aligned.
        if mapping_score >= 0.58 or base_hybrid_score >= 0.58:
            return "partially_aligned", "moderate_hybrid_match"

        return "divergent", "weak_or_uncertain_match"

    def _estimate_confidence(
        self,
        mapping: dict[str, Any],
    ) -> str:
        """
        Estimate classification confidence from mapping evidence.
        """

        mapping_score = self._safe_float(mapping.get("mapping_score"))
        cosine_score = self._safe_float(mapping.get("cosine_score"))
        bm25_score = self._safe_float(mapping.get("bm25_score"))
        context_support = self._safe_float(mapping.get("context_support"))

        evidence_score = (
            0.45 * mapping_score
            + 0.30 * cosine_score
            + 0.15 * bm25_score
            + 0.10 * context_support
        )

        if evidence_score >= 0.78:
            return "high"

        if evidence_score >= 0.60:
            return "medium"

        return "low"

    def _build_text_lookup(
        self,
        chunks_a: list[dict[str, Any]],
        chunks_b: list[dict[str, Any]],
    ) -> dict[str, str]:
        """
        Build chunk_id -> chunk text lookup.
        """
        lookup: dict[str, str] = {}

        for chunk in chunks_a + chunks_b:
            chunk_id = chunk.get("chunk_id")
            text = str(chunk.get("text", "")).strip()

            if chunk_id and text:
                lookup[chunk_id] = " ".join(text.split())

        return lookup

    def _preview(
        self,
        text: str,
        *,
        max_chars: int = 220,
    ) -> str:
        """
        Return a short text preview for frontend/debug output.
        """
        text = " ".join(str(text).split())

        if len(text) <= max_chars:
            return text

        return text[: max_chars - 3].rstrip() + "..."

    def _safe_float(
        self,
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


_relationship_classification_service = RelationshipClassificationService()


def get_relationship_classification_service() -> RelationshipClassificationService:
    return _relationship_classification_service