"""Heuristics to detect paywalls, login walls, and non-article pages in HTML."""

from __future__ import annotations

import re

from app.services.errors import ErrorCode

_PAYWALL_PATTERNS: tuple[tuple[re.Pattern[str], ErrorCode], ...] = (
    (re.compile(r"subscribe to (continue|read|unlock)", re.I), ErrorCode.EXTRACTION_PAYWALL),
    (re.compile(r"subscription required", re.I), ErrorCode.EXTRACTION_PAYWALL),
    (re.compile(r"members? only", re.I), ErrorCode.EXTRACTION_PAYWALL),
    (re.compile(r"premium content", re.I), ErrorCode.EXTRACTION_PAYWALL),
    (re.compile(r"paywall", re.I), ErrorCode.EXTRACTION_PAYWALL),
    (re.compile(r"become a (member|subscriber)", re.I), ErrorCode.EXTRACTION_PAYWALL),
    (re.compile(r"sign in to (continue|read|view)", re.I), ErrorCode.EXTRACTION_LOGIN_REQUIRED),
    (re.compile(r"log in to (continue|read|view)", re.I), ErrorCode.EXTRACTION_LOGIN_REQUIRED),
    (re.compile(r"create an account to (continue|read)", re.I), ErrorCode.EXTRACTION_LOGIN_REQUIRED),
    (re.compile(r"register to (continue|read)", re.I), ErrorCode.EXTRACTION_LOGIN_REQUIRED),
    (re.compile(r"this content is for subscribers", re.I), ErrorCode.EXTRACTION_PAYWALL),
    (re.compile(r"unlock this article", re.I), ErrorCode.EXTRACTION_PAYWALL),
)

_NON_ARTICLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<video\b", re.I),
    re.compile(r"youtube\.com/embed", re.I),
    re.compile(r"search results for", re.I),
)

_JS_SHELL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"enable javascript", re.I),
    re.compile(r"javascript is (required|disabled|not available)", re.I),
    re.compile(r"__NEXT_DATA__", re.I),
    re.compile(r"window\.__INITIAL_STATE__", re.I),
)


def detect_html_issue(html: str, *, body_text: str = "") -> ErrorCode | None:
    """Return a specific extraction error code when HTML signals a known failure mode."""
    sample = html[:120_000]
    lowered = sample.lower()

    for pattern, code in _PAYWALL_PATTERNS:
        if pattern.search(sample):
            return code

    visible_text_len = len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sample)).strip())
    if not body_text.strip() and visible_text_len < 400:
        for pattern in _JS_SHELL_PATTERNS:
            if pattern.search(sample):
                return ErrorCode.EXTRACTION_JS_RENDERED

    if not body_text.strip():
        if any(p.search(sample) for p in _NON_ARTICLE_PATTERNS):
            return ErrorCode.EXTRACTION_NOT_NEWS_PAGE

        # Short teaser with strong paywall vocabulary in surrounding HTML.
        if visible_text_len > 200 and any(
            token in lowered
            for token in ("subscriber", "subscription", "sign in", "register to read", "member")
        ):
            return ErrorCode.EXTRACTION_PAYWALL

    return None
