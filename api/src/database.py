"""SQLite database access (stdlib sqlite3, synchronous, aarch64-safe).

The trajectory/run tables live here for the API. The agent's Trajectory
class writes to the same file so the observer UI can poll live steps.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.config import settings


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = Path(db_path or settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    init_schema(conn)
    return conn


@contextmanager
def get_db(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.execute(
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
    conn.commit()


def run_exists(conn: sqlite3.Connection, run_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    return row is not None
