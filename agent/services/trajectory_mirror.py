"""TrajectoryMirror — mirrors runs + steps to the Supabase agent_runs table.

PostgREST REST client via pure-Python requests, matching the house pattern
(ADR-006). When SUPABASE_URL/KEY are absent the mirror is inactive and
sync_run is a no-op (typed, never raises). The mirror performs zero mocks —
transport fakes are injected only in offline tests.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import requests

from agent.core.trajectory import Trajectory

RUNS_TABLE = "agent_runs"
DEFAULT_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class TrajectoryMirror:
    trajectory: Trajectory
    url: str = ""
    service_key: str = ""
    timeout_s: float = DEFAULT_TIMEOUT_S
    session: Any = field(default=None, repr=False)

    def is_active(self) -> bool:
        return bool(self.url and self.service_key)

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict:
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        with ThreadPoolExecutor(max_workers=1) as pool:
            session = self.session or requests.Session()
            future = pool.submit(
                session.request,
                method,
                f"{self.url.rstrip('/')}{path}",
                json=payload,
                headers=headers,
                timeout=self.timeout_s,
            )
            try:
                resp = future.result(timeout=self.timeout_s)
            except TimeoutError:
                return {"error": "timeout"}
            except requests.RequestException as exc:
                return {"error": f"request_failed: {exc.__class__.__name__}"}
        if resp.status_code >= 400:
            return {"error": f"api_error: {resp.status_code} {resp.text[:200]}"}
        return {"ok": True}

    def sync_run(self, run_id: str) -> dict[str, Any]:
        """Push a run record + all its steps to agent_runs (one POST each)."""
        if not self.is_active():
            return {"error": "not_configured"}
        run = self.trajectory.get_run(run_id)
        if run is None:
            return {"error": "run_not_found"}

        run_payload = {
            "run_id": run["run_id"],
            "task": run["task"],
            "task_type": run["task_type"],
            "status": run["status"],
            "error": run["error"],
            "golden_path_score": run["golden_path_score"],
            "started_at": run["started_at"],
            "finished_at": run["finished_at"],
        }
        run_result = self._request("POST", f"/rest/v1/{RUNS_TABLE}", run_payload)
        if "error" in run_result:
            return run_result

        for step in self.trajectory.steps(run_id):
            step_payload = {
                "run_id": run_id,
                "step_number": step["step_number"],
                "tool_called": step["tool_called"],
                "tool_input": step["tool_input"],
                "tool_output": step["tool_output"],
                "success": step["success"],
                "duration_ms": step["duration_ms"],
                "tokens_used": step["tokens_used"],
                "timestamp": step["timestamp"],
            }
            res = self._request("POST", f"/rest/v1/{RUNS_TABLE}", step_payload)
            if "error" in res:
                return res
        return {"ok": True, "steps": len(self.trajectory.steps(run_id))}