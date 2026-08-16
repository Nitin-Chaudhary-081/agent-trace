"""Tests for Reporter — run summary and JSONL export records."""

import json

from agent.core.trajectory import Trajectory
from agent.core.types import Action, ToolResult
from agent.services.reporter import Reporter


def _seed_run(tmp_path) -> tuple[Trajectory, str]:
    traj = Trajectory(tmp_path / "traj.sqlite")
    run_id = traj.new_run("research flask", "research_and_email")
    traj.log_step(
        run_id=run_id,
        step_number=1,
        action=Action(tool="web_search", params={"query": "flask"}),
        result=ToolResult(success=True, output={}, error=None, duration_ms=5),
    )
    traj.set_run_score(run_id, 100.0)
    return traj, run_id


def test_summarize_run(tmp_path):
    traj, run_id = _seed_run(tmp_path)
    reporter = Reporter(traj)

    summary = reporter.summarize_run(run_id)

    assert summary["found"] is True
    assert summary["steps_taken"] == 1
    assert summary["golden_path_score"] == 100.0


def test_summarize_run_missing(tmp_path):
    traj = Trajectory(tmp_path / "traj.sqlite")
    reporter = Reporter(traj)

    summary = reporter.summarize_run("nope")

    assert summary["found"] is False


def test_export_record_is_valid_jsonl_line(tmp_path):
    traj, run_id = _seed_run(tmp_path)
    reporter = Reporter(traj)

    line = reporter.export_record(run_id)
    record = json.loads(line)

    assert record["task"] == "research flask"
    assert record["golden_path_score"] == 100.0
    assert record["steps"][0]["tool_called"] == "web_search"