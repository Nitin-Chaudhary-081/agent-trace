"""Tool registry — register, deregister, and execute tools.

Enforces a per-call timeout (default 60s) so a hung external API never
blocks the agent loop. All errors surface as typed ToolResult failures
or typed exceptions; never bare excepts.
"""

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Callable

from agent.core.types import Action, ToolResult

DEFAULT_TIMEOUT_S = 60


class ToolError(Exception):
    """Base typed error for the tool registry."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ToolNotFoundError(ToolError):
    def __init__(self, name: str):
        super().__init__("TOOL_NOT_FOUND", f"Tool not registered: {name}")


class ToolValidationError(ToolError):
    def __init__(self, message: str):
        super().__init__("TOOL_VALIDATION_ERROR", message)


class ToolTimeoutError(ToolError):
    def __init__(self, name: str, timeout_s: float):
        super().__init__(
            "TOOL_TIMEOUT", f"Tool '{name}' exceeded timeout of {timeout_s}s"
        )


ToolFn = Callable[..., ToolResult]


class ToolRegistry:
    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S):
        self._tools: dict[str, ToolFn] = {}
        self.timeout_s = timeout_s

    def register(self, name: str, func: ToolFn) -> None:
        if name in self._tools:
            raise ToolValidationError(f"Tool already registered: {name}")
        self._tools[name] = func

    def deregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def has(self, name: str) -> bool:
        return name in self._tools

    def execute(self, action: Action) -> ToolResult:
        if not self.has(action.tool):
            return ToolResult.failure(
                f"tool_not_found:{action.tool}", duration_ms=0
            )

        func = self._tools[action.tool]
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(func, **action.params)
            try:
                result = future.result(timeout=self.timeout_s)
            except TimeoutError:
                duration = int((time.monotonic() - start) * 1000)
                return ToolResult.failure(
                    f"timeout:{action.tool}", duration_ms=duration
                )
            except Exception as exc:  # noqa: BLE001 - normalized into typed result
                duration = int((time.monotonic() - start) * 1000)
                return ToolResult.failure(
                    f"error:{action.tool}:{exc.__class__.__name__}:{exc}",
                    duration_ms=duration,
                )
        return result
