"""GoldenPathEvaluator — rubric-based scoring of an agent run.

Module 4: scoring uses the per-task-type rubrics (expected tool sequences)
plus deviation detection (missing_step, wrong_order, extra_step, retry).

Score formula (per spec):
    step_score = (matched_steps / expected_steps) * 100
    order_bonus = 10 if steps are in the correct order else 0
    final_score = min(step_score + order_bonus, 100)
"""

from typing import Any

from agent.evaluator.rubrics import (
    score_run_data,
    task_type_for_goal,
)
from agent.services.logic_processor import LogicProcessor


class GoldenPathEvaluator:
    def __init__(self, processor: LogicProcessor | None = None):
        self.processor = processor or LogicProcessor()

    def is_complete(self, memory: Any) -> bool:
        data = memory.read() if hasattr(memory, "read") else memory
        return data.get("STATUS") == "COMPLETED"

    def score_run(
        self,
        memory: Any,
        steps: list[dict[str, Any]],
        task_type: str | None = None,
    ) -> dict[str, Any]:
        """Score a run against its task-type rubric.

        Returns {score, matched_steps, expected_steps, order_bonus,
        deviations}. Falls back to keyword-derived task type when not given.
        """
        data = memory.read() if hasattr(memory, "read") else memory
        if not isinstance(data, dict):
            data = {"GOAL": ""}
        goal = data.get("GOAL", "")
        # The executed plan is keyword-derived from the goal, so scoring must
        # follow the goal-derived task type when the goal maps unambiguously;
        # otherwise a UI defaulting to another task_type would score a correct
        # run against the wrong rubric.
        ttype = task_type_for_goal(goal) or task_type
        if ttype is None:
            return {
                "score": None,
                "matched_steps": 0,
                "expected_steps": 0,
                "order_bonus": 0,
                "deviations": [],
            }
        from agent.evaluator.rubrics import expected_for

        expected = expected_for(ttype)
        actual = [s.get("tool_called") for s in steps]
        return score_run_data(expected, actual)

    def _in_order(self, expected: list[str], actual: list[str]) -> bool:
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