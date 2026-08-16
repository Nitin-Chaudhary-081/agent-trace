"""Tests for the logic processor keyword stub."""

from agent.core.memory import MemoryFile
from agent.services.logic_processor import LogicProcessor


def test_plan_research_and_email():
    processor = LogicProcessor()

    plan = processor.plan_for_task("research Python best practices")

    tools = [a.tool for a in plan]
    assert tools[0] == "web_search"


def test_plan_inbox_summarize():
    processor = LogicProcessor()

    plan = processor.plan_for_task("summarize my inbox")

    assert plan[0].tool == "gmail_list_inbox"


def test_plan_data_lookup():
    processor = LogicProcessor()

    plan = processor.plan_for_task("query table and report")

    assert plan[0].tool == "supabase_select"


def test_decide_returns_none_when_plan_done(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    processor = LogicProcessor()

    next_action = processor.decide(memory, {})

    assert next_action is None


def test_decide_returns_first_action_for_new_memory(tmp_path):
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="research Python best practices", STATUS="RUNNING")
    processor = LogicProcessor()

    action = processor.decide(memory, {})

    assert action is not None
    assert action.tool == "web_search"
