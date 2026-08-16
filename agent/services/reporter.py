"""Reporter — trajectory export and scoring summary.

Module 4: export records are enriched with golden-path deviations, and the
JSONL format matches the AI training-data schema:
{tasks, steps, golden_path_score, deviations, outcome}.
"""

import json
from pathlib import Path
from typing import Any

from agent.core.trajectory import Trajectory
from agent.evaluator.golden_path import GoldenPathEvaluator


class Reporter:
    def __init__(self, trajectory: Trajectory, evaluator: GoldenPathEvaluator | None = None):
        self.trajectory = trajectory
        self.evaluator = evaluator or GoldenPathEvaluator()

    def deviations_for(self, run_id: str) -> list[dict[str, Any]]:
        run = self.trajectory.get_run(run_id)
        steps = self.trajectory.steps(run_id)
        if run is None:
            return []
        scoring = self.evaluator.score_run(
            {"GOAL": run["task"]},
            steps,
            task_type=run["task_type"],
        )
        return [d.__dict__ if hasattr(d, "__dict__") else dict(d) for d in scoring["deviations"]]

    def summarize_run(self, run_id: str) -> dict[str, Any]:
        run = self.trajectory.get_run(run_id)
        steps = self.trajectory.steps(run_id)
        if run is None:
            return {"run_id": run_id, "found": False}

        return {
            "run_id": run_id,
            "found": True,
            "task": run["task"],
            "task_type": run["task_type"],
            "status": run["status"],
            "steps_taken": len(steps),
            "golden_path_score": run["golden_path_score"],
            "error": run["error"],
            "deviations": self.deviations_for(run_id),
        }

    def export_record(self, run_id: str) -> str:
        run = self.trajectory.get_run(run_id)
        steps = self.trajectory.steps(run_id)
        record = {
            "task": run["task"],
            "task_type": run["task_type"],
            "steps": steps,
            "golden_path_score": run["golden_path_score"],
            "deviations": self.deviations_for(run_id),
            "outcome": run["status"],
        }
        return json.dumps(record)

    def export_jsonl(self, run_id: str, out_path: str) -> None:
        run = self.trajectory.get_run(run_id)
        steps = self.trajectory.steps(run_id)
        record = {
            "task": run["task"],
            "task_type": run["task_type"],
            "steps": steps,
            "golden_path_score": run["golden_path_score"],
            "deviations": self.deviations_for(run_id),
            "outcome": run["status"],
        }
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")