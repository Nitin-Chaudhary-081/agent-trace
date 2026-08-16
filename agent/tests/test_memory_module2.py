"""Tests for Module 2 memory: summarization, session discovery, resume."""

import pytest

from agent.core.memory import MemoryError, MemoryFile

T = 4000


def _write_big_progress(memory: MemoryFile, entries: int = 200) -> None:
    memory.write(GOAL="big goal", STATUS="RUNNING", SESSION_ID="s1")
    for i in range(entries):
        memory.append_progress(f"step-{i}: " + "x" * 30)


def test_append_progress_grows(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.append_progress("first")
    memory.append_progress("second")

    data = memory.read()

    assert "first" in data["PROGRESS"]
    assert "second" in data["PROGRESS"]


def test_append_progress_beyond_4000_truncates(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    _write_big_progress(memory)

    data = memory.read()

    assert len(data["PROGRESS"]) <= T
    # oldest entries dropped
    assert "step-0:" not in data["PROGRESS"]
    # newest entries retained
    assert "step-199:" in data["PROGRESS"]


def test_summarized_memory_stays_readable(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    _write_big_progress(memory)

    data = memory.read()

    assert data["GOAL"] == "big goal"
    assert data["STATUS"] == "RUNNING"


def test_start_fresh_writes_new_session(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")

    state = memory.start_or_resume()

    assert state["mode"] == "fresh"
    assert len(state["session_id"]) > 0
    assert memory.read()["SESSION_ID"] == state["session_id"]


def test_resume_finds_incomplete_session(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="resume me", STATUS="RUNNING", SESSION_ID="s1")
    memory.append_completed_step("web_search")

    state = memory.start_or_resume()

    assert state["mode"] == "resumed"
    assert state["session_id"] == "s1"
    assert state["goal"] == "resume me"
    assert state["completed_steps"] == ["web_search"]


def test_resume_ignores_completed_session(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="done", STATUS="COMPLETED", SESSION_ID="s1")

    state = memory.start_or_resume()

    assert state["mode"] == "fresh"
    assert state["session_id"] != "s1"
