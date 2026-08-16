"""Tests for Module 4 rubric definitions and deviation reporting."""

import pytest

from agent.evaluator.golden_path import GoldenPathEvaluator
from agent.evaluator.rubrics import (
    RUBRICS,
    Deviation,
    expected_for,
    task_type_for_goal,
)


def test_three_task_type_rubrics_defined():
    assert set(RUBRICS) == {
        "research_and_email",
        "inbox_summarize",
        "data_lookup_report",
    }


def test_research_and_email_sequence():
    assert RUBRICS["research_and_email"] == [
        "web_search",
        "supabase_insert",
        "gmail_send",
    ]


def test_inbox_summarize_sequence():
    assert RUBRICS["inbox_summarize"] == [
        "gmail_list_inbox",
        "gmail_read_email",
        "supabase_insert",
    ]


def test_data_lookup_report_sequence():
    assert RUBRICS["data_lookup_report"] == [
        "supabase_select",
        "gmail_send",
    ]


def test_expected_for_known_type():
    assert expected_for("data_lookup_report") == RUBRICS["data_lookup_report"]


def test_expected_for_unknown_type_is_none():
    assert expected_for("unknown_type") is None


def test_task_type_for_goal_keywords():
    assert task_type_for_goal("research X and email") == "research_and_email"
    assert task_type_for_goal("summarize my inbox") == "inbox_summarize"
    assert task_type_for_goal("lookup records from table") == "data_lookup_report"
    assert task_type_for_goal("something else entirely") is None


def test_perfect_run_scores_full_marks():
    ev = GoldenPathEvaluator()
    steps = [
        {"tool_called": "web_search"},
        {"tool_called": "supabase_insert"},
        {"tool_called": "gmail_send"},
    ]
    result = ev.score_run("", steps, task_type="research_and_email")
    assert result["score"] == 100.0
    assert result["matched_steps"] == 3
    assert result["deviations"] == []


def test_missing_step_deviation():
    ev = GoldenPathEvaluator()
    steps = [
        {"tool_called": "web_search"},
        {"tool_called": "supabase_insert"},
    ]
    result = ev.score_run("", steps, task_type="research_and_email")
    assert any(d.kind == "missing_step" for d in result["deviations"])
    assert result["score"] < 100.0


def test_wrong_order_deviation():
    ev = GoldenPathEvaluator()
    steps = [
        {"tool_called": "gmail_send"},
        {"tool_called": "web_search"},
        {"tool_called": "supabase_insert"},
    ]
    result = ev.score_run("", steps, task_type="research_and_email")
    assert any(d.kind == "wrong_order" for d in result["deviations"])


def test_extra_step_deviation():
    ev = GoldenPathEvaluator()
    steps = [
        {"tool_called": "web_search"},
        {"tool_called": "supabase_insert"},
        {"tool_called": "gmail_send"},
        {"tool_called": "supabase_delete"},  # not part of golden path
    ]
    result = ev.score_run("", steps, task_type="research_and_email")
    assert any(d.kind == "extra_step" for d in result["deviations"])


def test_retry_deviation():
    ev = GoldenPathEvaluator()
    steps = [
        {"tool_called": "supabase_select"},
        {"tool_called": "supabase_select"},  # retried
        {"tool_called": "gmail_send"},
    ]
    result = ev.score_run("", steps, task_type="data_lookup_report")
    assert any(d.kind == "retry" for d in result["deviations"])


def test_score_capped_at_100():
    ev = GoldenPathEvaluator()
    steps = [
        {"tool_called": "web_search"},
        {"tool_called": "supabase_insert"},
        {"tool_called": "gmail_send"},
    ]
    result = ev.score_run("", steps, task_type="research_and_email")
    assert result["score"] <= 100.0


def test_deviation_fields():
    ev = GoldenPathEvaluator()
    steps = [{"tool_called": "web_search"}]
    result = ev.score_run("", steps, task_type="research_and_email")
    assert result["deviations"]
    d = result["deviations"][0]
    assert isinstance(d, Deviation)
    assert d.severity in ("info", "warning", "critical")