import asyncio
import io

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.api.routes import compare as compare_route
from app.main import app
from app.config import get_settings
from app.services import fetch_service
from app.services.errors import ErrorCode
from app.services.paywall_detection import detect_html_issue

client = TestClient(app)

SAMPLE_HTML = """
<html><head><title>Budget passed by parliament</title></head>
<body>
  <nav>Home About Contact Subscribe</nav>
  <aside>Advertisement: buy now!</aside>
  <article>
    <h1>Budget passed by parliament</h1>
    <p>The government announced a sweeping new national budget on Tuesday, allocating
    record funding to infrastructure and health programmes across the country. Officials
    described the package as the most ambitious in a decade.</p>
    <p>Critics, however, said the budget disproportionately favours wealthy households and
    large corporations. Opposition leaders argued that essential services for low-income
    families had been neglected once again.</p>
    <p>Treasury officials defended the plan in a lengthy briefing. They argued that the
    measures would boost long-term economic growth and create thousands of new jobs over
    the coming years.</p>
  </article>
  <footer>Copyright 2026. All rights reserved.</footer>
</body></html>
"""

PAYWALL_HTML = """
<html><head><title>Premium story</title></head>
<body>
  <div class="paywall">Subscribe to continue reading this article.</div>
</body></html>
"""


async def _fake_fetch_html(url, settings, *, article_ref=None, progress=None):
    return SAMPLE_HTML


