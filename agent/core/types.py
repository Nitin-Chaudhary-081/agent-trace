"""Shared dataclasses and typed results for the agent runtime.

Every tool returns a ToolResult; every action is an Action. Typed results
throughout — never bare `except`.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    """A single tool invocation requested by the logic processor."""

    tool: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "params": self.params}


@dataclass(frozen=True)
class ToolResult:
    """Typed result returned by any registered tool."""

    success: bool
    output: dict[str, Any]
    error: str | None
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def failure(cls, error: str, duration_ms: int = 0) -> "ToolResult":
        return cls(success=False, output={}, error=error, duration_ms=duration_ms)
