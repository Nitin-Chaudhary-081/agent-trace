"""Tests for DataParser — output normalization and PII scrubbing."""

from agent.core.types import ToolResult
from agent.services.data_parser import DataParser


def test_normalize_success():
    parser = DataParser()
    result = ToolResult(success=True, output={"url": "http://x"}, error=None, duration_ms=1)

    out = parser.normalize("web_search", result)

    assert out["success"] is True
    assert out["tool"] == "web_search"
    assert out["data"] == {"url": "http://x"}


def test_normalize_failure_preserves_error():
    parser = DataParser()
    result = ToolResult(success=False, output={}, error="fetch_failed", duration_ms=1)

    out = parser.normalize("web_search", result)

    assert out["success"] is False
    assert out["error"] == "fetch_failed"


def test_scrub_redacts_sensitive_fields():
    parser = DataParser(scrub_pii=True)
    result = ToolResult(
        success=True,
        output={"email": "a@b.com", "api_key": "secret-123"},
        error=None,
        duration_ms=1,
    )

    out = parser.normalize("gmail", result)

    assert out["data"]["api_key"] == "[REDACTED]"
    assert out["data"]["email"] == "a@b.com"


def test_scrub_off_no_redaction():
    parser = DataParser(scrub_pii=False)
    result = ToolResult(
        success=True, output={"api_key": "secret"}, error=None, duration_ms=1
    )

    out = parser.normalize("gmail", result)

    assert out["data"]["api_key"] == "secret"
