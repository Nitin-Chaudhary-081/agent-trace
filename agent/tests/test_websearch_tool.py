"""Tests for the live Web Search tool (Module 3).

Success path hits real network (no credentials needed). Failure and timeout
paths are deterministic via injection so CI stays fast and offline-safe.
"""

import time

from agent.tools.websearch_tool import WebSearchTool
from agent.core.types import ToolResult


def _tool(**overrides) -> WebSearchTool:
    base = {"timeout_s": 10.0}
    base.update(overrides)
    return WebSearchTool(**base)


class _SlowResponder:
    def get(self, *args, **kwargs):
        time.sleep(3.0)
        return None


class _FailingResponder:
    def get(self, *args, **kwargs):
        raise RuntimeError("connection refused")


class _HTMLResponder:
    def get(self, *args, **kwargs):
        class Resp:
            status_code = 200
            text = (
                "<html><body><h1>Python Flask Documentation</h1>"
                "<p>Flask is a microframework for Python.</p>"
                "<a href='https://flask.palletsprojects.com/en/stable/'>docs</a>"
                "</body></html>"
            )

            def raise_for_status(self):
                return None

        return Resp()


def test_live_search_returns_content():
    tool = _tool()
    result = tool.invoke(query="Python Flask documentation")
    assert result.success is True
    assert result.output["url"] != ""
    assert "flask" in result.output["content"].lower() or "python" in result.output["content"].lower()


def test_success_schema_matches_spec():
    tool = _tool(session=_HTMLResponder())
    result = tool.invoke(query="python flask docs", url="https://example.org/flask")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.error is None
    assert set(result.output) == {"url", "content"}
    assert "Flask" in result.output["content"]


def test_failure_returns_typed_failure():
    tool = _tool(session=_FailingResponder())
    result = tool.invoke(query="python flask docs", url="https://example.org/flask")
    assert result.success is False
    assert result.error == "fetch_failed"


def test_timeout_returns_typed_failure():
    tool = _tool(session=_SlowResponder(), timeout_s=1.0)
    start = time.monotonic()
    result = tool.invoke(query="python flask docs", url="https://example.org/flask")
    elapsed = time.monotonic() - start
    assert result.success is False
    assert result.error == "timeout"
    assert elapsed < 3.0


def test_blank_query_rejected():
    tool = _tool(session=_HTMLResponder())
    result = tool.invoke(query="   ")
    assert result.success is False
    assert result.error == "invalid_query"