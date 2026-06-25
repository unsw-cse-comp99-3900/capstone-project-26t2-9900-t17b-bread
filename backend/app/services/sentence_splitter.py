"""Deterministic, dependency-free sentence segmentation.

Sprint 1 keeps sentence segmentation self-contained so the backend runs
without downloading NLP models. The splitter protects common abbreviations
and decimal numbers from being treated as sentence boundaries. It is
deterministic, which guarantees reproducible output for identical input
(PROJ-4 AC 4.3).

This module exposes a single ``split_sentences`` function so it can later be
swapped for a model-based segmenter (e.g. spaCy) without touching callers.
"""

from __future__ import annotations

import re

# Abbreviations whose trailing period must NOT end a sentence.
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "inc",
    "ltd", "co", "corp", "govt", "dept", "fig", "no", "vol", "approx",
    "u.s", "u.k", "e.g", "i.e", "a.m", "p.m", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}

# A boundary is a sentence-ending punctuation mark followed by whitespace and
# an uppercase letter, opening quote, or digit (start of the next sentence).
_BOUNDARY_RE = re.compile(r'(?<=[.!?])["\')\]]?\s+(?=["\'(\[]?[A-Z0-9])')


def _ends_with_abbreviation(text: str) -> bool:
    """Return True if ``text`` ends with a known abbreviation or an initial."""
    match = re.search(r'(\b[\w.]+)\.\s*$', text)
    if not match:
        return False
    token = match.group(1).lower().rstrip(".")
    if token in _ABBREVIATIONS:
        return True
    # Single-letter initials such as "J." in "J. Smith".
    return len(token) == 1 and token.isalpha()


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into a list of trimmed, non-empty sentences."""
    if not text or not text.strip():
        return []

    sentences: list[str] = []
    start = 0
    for match in _BOUNDARY_RE.finditer(text):
        candidate = text[start:match.start() + 1]
        if _ends_with_abbreviation(candidate):
            # False boundary (abbreviation/initial); keep scanning.
            continue
        cleaned = candidate.strip()
        if cleaned:
            sentences.append(cleaned)
        start = match.end()

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences
