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
from app.services.errors import ErrorCode, PipelineError, PipelineStage
from app.services.paywall_detection import detect_html_issue
from app.services.progress import ProgressTracker
from app.services.validation import domain_of, normalize_and_validate_url


def _fetch_error_from_status(status_code: int) -> ErrorCode:
    if status_code == 401:
        return ErrorCode.FETCH_HTTP_401
    if status_code == 403:
        return ErrorCode.FETCH_HTTP_403
    if status_code == 404:
        return ErrorCode.FETCH_HTTP_404
    return ErrorCode.FETCH_HTTP_ERROR


def _fetch_error_from_request(exc: httpx.RequestError) -> ErrorCode:
    if exc.__class__.__name__.endswith("Timeout"):
        return ErrorCode.FETCH_TIMEOUT
    return ErrorCode.FETCH_CONNECTION_FAILED


async def fetch_html(
    url: str,
    settings: Settings,
    *,
    article_ref: str | None = None,
    progress: ProgressTracker | None = None,
) -> str:
    """Download raw HTML for ``url``."""
    if progress is not None:
        await progress.emit(
            percent=progress.percent,
            message=f"Downloading article {article_ref or ''} from the web...".strip(),
            step="fetch",
            article_ref=article_ref,
            status="running",
        )

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
        code = _fetch_error_from_status(exc.response.status_code)
        raise PipelineError(
            PipelineStage.FETCH,
            code,
            article_ref=article_ref,
            url=url,
        ) from exc
    except httpx.RequestError as exc:
        raise PipelineError(
            PipelineStage.FETCH,
            _fetch_error_from_request(exc),
            article_ref=article_ref,
            url=url,
        ) from exc

    if len(response.content) > settings.fetch_max_bytes:
        raise PipelineError(
            PipelineStage.FETCH,
            ErrorCode.FETCH_PAGE_TOO_LARGE,
            article_ref=article_ref,
            url=url,
        )

    if progress is not None:
        await progress.emit(
            message=f"Download finished for article {article_ref or ''}.".strip(),
            step="fetch",
            article_ref=article_ref,
            status="completed",
        )

    return response.text

#clean ads that are directly embedded into articles
BAD_PATTERNS = [
    r"recommended stories",
    r"list of \d+ items",
    r"list \d+ of \d+",
    r"more from",
    r"trending",
    r"sponsored",
    r"advertisement",
    r"related",
    r"read more",
    r"watch now",
    r"breaking news",
]

import re

def filter_paragraphs(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    clean = []

    for p in paragraphs:
        lower = p.lower()

        # remove junk by regex
        if any(re.search(pattern, lower) for pattern in BAD_PATTERNS):
            continue

        # remove bullet-style junk
        if lower.startswith("list ") or lower.startswith("- list"):
            continue

        # remove very short junk (like "–" or "•")
        if len(p.split()) < 5:
            continue

        clean.append(p)

    return "\n\n".join(clean)

def extract_main_content(
    html: str,
    url: str,
    *,
    article_ref: str | None = None,
    progress: ProgressTracker | None = None,
) -> RawArticle:
    """Extract title, source domain and cleaned body text from raw HTML."""
    raw_body = (
        trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        or ""
    ).strip()

    #junk filter applied
    body_text = filter_paragraphs(raw_body)


    title = None
    try:
        metadata = trafilatura.extract_metadata(html, default_url=url)
        if metadata is not None:
            title = getattr(metadata, "title", None)
    except Exception:  # pragma: no cover - metadata is best-effort only
        title = None

    issue = detect_html_issue(html, body_text=body_text)
    if issue is not None:
        raise PipelineError(
            PipelineStage.EXTRACTION,
            issue,
            article_ref=article_ref,
            url=url,
        )

    if not body_text:
        raise PipelineError(
            PipelineStage.EXTRACTION,
            ErrorCode.EXTRACTION_EMPTY,
            article_ref=article_ref,
            url=url,
        )

    if progress is not None:
        # sync helper; caller may emit completion asynchronously
        pass

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
    progress: ProgressTracker | None = None,
) -> RawArticle:
    """End-to-end fetch: validate URL -> download HTML -> extract main content."""
    settings = settings or get_settings()

    if progress is not None:
        await progress.emit(
            message=f"Validating URL for article {article_ref or ''}...".strip(),
            step="validation",
            article_ref=article_ref,
            status="running",
        )

    url = normalize_and_validate_url(raw_url, article_ref=article_ref)

    if progress is not None:
        await progress.emit(
            step="validation",
            article_ref=article_ref,
            status="completed",
            message=f"URL validated for article {article_ref or ''}.".strip(),
        )

    html = await fetch_html(url, settings, article_ref=article_ref, progress=progress)

    if progress is not None:
        await progress.emit(
            message=f"Extracting main article text for article {article_ref or ''}...".strip(),
            step="extraction",
            article_ref=article_ref,
            status="running",
        )

    article = extract_main_content(html, url, article_ref=article_ref, progress=progress)

    if progress is not None:
        await progress.emit(
            message=f"Article text extracted for article {article_ref or ''}.".strip(),
            step="extraction",
            article_ref=article_ref,
            status="completed",
        )

    return article
