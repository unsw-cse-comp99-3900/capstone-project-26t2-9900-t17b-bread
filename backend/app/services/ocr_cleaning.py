"""Clean raw OCR output into key article text.

OCR of scanned pages is noisy: it captures page numbers, running headers and
footers, watermarks, stray symbols from lines/tables, and broken hyphenation.
This module strips that noise and keeps the meaningful body text so downstream
preprocessing (sentence splitting, embedding, comparison) receives clean input.
"""

from __future__ import annotations

import re
from collections import Counter

# A line that is only a page number: "12", "- 12 -", "Page 12", "12 / 30".
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page\s*)?[-–—]?\s*\d+\s*(?:[-–—/]\s*\d+)?\s*$",
    re.IGNORECASE,
)
_MULTISPACE_RE = re.compile(r"[ \t\u00a0]+")
_HYPHEN_BREAK_RE = re.compile(r"(\w)[-\u2010]\n(\w)")


def _alpha_ratio(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    letters = sum(1 for ch in stripped if ch.isalpha())
    return letters / len(stripped)


def _is_noise_line(line: str) -> bool:
    """Heuristic: True when a single line looks like OCR noise, not body text."""
    stripped = line.strip()
    if not stripped:
        return False  # blank lines are paragraph separators, handled elsewhere

    if _PAGE_NUMBER_RE.match(stripped):
        return True

    # Very short fragments with little alphabetic content (e.g. "|", "~ *", "•").
    if len(stripped) <= 3 and _alpha_ratio(stripped) < 0.5:
        return True

    # Lines dominated by symbols/digits are usually rules, tables, or artifacts.
    if len(stripped) >= 4 and _alpha_ratio(stripped) < 0.35:
        return True

    return False


def _find_repeated_lines(pages: list[str], *, min_ratio: float = 0.5) -> set[str]:
    """Find header/footer lines that repeat across many pages."""
    if len(pages) < 3:
        return set()

    counter: Counter[str] = Counter()
    for page in pages:
        seen_on_page = {
            ln.strip()
            for ln in page.splitlines()
            if ln.strip() and len(ln.strip()) <= 80
        }
        counter.update(seen_on_page)

    threshold = max(2, int(len(pages) * min_ratio))
    return {line for line, count in counter.items() if count >= threshold}


def clean_ocr_pages(pages: list[str]) -> str:
    """Turn a list of raw per-page OCR strings into cleaned body text."""
    repeated = _find_repeated_lines(pages)
    cleaned_pages: list[str] = []

    for page in pages:
        # Rejoin words split by end-of-line hyphenation before line analysis.
        page = _HYPHEN_BREAK_RE.sub(r"\1\2", page)

        kept: list[str] = []
        for raw_line in page.splitlines():
            line = _MULTISPACE_RE.sub(" ", raw_line).strip()
            if not line:
                kept.append("")
                continue
            if line in repeated:
                continue
            if _is_noise_line(line):
                continue
            kept.append(line)

        page_text = "\n".join(kept)
        if page_text.strip():
            cleaned_pages.append(page_text.strip())

    combined = "\n\n".join(cleaned_pages)
    return _reflow_paragraphs(combined)


def _reflow_paragraphs(text: str) -> str:
    """Merge wrapped lines into paragraphs; blank lines separate paragraphs."""
    blocks = re.split(r"\n\s*\n", text)
    paragraphs: list[str] = []

    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        merged: list[str] = []
        buffer = ""
        for line in lines:
            if not buffer:
                buffer = line
                continue
            # Continue the previous line unless it clearly ended a sentence.
            if buffer.endswith((".", "!", "?", ":", ";", '"', "”")):
                merged.append(buffer)
                buffer = line
            else:
                buffer = f"{buffer} {line}"
        if buffer:
            merged.append(buffer)

        paragraph = " ".join(merged) if len(merged) == 1 else "\n".join(merged)
        paragraphs.append(paragraph.strip())

    return "\n\n".join(p for p in paragraphs if p).strip()
