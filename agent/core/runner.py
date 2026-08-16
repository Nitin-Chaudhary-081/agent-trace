"""AgentRunner — main execution loop.

    while steps < max_steps:
        action = logic_processor.decide(memory, observations)
        result = tool_registry.execute(action)
        trajectory.log(action, result)
        memory.update(result)
        if evaluator.is_complete(memory): break

Defaults: 20 max steps, 60s per tool call (enforced by ToolRegistry).
Module 2: resume() restarts an incomplete session from COMPLETED_STEPS;
snapshotter is called every 5 steps.
"""

import time
from typing import Any

from agent.core.memory import MemoryFile
from agent.core.tool_registry import ToolRegistry
from agent.core.trajectory import Trajectory
from agent.core.types import Action, ToolResult
from agent.evaluator.golden_path import GoldenPathEvaluator
from agent.services.logic_processor import LogicProcessor
from agent.services.snapshotter import MemorySnapshotter

DEFAULT_MAX_STEPS = 20
SNAPSHOT_EVERY_N_STEPS = 5


class AgentRunner:
    def __init__(
        self,
        registry: ToolRegistry,
        memory: MemoryFile,
        trajectory: Trajectory,
        processor: LogicProcessor,
        evaluator: GoldenPathEvaluator | None = None,
        snapshotter: MemorySnapshotter | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
    ):
        self.registry = registry
        self.memory = memory
        self.trajectory = trajectory
        self.processor = processor
        self.evaluator = evaluator or GoldenPathEvaluator()
        self.snapshotter = snapshotter
        self.max_steps = max_steps

    def run(self, task: str, task_type: str) -> str:
        run_id = self.trajectory.new_run(task, task_type)
        self.memory.write(
            GOAL=task,
            STATUS="RUNNING",
            PROGRESS=f"Started run {run_id}",
            COMPLETED_STEPS="",
            NEXT_ACTIONS=self.processor.describe_plan(task_type),
            FAILURES="",
        )

        try:
            self._run_loop(run_id, task, task_type)
        except Exception as exc:  # noqa: BLE001 - normalized into typed run error
            self.trajectory.set_run_status(run_id, "FAILED", error=str(exc))
            self.memory.write(STATUS="FAILED", FAILURES=f"runner_error: {exc}")
        return run_id

    def resume(self) -> dict[str, str]:
        """Session discovery on process restart.

        If MEMORY.md holds an incomplete session (PENDING/RUNNING + GOAL),
        continue the plan from COMPLETED_STEPS; otherwise report nothing to
        resume. Returns the new run metadata.
        """
        state = self.memory.start_or_resume()
        if state["mode"] == "fresh":
            return {"mode": "nothing_to_resume", "status": "COMPLETED"}

        goal = state["goal"]
        run_id = self.trajectory.new_run(goal, "resumed")
        self.memory.write(
            STATUS="RUNNING",
            PROGRESS=f"Resumed run {run_id}",
            NEXT_ACTIONS="",
            FAILURES="",
        )

        try:
            self._run_loop(run_id, goal, "resumed")
        except Exception as exc:  # noqa: BLE001 - normalized into typed run error
            self.trajectory.set_run_status(run_id, "FAILED", error=str(exc))
            self.memory.write(STATUS="FAILED", FAILURES=f"runner_error: {exc}")

        run = self.trajectory.get_run(run_id)
        return {"mode": "resumed", "status": run["status"], "run_id": run_id}

    def _run_loop(self, run_id: str, task: str, task_type: str) -> None:
        for step_number in range(1, self.max_steps + 1):
            action = self.processor.decide(self.memory.read(), {})
            if action is None:
                self._finish(run_id, "COMPLETED")
                return

            result = self._execute_and_log(run_id, step_number, action)
            self._update_memory(result)

            if not result.success:
                self._finish(run_id, "FAILED", error=result.error or "tool_failed")
                return
            if self.evaluator.is_complete(self.memory.read()):
                self._finish(run_id, "COMPLETED")
                return
            if step_number % SNAPSHOT_EVERY_N_STEPS == 0 and self.snapshotter:
                self.snapshotter.snapshot(run_id, self.memory.read())

        self._finish(run_id, "STOPPED_MAX_STEPS")

    def _execute_and_log(
        self, run_id: str, step_number: int, action: Action
    ) -> ToolResult:
        start = time.monotonic()
        result = self.registry.execute(action)
        elapsed_ms = result.duration_ms if result.duration_ms else int(
            (time.monotonic() - start) * 1000
        )
        result = ToolResult(
            success=result.success,
            output=result.output,
            error=result.error,
            duration_ms=elapsed_ms,
        )
        self.trajectory.log_step(
            run_id=run_id,
            step_number=step_number,
            action=action,
            result=result,
            tokens_used=None,
        )
        return result

    def _update_memory(self, result: ToolResult) -> None:
        if result.success:
            self.memory.append_completed_step(result.output.get("tool_name", "step"))
        else:
            self.memory.append_failure(result.error or "tool_failed")

    def _finish(
        self, run_id: str, status: str, error: str | None = None
    ) -> None:
        score = None
        if status == "COMPLETED":
            run = self.trajectory.get_run(run_id)
            task_type = run["task_type"] if run else None
            scoring = self.evaluator.score_run(
                self.memory.read(),
                self.trajectory.steps(run_id),
                task_type=task_type,
            )
            score = scoring.get("score")
        self.trajectory.set_run_score(run_id, score)
        self.trajectory.set_run_status(run_id, status, error=error)
        self.memory.write(STATUS=status)
