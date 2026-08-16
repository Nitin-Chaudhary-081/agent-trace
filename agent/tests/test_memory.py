"""Tests for MEMORY.md read/write, session discovery, and persistence."""

import uuid

import pytest

from agent.core.memory import Memory, MemoryError, MemoryFile


def test_read_empty_memory_returns_defaults(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")

    data = memory.read()

    assert data["GOAL"] == ""
    assert data["STATUS"] == "PENDING"


def test_write_then_read_roundtrip(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="Research X", STATUS="RUNNING", SESSION_ID="abc")

    data = memory.read()

    assert data["GOAL"] == "Research X"
    assert data["STATUS"] == "RUNNING"
    assert data["SESSION_ID"] == "abc"


def test_survives_process_restart(tmp_path):
    path = tmp_path / "MEMORY.md"
    first = MemoryFile(path)
    first.write(GOAL="Persistent goal", STATUS="RUNNING", SESSION_ID="s1")

    second = MemoryFile(path)
    data = second.read()

    assert data["GOAL"] == "Persistent goal"
    assert data["STATUS"] == "RUNNING"
    assert data["SESSION_ID"] == "s1"


def test_session_id_generated_when_missing(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")

    sid = memory.read()["SESSION_ID"]

    assert len(sid) > 0
    uuid.UUID(sid)


def test_session_discovery_finds_incomplete(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="X", STATUS="RUNNING", SESSION_ID="s1")

    assert memory.has_incomplete_session() is True


def test_session_discovery_none_when_completed(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="X", STATUS="COMPLETED", SESSION_ID="s1")

    assert memory.has_incomplete_session() is False


def test_memory_update_appends_progress(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="X", STATUS="RUNNING", SESSION_ID="s1")
    memory.append_completed_step("web_search")

    data = memory.read()

    assert "web_search" in data["COMPLETED_STEPS"]


def test_write_rejects_empty_file_path(tmp_path):
    with pytest.raises(MemoryError):
        MemoryFile(tmp_path / "")


def test_memory_facade_in_memory(tmp_path):
    mem = Memory()
    mem.set("GOAL", "hello")

    assert mem.get("GOAL") == "hello"
