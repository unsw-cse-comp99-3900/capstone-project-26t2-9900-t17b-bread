# backend/app/services/candidate_pair_service.py

from __future__ import annotations

from typing import Any


class CandidatePairService:
    """
    Build candidate paragraph chunk pairs between two articles.

    This service only defines the candidate search space.
    It does not compute similarity scores and does not decide final alignment.
    """

    def extract_valid_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Keep chunks with valid chunk_id and non-empty text."""
        valid_chunks: list[dict[str, Any]] = []

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            text = str(chunk.get("text", "")).strip()

            if not chunk_id or not text:
                continue

            cleaned_chunk = dict(chunk)
            cleaned_chunk["text"] = " ".join(text.split())
            valid_chunks.append(cleaned_chunk)

        return valid_chunks

    def build_candidate_pairs_from_valid_chunks(
        self,
        valid_a: list[dict[str, Any]],
        valid_b: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Build all possible A-B pairs from already validated chunk lists.

        The a_position and b_position fields match the order of valid_a and valid_b.
        This is important for reading scores from a score matrix.
        """

        candidate_pairs: list[dict[str, Any]] = []

        for i, chunk_a in enumerate(valid_a):
            for j, chunk_b in enumerate(valid_b):
                candidate_pairs.append(
                    {
                        "a_position": i,
                        "b_position": j,
                        "a_chunk_id": chunk_a.get("chunk_id"),
                        "b_chunk_id": chunk_b.get("chunk_id"),
                        "a_chunk_index": chunk_a.get("chunk_index"),
                        "b_chunk_index": chunk_b.get("chunk_index"),
                        "a_paragraph_index": chunk_a.get("paragraph_index"),
                        "b_paragraph_index": chunk_b.get("paragraph_index"),
                        "a_article_ref": chunk_a.get("article_ref"),
                        "b_article_ref": chunk_b.get("article_ref"),
                        "a_text": chunk_a.get("text", ""),
                        "b_text": chunk_b.get("text", ""),
                    }
                )

        return candidate_pairs

    def build_candidate_pairs(
        self,
        chunks_a: list[dict[str, Any]],
        chunks_b: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Validate chunks and build all possible A-B candidate pairs.
        """

        valid_a = self.extract_valid_chunks(chunks_a)
        valid_b = self.extract_valid_chunks(chunks_b)

        if not valid_a or not valid_b:
            return []

        return self.build_candidate_pairs_from_valid_chunks(valid_a, valid_b)


_candidate_pair_service = CandidatePairService()


def get_candidate_pair_service() -> CandidatePairService:
    return _candidate_pair_service