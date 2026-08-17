"""Tests for the agent runner execution loop."""

from agent.core.memory import MemoryFile
from agent.core.runner import AgentRunner
from agent.core.tool_registry import ToolRegistry
from agent.core.trajectory import Trajectory
from agent.core.types import ToolResult
from agent.services.logic_processor import LogicProcessor


def make_fake_tools() -> ToolRegistry:
    registry = ToolRegistry(timeout_s=2.0)
    registry.register(
        "web_search",
        lambda **kw: ToolResult(success=True, output={"url": "x"}, error=None, duration_ms=1),
    )
    registry.register(
        "supabase_insert",
        lambda **kw: ToolResult(success=True, output={"rows": 1}, error=None, duration_ms=1),
    )
    registry.register(
        "gmail_send",
        lambda **kw: ToolResult(success=True, output={"sent": True}, error=None, duration_ms=1),
    )
    return registry


def test_runner_completes_research_task(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    traj = Trajectory(tmp_path / "traj.sqlite")
    runner = AgentRunner(
        registry=make_fake_tools(),
        memory=memory,
        trajectory=traj,
        processor=LogicProcessor(),
    )

    run_id = runner.run("research Python and store and email summary", "research_and_email")

    run = traj.get_run(run_id)
    steps = traj.steps(run_id)

    assert run["status"] == "COMPLETED"
    assert len(steps) >= 3
    assert run["golden_path_score"] is not None


def test_runner_respects_max_steps(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    traj = Trajectory(tmp_path / "traj.sqlite")
    registry = ToolRegistry(timeout_s=2.0)
    for tool in ("web_search", "supabase_insert", "supabase_select", "gmail_send"):
        registry.register(
            tool,
            lambda **kw: ToolResult(success=True, output={}, error=None, duration_ms=1),
        )
    runner = AgentRunner(
        registry=registry,
        memory=memory,
        trajectory=traj,
        processor=LogicProcessor(max_steps=5),
        max_steps=2,
    )

    run_id = runner.run("research Python", "research_and_email")

    steps = traj.steps(run_id)
    assert len(steps) == 2
    assert traj.get_run(run_id)["status"] == "STOPPED_MAX_STEPS"


def test_runner_handles_tool_failure(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    traj = Trajectory(tmp_path / "traj.sqlite")
    registry = ToolRegistry(timeout_s=2.0)
    registry.register(
        "supabase_select",
        lambda **kw: ToolResult(
            success=False, output={}, error="fetch_failed", duration_ms=1
        ),
    )
    registry.register(
        "gmail_send",
        lambda **kw: ToolResult(success=True, output={}, error=None, duration_ms=1),
    )
    runner = AgentRunner(
        registry=registry,
        memory=memory,
        trajectory=traj,
        processor=LogicProcessor(max_steps=3),
        max_steps=3,
    )

    run_id = runner.run("query table and report", "data_lookup_report")

    run = traj.get_run(run_id)
    assert run["status"] == "FAILED"
    assert "fetch_failed" in run["error"]
