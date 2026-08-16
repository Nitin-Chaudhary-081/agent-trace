"""Tests for trajectory logging and JSONL export."""

import json

from agent.core.trajectory import Trajectory
from agent.core.types import Action, ToolResult


def test_log_step_writes_row(tmp_path):
    traj = Trajectory(tmp_path / "traj.sqlite")
    run_id = traj.new_run("research", "research_and_email")
    traj.log_step(
        run_id=run_id,
        step_number=1,
        action=Action(tool="web_search", params={"query": "flask"}),
        result=ToolResult(success=True, output={"url": "http://x"}, error=None, duration_ms=42),
    )

    steps = traj.steps(run_id)

    assert len(steps) == 1
    assert steps[0]["tool_called"] == "web_search"
    assert steps[0]["success"] is True
    assert steps[0]["duration_ms"] == 42


def test_steps_empty_for_unknown_run(tmp_path):
    traj = Trajectory(tmp_path / "traj.sqlite")

    assert traj.steps("nope") == []


def test_export_jsonl(tmp_path):
    traj = Trajectory(tmp_path / "traj.sqlite")
    run_id = traj.new_run("research flask", "research_and_email")
    traj.log_step(
        run_id=run_id,
        step_number=1,
        action=Action(tool="web_search", params={"query": "flask"}),
        result=ToolResult(success=True, output={"url": "http://x"}, error=None, duration_ms=42),
    )

    out = tmp_path / "export.jsonl"
    traj.export_jsonl(run_id, out)

    lines = out.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["task"] == "research flask"
    assert record["golden_path_score"] is None
    assert record["steps"][0]["tool_called"] == "web_search"


def test_run_task_persisted(tmp_path):
    traj = Trajectory(tmp_path / "traj.sqlite")
    run_id = traj.new_run("hello", "inbox_summarize")

    run = traj.get_run(run_id)

    assert run["task"] == "hello"
    assert run["task_type"] == "inbox_summarize"
