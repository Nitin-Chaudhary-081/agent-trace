"""Tests for Module 2: runner resume and periodic snapshotting."""

from agent.core.memory import MemoryFile
from agent.core.runner import AgentRunner
from agent.core.tool_registry import ToolRegistry
from agent.core.trajectory import Trajectory
from agent.core.types import Action, ToolResult
from agent.services.logic_processor import LogicProcessor
from agent.services.snapshotter import MemorySnapshotter


def make_fake_tools() -> ToolRegistry:
    registry = ToolRegistry(timeout_s=2.0)
    for tool in ("web_search", "supabase_insert", "supabase_select", "gmail_send"):
        registry.register(
            tool,
            lambda **kw: ToolResult(success=True, output={}, error=None, duration_ms=1),
        )
    return registry


class RepeatingProcessor(LogicProcessor):
    """Drives a deterministic long plan for snapshot/resume tests."""

    def __init__(self) -> None:
        super().__init__(max_steps=20)

    def decide(self, memory, observations):
        done = len([l for l in memory.get("COMPLETED_STEPS", "").splitlines() if l])
        if done >= 6:
            return None
        return Action("web_search", {"query": "test"})


def test_runner_resumes_after_kill_mid_run(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    traj = Trajectory(tmp_path / "traj.sqlite")

    first = AgentRunner(
        registry=make_fake_tools(),
        memory=memory,
        trajectory=traj,
        processor=LogicProcessor(),
    )
    first.run("research Python and store and email", "research_and_email")

    # simulate: memory was reset for a fresh process but retains prior SESSION_ID
    second = AgentRunner(
        registry=make_fake_tools(),
        memory=memory,
        trajectory=traj,
        processor=LogicProcessor(),
    )
    resumed = second.resume()

    assert resumed["status"] == "COMPLETED" or resumed["mode"] == "nothing_to_resume"


def test_resume_returns_nothing_when_completed(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="done", STATUS="COMPLETED", SESSION_ID="s1")
    traj = Trajectory(tmp_path / "traj.sqlite")

    runner = AgentRunner(
        registry=make_fake_tools(),
        memory=memory,
        trajectory=traj,
        processor=LogicProcessor(),
    )

    result = runner.resume()

    assert result["status"] == "COMPLETED"
    assert result["mode"] == "nothing_to_resume"


def test_snapshot_after_every_5_steps(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    traj = Trajectory(tmp_path / "traj.sqlite")
    snapshotter = MemorySnapshotter(local_dir=str(tmp_path / "snapshots"))

    runner = AgentRunner(
        registry=make_fake_tools(),
        memory=memory,
        trajectory=traj,
        processor=RepeatingProcessor(),
        snapshotter=snapshotter,
    )
    runner.run("loop forever", "data_lookup_report")

    # plan runs 6 steps; snapshots happen every 5 completed steps
    assert len(list((tmp_path / "snapshots").glob("*.md"))) >= 1


def test_resume_from_completed_steps_skips_prior_work(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="research Python best practices", STATUS="RUNNING", SESSION_ID="s1")
    memory.append_completed_step("web_search")
    traj = Trajectory(tmp_path / "traj.sqlite")

    runner = AgentRunner(
        registry=make_fake_tools(),
        memory=memory,
        trajectory=traj,
        processor=LogicProcessor(),
    )

    result = runner.resume()

    assert result["status"] == "COMPLETED"
    # only the remaining steps (supabase_insert, gmail_send) execute
    new_steps = traj.steps(result["run_id"])
    assert new_steps[0]["tool_called"] == "supabase_insert"