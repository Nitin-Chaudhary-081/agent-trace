"""API test configuration — in-memory SQLite, isolated tmp dirs per test."""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "api", ROOT / "api" / "src", ROOT / "agent"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("AGENTTRACE_DB_PATH", ":memory:")


@pytest.fixture()
def client(tmp_path):
    from src.app import create_app

    os.environ["AGENTTRACE_DB_PATH"] = str(tmp_path / "test.sqlite")
    os.environ["AGENTTRACE_MEMORY_PATH"] = str(tmp_path / "MEMORY.md")

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client
