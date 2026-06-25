import pytest

from app.services.errors import PipelineError, PipelineStage
from app.services.validation import domain_of, normalize_and_validate_url


def test_valid_http_and_https():
    assert normalize_and_validate_url("https://a.com/x") == "https://a.com/x"
    assert normalize_and_validate_url("  http://b.com  ") == "http://b.com"


@pytest.mark.parametrize("bad", ["", "   ", None, "ftp://a.com", "not a url", "www.a.com"])
def test_invalid_urls_rejected(bad):
    with pytest.raises(PipelineError) as exc:
        normalize_and_validate_url(bad)
    assert exc.value.stage == PipelineStage.VALIDATION


def test_domain_of():
    assert domain_of("https://news.example.com/story") == "news.example.com"
