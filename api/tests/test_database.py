"""Tests for src.database — SQLite helpers."""

from src.database import connect, get_db, run_exists


def test_connect_creates_schema(tmp_path):
    db_path = tmp_path / "t.sqlite"
    conn = connect(str(db_path))

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('runs','steps')"
    ).fetchall()
    assert {row[0] for row in tables} == {"runs", "steps"}
    conn.close()


def test_get_db_context_commits(tmp_path):
    db_path = tmp_path / "t.sqlite"
    with get_db(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO runs (run_id, task, task_type, status, started_at) "
            "VALUES ('r1', 'task', 'research_and_email', 'RUNNING', 'now')"
        )

    with get_db(str(db_path)) as conn:
        row = conn.execute("SELECT 1 FROM runs WHERE run_id='r1'").fetchone()
        assert row is not None


def test_run_exists(tmp_path):
    db_path = tmp_path / "t.sqlite"
    conn = connect(str(db_path))
    conn.execute(
        "INSERT INTO runs (run_id, task, task_type, status, started_at) "
        "VALUES ('r1', 'task', 'research_and_email', 'RUNNING', 'now')"
    )
    conn.commit()

    assert run_exists(conn, "r1") is True
    assert run_exists(conn, "missing") is False
    conn.close()


def test_connect_default_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTTRACE_DB_PATH", str(tmp_path / "default.sqlite"))
    conn = connect()
    assert conn is not None
    conn.close()
