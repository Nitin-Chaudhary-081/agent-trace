"""API endpoint tests: health, tasks, runs, memory, security."""

import json


def test_health(client):
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_submit_task_returns_run_id(client):
    resp = client.post(
        "/api/v1/tasks",
        json={"task": "research Python", "task_type": "research_and_email"},
    )

    assert resp.status_code == 202
    body = resp.get_json()
    assert "run_id" in body
    assert len(body["run_id"]) > 0


def test_get_run_returns_steps(client):
    resp = client.post(
        "/api/v1/tasks",
        json={"task": "research Python", "task_type": "research_and_email"},
    )
    run_id = resp.get_json()["run_id"]

    resp = client.get(f"/api/v1/runs/{run_id}")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["run"]["task"] == "research Python"


def test_get_run_missing_returns_404(client):
    resp = client.get("/api/v1/runs/does-not-exist")

    assert resp.status_code == 404


def test_export_run_jsonl(client, tmp_path):
    resp = client.post(
        "/api/v1/tasks",
        json={"task": "research Python", "task_type": "research_and_email"},
    )
    run_id = resp.get_json()["run_id"]

    resp = client.get(f"/api/v1/runs/{run_id}/export")

    assert resp.status_code == 200
    assert resp.content_type.startswith("text/plain")
    record = json.loads(resp.get_data(as_text=True).strip())
    assert record["task_type"] == "research_and_email"
    assert isinstance(record["deviations"], list)
    assert record["outcome"] in (
        "COMPLETED",
        "FAILED",
        "RUNNING",
        "STOPPED_MAX_STEPS",
    )


def test_get_memory_sections(client):
    resp = client.get("/api/v1/memory")

    assert resp.status_code == 200
    body = resp.get_json()
    for section in ("GOAL", "STATUS", "PROGRESS", "COMPLETED_STEPS", "SESSION_ID"):
        assert section in body["sections"]


def test_get_security_report(client):
    resp = client.get("/api/v1/security/attacks")

    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body["results"], list)
