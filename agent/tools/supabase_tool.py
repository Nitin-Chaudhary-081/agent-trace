"""Live Supabase tool — PostgREST REST API via pure-Python requests.

Operations: select, insert, update, delete on any allowed table.
Auth: SUPABASE_URL + SUPABASE_SERVICE_KEY from env. A table whitelist
(Module 5 Attack 2) blocks out-of-scope tables at the tool boundary.
Typed errors only: not_configured / invalid_operation / table_not_allowed /
invalid_table_name / timeout / api_error.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import requests

from agent.core.types import ToolResult
from agent.tools import BaseTool

DEFAULT_TIMEOUT_S = 60.0
VALID_OPERATIONS = ("select", "insert", "update", "delete")
_TABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class SupabaseTool(BaseTool):
    name: str = "supabase"
    url: str = ""
    service_key: str = ""
    allowed_tables: tuple[str, ...] = ()
    timeout_s: float = DEFAULT_TIMEOUT_S
    session: Any = field(default=None, repr=False)

    def _postgrest(self, method: str, path: str, json=None, params=None, prefer=None) -> dict:
        """Runs a PostgREST call with real timeout enforcement in a worker."""

        def _call() -> requests.Response:
            session = self.session or requests.Session()
            headers = {
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": "application/json",
            }
            if prefer:
                headers["Prefer"] = prefer
            kwargs: dict[str, Any] = {
                "headers": headers,
                "timeout": self.timeout_s,
            }
            if json is not None:
                kwargs["json"] = json
            if params is not None:
                kwargs["params"] = params
            return session.request(method, f"{self.url.rstrip('/')}{path}", **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_call)
            try:
                resp = future.result(timeout=self.timeout_s)
            except TimeoutError:
                return {"error": "timeout"}

        if resp.status_code >= 400:
            detail = (resp.text or "")[:200]
            return {"error": f"api_error: {resp.status_code} {detail}"}
        try:
            data = resp.json()
        except ValueError:
            data = []
        return {"data": data}

    def _validate(self, operation: str, table: str) -> str | None:
        if operation not in VALID_OPERATIONS:
            return "invalid_operation"
        if not _TABLE_RE.match(table or ""):
            return "invalid_table_name"
        if self.allowed_tables and table not in self.allowed_tables:
            return "table_not_allowed"
        return None

    def invoke(self, operation: str = "", table: str = "", **params: Any) -> ToolResult:
        if not self.url or not self.service_key:
            return ToolResult.failure("not_configured")
        err = self._validate(operation, table)
        if err:
            return ToolResult.failure(err)

        data = params.get("data") or []
        limit = params.get("limit", 100)
        eq = params.get("eq") or {}
        order = params.get("order") or ""
        start = time.monotonic()

        if operation == "select":
            qs = {"select": "*", "limit": str(limit)}
            for col, val in eq.items():
                qs[col] = f"eq.{val}"
            if order:
                qs["order"] = order
            res = self._postgrest("GET", f"/rest/v1/{table}", params=qs)
        elif operation == "insert":
            res = self._postgrest(
                "POST",
                f"/rest/v1/{table}",
                json=data,
                prefer="return=representation",
            )
            if "data" not in res:
                res["rows_affected"] = 0
        elif operation == "update":
            qs = {}
            for col, val in eq.items():
                qs[col] = f"eq.{val}"
            res = self._postgrest("PATCH", f"/rest/v1/{table}", json=data, params=qs)
        elif operation == "delete":
            qs = {}
            for col, val in eq.items():
                qs[col] = f"eq.{val}"
            res = self._postgrest("DELETE", f"/rest/v1/{table}", params=qs)

        elapsed = int((time.monotonic() - start) * 1000)
        if "error" in res:
            return ToolResult.failure(res["error"], duration_ms=elapsed)

        rows = res.get("data", [])
        return ToolResult(
            success=True,
            output={
                "data": rows,
                "rows_affected": res.get("rows_affected", len(rows)),
            },
            error=None,
            duration_ms=elapsed,
        )