def _make_docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _make_pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_compare_with_mocked_fetch(monkeypatch):
    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    payload = {
        "article_a_url": "https://outlet-a.com/budget",
        "article_b_url": "https://outlet-b.com/budget",
        "focus": "political",
    }
    response = client.post("/api/compare", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["focus"] == "political"
    assert data["errors"] == []
    assert len(data["articles"]) == 2
    assert data["processing"]["total_elapsed_seconds"] >= 0
    assert data["processing"]["message"]
    for article in data["articles"]:
        assert article["paragraphs"], "expected prepared article paragraphs"
        joined = " ".join(article["paragraphs"])
        assert "Advertisement" not in joined
        assert "Copyright" not in joined


def test_compare_reports_invalid_url_per_article(monkeypatch):
    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    payload = {
        "article_a_url": "not-a-valid-url",
        "article_b_url": "https://outlet-b.com/budget",
    }
    response = client.post("/api/compare", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert len(data["articles"]) == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["stage"] == "validation"
    assert data["errors"][0]["code"] == ErrorCode.URL_INVALID_SCHEME.value
    assert data["errors"][0]["article_ref"] == "A"


def test_fetch_endpoint_rejects_invalid_url():
    response = client.post("/api/fetch", json={"url": "ftp://example.com"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["stage"] == "validation"
    assert detail["code"] == ErrorCode.URL_INVALID_SCHEME.value


def test_fetch_reports_paywall_error(monkeypatch):
    async def _paywall_html(url, settings, *, article_ref=None, progress=None):
        return PAYWALL_HTML

    monkeypatch.setattr(fetch_service, "fetch_html", _paywall_html)
    response = client.post("/api/fetch", json={"url": "https://news.example.com/story"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == ErrorCode.EXTRACTION_PAYWALL.value
    assert "paywall" in detail["message"].lower() or "membership" in detail["message"].lower()


def test_paywall_detection():
    assert detect_html_issue(PAYWALL_HTML, body_text="") == ErrorCode.EXTRACTION_PAYWALL


def test_upload_docx():
    content = _make_docx_bytes(
        "The government announced a sweeping new national budget on Tuesday for all citizens."
    )
    response = client.post(
        "/api/upload",
        files={"file": ("budget.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["article"]["source_type"] == "upload"
    assert "budget" in data["article"]["body_text"].lower()
    assert data["processing"]["total_elapsed_seconds"] >= 0


def test_upload_rejects_unsupported_type():
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == ErrorCode.UPLOAD_UNSUPPORTED_TYPE.value


def test_compare_files_with_docx_and_url(monkeypatch):
    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    docx_bytes = _make_docx_bytes(
        "Opposition leaders argued that essential services for low-income families had been neglected again."
    )
    response = client.post(
        "/api/compare/files",
        data={"article_b_url": "https://outlet-b.com/budget", "focus": "general"},
        files={"article_a_file": ("article-a.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["articles"]) == 2
    assert any(a["source_type"] == "upload" for a in data["articles"])


ARTICLE_A_TEXT = (
    "The government announced a sweeping new national budget on Tuesday, allocating "
    "record funding to infrastructure and health programmes across the country."
)
ARTICLE_B_TEXT = (
    "Opposition leaders argued that essential services for low-income families had "
    "been neglected again in the newly announced national budget."
)


def test_compare_with_pasted_text_json():
    payload = {
        "article_a_text": ARTICLE_A_TEXT,
        "article_b_text": ARTICLE_B_TEXT,
        "focus": "general",
    }
    response = client.post("/api/compare", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["errors"] == []
    assert len(data["articles"]) == 2
    assert all(a["source_type"] == "text" for a in data["articles"])


def test_compare_json_mixed_text_and_url(monkeypatch):
    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    payload = {
        "article_a_text": ARTICLE_A_TEXT,
        "article_b_url": "https://outlet-b.com/budget",
        "focus": "general",
    }
    response = client.post("/api/compare", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert len(data["articles"]) == 2
    source_types = {a["source_type"] for a in data["articles"]}
    assert source_types == {"text", "url"}


def test_compare_rejects_missing_sources():
    response = client.post("/api/compare", json={"focus": "general"})
    assert response.status_code == 422


def test_compare_reports_empty_text_error():
    payload = {
        "article_a_text": "short",
        "article_b_text": ARTICLE_B_TEXT,
    }
    response = client.post("/api/compare", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert len(data["errors"]) == 1
    assert data["errors"][0]["code"] == ErrorCode.TEXT_TOO_SHORT.value
    assert data["errors"][0]["article_ref"] == "A"


def test_compare_timeout_returns_structured_error(monkeypatch):
    async def slow_pipeline(*_args, **_kwargs):
        await asyncio.sleep(1)

    settings = get_settings()
    monkeypatch.setattr(settings, "comparison_timeout_seconds", 0.01)
    monkeypatch.setattr(compare_route, "process_pair_inputs_with_comparison", slow_pipeline)

    payload = {
        "article_a_text": ARTICLE_A_TEXT,
        "article_b_text": ARTICLE_B_TEXT,
    }
    response = client.post("/api/compare", json=payload)

    assert response.status_code == 408
    assert response.json()["detail"]["code"] == "comparison_timeout"


def test_compare_stream_timeout_returns_error_event(monkeypatch):
    async def slow_pipeline(*_args, **_kwargs):
        await asyncio.sleep(1)

    settings = get_settings()
    monkeypatch.setattr(settings, "comparison_timeout_seconds", 0.01)
    monkeypatch.setattr(compare_route, "process_pair_inputs_with_comparison", slow_pipeline)

    payload = {
        "article_a_text": ARTICLE_A_TEXT,
        "article_b_text": ARTICLE_B_TEXT,
    }

    with client.stream("POST", "/api/compare/stream", json=payload) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: error" in body
    assert "comparison_timeout" in body


def test_specific_article_errors_are_not_replaced_by_timeout():
    payload = {
        "article_a_text": "short",
        "article_b_text": ARTICLE_B_TEXT,
    }
    response = client.post("/api/compare", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["errors"][0]["code"] == ErrorCode.TEXT_TOO_SHORT.value


def test_compare_files_with_pasted_text_form(monkeypatch):
    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    response = client.post(
        "/api/compare/files",
        data={
            "article_a_text": ARTICLE_A_TEXT,
            "article_b_url": "https://outlet-b.com/budget",
            "focus": "general",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["articles"]) == 2
    assert any(a["source_type"] == "text" for a in data["articles"])
