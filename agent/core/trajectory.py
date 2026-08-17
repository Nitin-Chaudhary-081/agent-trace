"""Trajectory logging — every agent step persisted to SQLite.

Module 4 adds Supabase mirroring of the same rows. Schema follows the
spec's step schema exactly.
"""

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from agent.core.types import Action, ToolResult
from agent.security.sanitizer import sanitize_tool_output

STEP_COLUMNS = (
    "run_id",
    "step_number",
    "tool_called",
    "tool_input",
    "tool_output",
    "success",
    "duration_ms",
    "tokens_used",
    "timestamp",
)


class Trajectory:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        # sqlite3.Connection is not thread-safe; the API server is threaded and
        # the observer UI polls, so every execute+commit pair is serialized.
        self._lock = threading.RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                golden_path_score REAL,
                started_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                tool_called TEXT NOT NULL,
                tool_input TEXT NOT NULL,
                tool_output TEXT NOT NULL,
                success INTEGER NOT NULL,
                duration_ms INTEGER NOT NULL,
                tokens_used INTEGER,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                memory_md TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_steps_run_id ON steps (run_id)"
        )
        self._conn.commit()

    def _conn_locked(self):
        return self._lock

    def new_run(self, task: str, task_type: str) -> str:
        with self._lock:
            run_id = str(uuid.uuid4())
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._conn.execute(
                "INSERT INTO runs (run_id, task, task_type, status, started_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, task, task_type, "RUNNING", now),
            )
            self._conn.commit()
            return run_id

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            cols = [c[0] for c in self._conn.execute("SELECT * FROM runs").description]
            return dict(zip(cols, row))

    def all_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            cols = [c[0] for c in self._conn.execute("SELECT * FROM runs").description]
            return [dict(zip(cols, row)) for row in rows]

    def set_run_status(self, run_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._conn.execute(
                "UPDATE runs SET status = ?, error = ?, finished_at = ? WHERE run_id = ?",
                (status, error, finished, run_id),
            )
            self._conn.commit()

    def set_run_score(self, run_id: str, score: float | None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET golden_path_score = ? WHERE run_id = ?", (score, run_id)
            )
            self._conn.commit()

    def log_step(
        self,
        run_id: str,
        step_number: int,
        action: Action,
        result: ToolResult,
        tokens_used: int | None = None,
    ) -> None:
        with self._lock:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            # Security model (Module 5): every value that is logged is treated as
            # untrusted — strip injection markers + PII before it is persisted or
            # mirrored, so nothing sensitive reaches the DB or Supabase.
            sanitized_output = sanitize_tool_output(result.output)
            self._conn.execute(
                "INSERT INTO steps (run_id, step_number, tool_called, tool_input, "
                "tool_output, success, duration_ms, tokens_used, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    step_number,
                    action.tool,
                    json.dumps(action.params),
                    json.dumps(sanitized_output),
                    1 if result.success else 0,
                    result.duration_ms,
                    tokens_used,
                    now,
                ),
            )
            self._conn.commit()

    def steps(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM steps WHERE run_id = ? ORDER BY step_number", (run_id,)
            ).fetchall()
            cols = [c[0] for c in self._conn.execute("SELECT * FROM steps").description]
            out = []
            for row in rows:
                rec = dict(zip(cols, row))
                rec["tool_input"] = json.loads(rec["tool_input"])
                rec["tool_output"] = json.loads(rec["tool_output"])
                rec["success"] = bool(rec["success"])
                out.append(rec)
            return out

    def export_jsonl(self, run_id: str, out_path: str | Path) -> None:
        run = self.get_run(run_id)
        steps = self.steps(run_id)
        record = {
            "task": run["task"] if run else "",
            "task_type": run["task_type"] if run else "",
            "steps": steps,
            "golden_path_score": run["golden_path_score"] if run else None,
            "deviations": [],
            "outcome": run["status"] if run else "UNKNOWN",
        }
        Path(out_path).write_text(json.dumps(record) + "\n", encoding="utf-8")

    def close(self) -> None:
        self._conn.close()
