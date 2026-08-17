"""Tests for Module 4 Supabase mirroring of trajectory rows (agent_runs).

The mirror posts to PostgREST like every other live integration. Transport
fakes are injected only in offline tests; no mock lives in the tool itself.
"""

import json

from agent.core.trajectory import Trajectory
from agent.core.types import Action, ToolResult
from agent.services.reporter import Reporter
from agent.services.trajectory_mirror import TrajectoryMirror


class FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        return self._json


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0) if self.responses else FakeResponse(204)


def _seed_run(tmp_path):
    traj = Trajectory(tmp_path / "traj.sqlite")
    run_id = traj.new_run("lookup records from table", "data_lookup_report")
    traj.log_step(
        run_id=run_id,
        step_number=1,
        action=Action(tool="supabase_select", params={"table": "records"}),
        result=ToolResult(success=True, output={"data": []}, error=None, duration_ms=7),
    )
    traj.set_run_status(run_id, "COMPLETED")
    traj.set_run_score(run_id, 100.0)
    return traj, run_id


def test_mirror_absent_creds_is_noop(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    traj, run_id = _seed_run(tmp_path)
    mirror = TrajectoryMirror(trajectory=traj)
    assert mirror.is_active() is False
    mirror.sync_run(run_id)  # must not raise


def test_mirror_posts_steps_and_run(tmp_path):
    traj, run_id = _seed_run(tmp_path)
    session = FakeSession()
    mirror = TrajectoryMirror(
        trajectory=traj,
        url="https://x.supabase.co",
        service_key="k",
        session=session,
    )
    assert mirror.is_active() is True
    mirror.sync_run(run_id)

    assert len(session.calls) == 2  # one for run, one for steps
    post_methods = [c[0] for c in session.calls]
    assert all(m == "POST" for m in post_methods)
    run_payload = session.calls[0][2]["json"]
    assert run_payload["run_id"] == run_id
    assert run_payload["task_type"] == "data_lookup_report"
    assert run_payload["golden_path_score"] == 100.0
    steps_payload = session.calls[1][2]["json"]
    assert steps_payload["run_id"] == run_id
    assert steps_payload["step_number"] == 1
    assert steps_payload["tool_called"] == "supabase_select"


def test_export_record_has_deviations_and_outcome(tmp_path):
    traj, run_id = _seed_run(tmp_path)
    reporter = Reporter(traj)
    record = json.loads(reporter.export_record(run_id))
    assert record["task_type"] == "data_lookup_report"
    assert record["golden_path_score"] == 100.0
    assert isinstance(record["deviations"], list)
    assert record["outcome"] == "COMPLETED"
    assert len(record["steps"]) == 1
    assert record["steps"][0]["tool_called"] == "supabase_select"


def test_export_jsonl_roundtrip(tmp_path):
    traj, run_id = _seed_run(tmp_path)
    traj.log_step(
        run_id=run_id,
        step_number=2,
        action=Action(tool="gmail_send", params={"to": "self"}),
        result=ToolResult(success=True, output={"messages": [{"id": "x"}]}, error=None, duration_ms=4),
    )
    reporter = Reporter(traj)
    out = tmp_path / "export.jsonl"
    reporter.export_jsonl(run_id, str(out))
    line = out.read_text().strip()
    record = json.loads(line)
    assert record["golden_path_score"] == 100.0
    assert record["deviations"] == []
    assert len(record["steps"]) == 2