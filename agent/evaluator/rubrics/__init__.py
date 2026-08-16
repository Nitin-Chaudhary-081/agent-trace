"""Per-task-type golden path rubrics (Module 4).

Each rubric lists the expected tool sequence for the task type. Scoring
formula (per spec):
    step_score = (matched_steps / expected_steps) * 100
    order_bonus = 10 if steps in correct order else 0
    final_score = min(step_score + order_bonus, 100)

Deviations are flagged as typed records: missing_step, wrong_order,
extra_step, retry.
"""

from dataclasses import dataclass
from typing import Any

RUBRICS: dict[str, list[str]] = {
    "research_and_email": ["web_search", "supabase_insert", "gmail_send"],
    "inbox_summarize": ["gmail_list_inbox", "gmail_read_email", "supabase_insert"],
    "data_lookup_report": ["supabase_select", "gmail_send"],
}

_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("research_and_email", ("research", "search", "web", "store in")),
    ("inbox_summarize", ("inbox", "summarize", "email", "unread")),
    ("data_lookup_report", ("query", "table", "lookup", "records", "report")),
]


@dataclass(frozen=True)
class Deviation:
    """A typed deviation from the golden path."""

    kind: str  # missing_step | wrong_order | extra_step | retry
    tool: str
    detail: str
    severity: str  # info | warning | critical


def expected_for(task_type: str) -> list[str] | None:
    return RUBRICS.get(task_type)


def task_type_for_goal(goal: str) -> str | None:
    lower = (goal or "").lower()
    for task_type, keywords in _KEYWORDS:
        if any(k in lower for k in keywords):
            return task_type
    return None


def score_matches(
    expected: list[str], actual: list[str]
) -> tuple[list[str], list[str]]:
    """Subsequence match. Returns (matched_expected, actual_used)."""
    matched: list[str] = []
    cursor = 0
    for tool in expected:
        for i in range(cursor, len(actual)):
            if actual[i] == tool:
                matched.append(tool)
                cursor = i + 1
                break
    return matched, [t for t in expected if t in matched]


def in_order(expected: list[str], actual: list[str]) -> bool:
    cursor = 0
    for tool in expected:
        found = False
        while cursor < len(actual):
            if actual[cursor] == tool:
                cursor += 1
                found = True
                break
            cursor += 1
        if not found:
            return False
    return True


def detect_deviations(expected: list[str], actual: list[str]) -> list[Deviation]:
    """Flags missing, wrong-order, extra, and retry steps against the rubric."""
    deviations: list[Deviation] = []
    matched = score_matches(expected, actual)[0]

    for tool in expected:
        if tool not in matched:
            deviations.append(
                Deviation(
                    kind="missing_step",
                    tool=tool,
                    detail=f"expected {tool} but never called",
                    severity="critical" if tool in ("gmail_send", "supabase_insert") else "warning",
                )
            )

    for tool in actual:
        if tool not in expected:
            deviations.append(
                Deviation(
                    kind="extra_step",
                    tool=tool,
                    detail=f"{tool} called but not in golden path",
                    severity="warning",
                )
            )

    if matched and len(matched) == len(set(matched)) and len(matched) > 1 and not in_order(expected, actual):
        deviations.append(
            Deviation(
                kind="wrong_order",
                tool=",".join(matched),
                detail="tools executed out of golden path order",
                severity="warning",
            )
        )

    expected_counts: dict[str, int] = {}
    for t in expected:
        expected_counts[t] = expected_counts.get(t, 0) + 1
    for t, count in _counts(actual).items():
        if count > expected_counts.get(t, 0):
            deviations.append(
                Deviation(
                    kind="retry",
                    tool=t,
                    detail=f"{t} called {count}x but rubric expects {expected_counts.get(t, 0)}x",
                    severity="warning",
                )
            )
    return deviations


def _counts(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def score_run_data(expected: list[str], actual: list[str]) -> dict[str, Any]:
    """Full scoring result for a task-type rubric."""
    if not expected:
        return {
            "score": None,
            "matched_steps": 0,
            "expected_steps": 0,
            "order_bonus": 0,
            "deviations": [],
        }
    matched, _ = score_matches(expected, actual)
    step_score = (len(matched) / len(expected)) * 100
    order_bonus = 10 if in_order(expected, actual) else 0
    score = min(step_score + order_bonus, 100.0)
    return {
        "score": score,
        "matched_steps": len(matched),
        "expected_steps": len(expected),
        "order_bonus": order_bonus,
        "deviations": detect_deviations(expected, actual),
    }