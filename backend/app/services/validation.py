"""URL validation shared by the Fetch and Compare controllers (PROJ-1)."""

from __future__ import annotations

from urllib.parse import urlparse

from app.services.errors import ErrorCode, PipelineError, PipelineStage


def normalize_and_validate_url(
    raw_url: str | None,
    *,
    article_ref: str | None = None,
) -> str:
    """Validate that ``raw_url`` is a well-formed HTTP/HTTPS URL."""
    if raw_url is None or not raw_url.strip():
        raise PipelineError(
            PipelineStage.VALIDATION,
            ErrorCode.URL_MISSING,
            article_ref=article_ref,
            url=raw_url,
        )

    url = raw_url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise PipelineError(
            PipelineStage.VALIDATION,
            ErrorCode.URL_INVALID_SCHEME,
            article_ref=article_ref,
            url=url,
        )
    if not parsed.netloc:
        raise PipelineError(
            PipelineStage.VALIDATION,
            ErrorCode.URL_MISSING_HOST,
            article_ref=article_ref,
            url=url,
        )
    return url


def domain_of(url: str) -> str | None:
    """Return the host portion of a URL (used as the article source domain)."""
    host = urlparse(url).netloc
    return host or None
