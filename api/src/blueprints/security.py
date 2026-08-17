"""Security endpoints — adversarial attack results (Module 5).

Runs the four attacks against a *throwaway* tool registry built from safe,
deterministic fakes — never the production live registry (no real Gmail
reads, web searches, or Supabase calls on a poll). Results are cached for
`CACHE_TTL_S` so the observer UI's polling does not re-execute attacks on
every request.
"""

import time

from flask import Blueprint, current_app, jsonify

from agent.core.tool_registry import ToolRegistry
from agent.core.types import ToolResult
from agent.security.adversarial import AdversarialSuite

bp = Blueprint("security", __name__)

CACHE_TTL_S = 60
_ATTACKS_CACHE: dict[str, object] = {"t": 0.0, "results": []}


def _fake_registry() -> ToolRegistry:
    """Deterministic, offline-safe tool surface used only by the attack suite."""
    registry = ToolRegistry(timeout_s=5.0)

    def web_search(**kw) -> ToolResult:
        return ToolResult(
            success=True,
            output={"url": "https://example.com", "content": "Python Flask summary"},
            error=None,
            duration_ms=1,
        )

    def supabase(**kw) -> ToolResult:
        table = kw.get("table", "public_data")
        if table != "public_data":
            return ToolResult(success=False, output={}, error="table_not_allowed", duration_ms=1)
        return ToolResult(success=True, output={"data": [{"id": 1, "note": "row"}]}, error=None, duration_ms=1)

    def supabase_insert(**kw) -> ToolResult:
        return ToolResult(success=True, output={"rows_affected": 1}, error=None, duration_ms=1)

    def gmail_read(**kw) -> ToolResult:
        return ToolResult(
            success=True,
            output={"messages": [{"id": "1", "subject": "Hello", "snippet": "Meeting at 3pm"}]},
            error=None,
            duration_ms=1,
        )

    def gmail(**kw) -> ToolResult:
        return ToolResult(success=True, output={"messages": []}, error=None, duration_ms=1)

    registry.register("web_search", web_search)
    registry.register("supabase_select", supabase)
    registry.register("supabase_insert", supabase_insert)
    registry.register("supabase_update", supabase)
    registry.register("supabase_delete", supabase)
    registry.register("gmail_list_inbox", gmail)
    registry.register("gmail_read_email", gmail_read)
    registry.register("gmail_send", gmail)
    return registry


@bp.get("/attacks")
def get_attacks():
    now = time.monotonic()
    if now - _ATTACKS_CACHE["t"] >= CACHE_TTL_S or not _ATTACKS_CACHE["results"]:
        suite = AdversarialSuite()
        suite.build(registry=_fake_registry(), trajectory=None, tmp_path="/tmp/agenttrace_security")
        _ATTACKS_CACHE["results"] = suite.run_all()
        _ATTACKS_CACHE["t"] = now
    return jsonify({"results": _ATTACKS_CACHE["results"]}), 200