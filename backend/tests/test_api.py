from fastapi.testclient import TestClient

from app.main import app
from app.services import fetch_service

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


async def _fake_fetch_html(url, settings, *, article_ref=None):
    return SAMPLE_HTML


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
    for article in data["articles"]:
        assert article["sentences"], "expected prepared sentences"
        # Webpage noise (nav/ads/footer) should be stripped by extraction.
        joined = " ".join(s["text"] for s in article["sentences"])
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
    assert len(data["articles"]) == 1  # B still processed
    assert len(data["errors"]) == 1
    assert data["errors"][0]["stage"] == "validation"
    assert data["errors"][0]["article_ref"] == "A"


def test_fetch_endpoint_rejects_invalid_url():
    response = client.post("/api/fetch", json={"url": "ftp://example.com"})
    assert response.status_code == 422
    assert response.json()["detail"]["stage"] == "validation"
