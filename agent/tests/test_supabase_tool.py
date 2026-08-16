"""Tests for the live Supabase tool (Module 3).

The tool itself performs zero mocks — it always talks to the PostgREST REST
endpoint via requests. Transport-level fakes are injected only in tests that
must run offline; live insert/read/delete tests run when SUPABASE_URL +
SUPABASE_SERVICE_KEY are present.
"""

import os

import pytest

from agent.tools.supabase_tool import SupabaseTool
from agent.core.types import ToolResult


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.text}")


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        resp = self.responses.pop(0)
        return resp


def _creds():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    return url, key


def test_absent_creds_returns_typed_failure(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    tool = SupabaseTool()
    result = tool.invoke(operation="select", table="public_data")
    assert result.success is False
    assert result.error == "not_configured"


def test_invalid_operation_rejected():
    tool = SupabaseTool(url="https://x.supabase.co", service_key="k")
    result = tool.invoke(operation="drop", table="public_data")
    assert result.success is False
    assert result.error == "invalid_operation"


def test_table_whitelist_enforced():
    tool = SupabaseTool(
        url="https://x.supabase.co",
        service_key="k",
        allowed_tables=["public_data"],
    )
    result = tool.invoke(operation="select", table="private_keys")
    assert result.success is False
    assert result.error == "table_not_allowed"


def test_unsafe_table_name_rejected():
    tool = SupabaseTool(url="https://x.supabase.co", service_key="k")
    result = tool.invoke(operation="select", table="public_data; DROP TABLE x; --")
    assert result.success is False
    assert result.error == "invalid_table_name"


def test_success_schema_matches_spec():
    url, key = _creds()
    tool = SupabaseTool(
        url=url or "https://x.supabase.co",
        service_key=key or "k",
        session=FakeSession(
            [FakeResponse(200, json_data=[{"id": 1, "note": "hello"}])]
        ),
    )
    result = tool.invoke(operation="select", table="public_data")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.error is None
    assert set(result.output) == {"data", "rows_affected"}
    assert result.output["data"] == [{"id": 1, "note": "hello"}]


def test_timeout_returns_typed_failure():
    class SlowSession:
        def request(self, *a, **k):
            raise TimeoutError("timed out")

    tool = SupabaseTool(
        url="https://x.supabase.co",
        service_key="k",
        session=SlowSession(),
        timeout_s=1.0,
    )
    result = tool.invoke(operation="select", table="public_data")
    assert result.success is False
    assert result.error == "timeout"


@pytest.mark.skipif(not all(_creds()), reason="SUPABASE creds not set")
def test_live_insert_read_delete():
    url, key = _creds()
    tool = SupabaseTool(url=url, service_key=key)
    marker = f"at_test_{os.getpid()}"
    ins = tool.invoke(operation="insert", table="public_data", data=[{"note": marker}])
    assert ins.success is True, ins.error
    sel = tool.invoke(operation="select", table="public_data", limit=1000)
    assert sel.success is True
    assert any(r.get("note") == marker for r in sel.output["data"])
    ids = [r["id"] for r in sel.output["data"] if r.get("note") == marker]
    for rid in ids:
        tool.invoke(operation="delete", table="public_data", eq={"id": rid})
    sel2 = tool.invoke(operation="select", table="public_data", limit=1000)
    assert not any(r.get("note") == marker for r in sel2.output["data"])