"""DataParser — normalize tool outputs before they enter agent context.

Module 1 provides a passthrough normalizer plus a safety hook for the PII
scrubber (Attack 3 in Module 5). Every tool output that will be logged or
added to context must pass through `normalize`.
"""

from typing import Any

from agent.core.types import ToolResult

SENSITIVE_FIELDS = ("password", "token", "secret", "api_key", "refresh_token")


class DataParser:
    def __init__(self, scrub_pii: bool = False):
        self.scrub_pii = scrub_pii

    def normalize(self, tool_name: str, result: ToolResult) -> dict[str, Any]:
        if not result.success:
            return {"tool": tool_name, "success": False, "error": result.error}

        output = dict(result.output)
        if self.scrub_pii:
            output = self._scrub(output)
        return {"tool": tool_name, "success": True, "data": output}

    def _scrub(self, data: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_FIELDS or "secret" in key.lower():
                out[key] = "[REDACTED]"
            else:
                out[key] = value
        return out
