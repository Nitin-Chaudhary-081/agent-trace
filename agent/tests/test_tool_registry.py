"""Tests for the tool registry: registration, execution, timeout, typed errors."""

import time

import pytest

from agent.core.tool_registry import (
    ToolRegistry,
    ToolValidationError,
)
from agent.core.types import Action, ToolResult


def make_ok_tool() -> ToolResult:
    return ToolResult(success=True, output={"ok": True}, error=None, duration_ms=1)


def make_slow_tool(timeout: float = 5.0) -> ToolResult:
    time.sleep(timeout)
    return ToolResult(success=True, output={"slow": True}, error=None, duration_ms=5000)


def make_broken_tool() -> ToolResult:
    raise RuntimeError("boom")


def test_register_then_execute(tmp_path):
    registry = ToolRegistry()
    registry.register("ok", make_ok_tool)

    result = registry.execute(Action(tool="ok", params={}))

    assert result.success is True
    assert result.output == {"ok": True}


def test_execute_unknown_tool_returns_typed_error(tmp_path):
    registry = ToolRegistry()

    result = registry.execute(Action(tool="missing", params={}))

    assert result.success is False
    assert result.error is not None
    assert "missing" in result.error


def test_deregister_removes_tool(tmp_path):
    registry = ToolRegistry()
    registry.register("ok", make_ok_tool)
    registry.deregister("ok")

    result = registry.execute(Action(tool="ok", params={}))

    assert result.success is False
    assert result.error is not None


def test_register_duplicate_raises(tmp_path):
    registry = ToolRegistry()
    registry.register("ok", make_ok_tool)

    with pytest.raises(ToolValidationError):
        registry.register("ok", make_ok_tool)


def test_execute_times_out_after_timeout(tmp_path):
    registry = ToolRegistry(timeout_s=0.05)
    registry.register("slow", make_slow_tool)

    result = registry.execute(Action(tool="slow", params={}))

    assert result.success is False
    assert "timeout" in (result.error or "").lower()


def test_execute_returns_failed_result_on_exception(tmp_path):
    registry = ToolRegistry()
    registry.register("broken", make_broken_tool)

    result = registry.execute(Action(tool="broken", params={}))

    assert result.success is False
    assert result.error is not None
