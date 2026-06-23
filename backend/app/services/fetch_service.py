"""Article Fetch Service (PROJ-2).

Retrieves the raw HTML for a user-provided URL and extracts the main article
content (title, source domain, body text) while stripping webpage noise such
as navigation menus, ads, recommendation blocks and footers. Content
extraction is delegated to ``trafilatura``, which is purpose-built for news
boilerplate removal.
"""

from __future__ import annotations

import httpx
import trafilatura

from app.config import Settings, get_settings
from app.schemas.article import RawArticle
from app.services.errors import PipelineError, PipelineStage
from app.services.validation import domain_of, normalize_and_validate_url


async def fetch_html(url: str, settings: Settings, *, article_ref: str | None = None) -> str:
    """Download raw HTML for ``url``.

    Raises ``PipelineError`` at the FETCH stage on network/HTTP errors so the
    caller can report exactly which article could not be retrieved
    (PROJ-2 AC 2.5).
    """
    headers = {"User-Agent": settings.fetch_user_agent}
    try:
        async with httpx.AsyncClient(
            timeout=settings.fetch_timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PipelineError(
            PipelineStage.FETCH,
            f"Server returned HTTP {exc.response.status_code} for the article.",
            article_ref=article_ref,
            url=url,
        ) from exc
    except httpx.RequestError as exc:
        raise PipelineError(
            PipelineStage.FETCH,
            f"Could not reach the article URL ({exc.__class__.__name__}).",
            article_ref=article_ref,
            url=url,
        ) from exc

    if len(response.content) > settings.fetch_max_bytes:
        raise PipelineError(
            PipelineStage.FETCH,
            "Article response is too large to process.",
            article_ref=article_ref,
            url=url,
        )
    return response.text


def extract_main_content(
    html: str,
    url: str,
    *,
    article_ref: str | None = None,
) -> RawArticle:
    """Extract title, source domain and cleaned body text from raw HTML.

    Raises ``PipelineError`` at the EXTRACTION stage when no usable article
    body can be recovered from the page (PROJ-2 AC 2.5).
    """
    # ``extract`` and ``extract_metadata`` are the most stable entry points
    # across trafilatura 1.x/2.x (``bare_extraction``'s return type changed
    # between versions), so we use them directly.
    body_text = (
        trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        or ""
    ).strip()

    title = None
    try:
        metadata = trafilatura.extract_metadata(html, default_url=url)
        if metadata is not None:
            title = getattr(metadata, "title", None)
    except Exception:  # pragma: no cover - metadata is best-effort only
        title = None

    if not body_text:
        raise PipelineError(
            PipelineStage.EXTRACTION,
            "Could not extract readable article text from the page.",
            article_ref=article_ref,
            url=url,
        )

    return RawArticle(
        url=url,
        title=title or None,
        source_domain=domain_of(url),
        body_text=body_text,
    )


async def fetch_article(
    raw_url: str | None,
    *,
    article_ref: str | None = None,
    settings: Settings | None = None,
) -> RawArticle:
    """End-to-end fetch: validate URL -> download HTML -> extract main content."""
    settings = settings or get_settings()
    url = normalize_and_validate_url(raw_url, article_ref=article_ref)
    html = await fetch_html(url, settings, article_ref=article_ref)
    return extract_main_content(html, url, article_ref=article_ref)
