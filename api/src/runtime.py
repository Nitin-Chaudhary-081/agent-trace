"""Runtime manager — builds an agent runtime bound to the current settings.

A runtime holds the tool registry, trajectory store, memory file, and
agent runner. It is created per-app so tests get isolated instances.
"""

import logging
import os
import threading

from agent.core.memory import MemoryFile
from agent.core.runner import AgentRunner
from agent.core.tool_registry import ToolRegistry
from agent.core.trajectory import Trajectory
from agent.services.logic_processor import LogicProcessor
from agent.services.snapshotter import MemorySnapshotter
from agent.services.trajectory_mirror import TrajectoryMirror
from agent.tools import register_live_tools

logger = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(self, database_path: str, memory_path: str, max_steps: int, tool_timeout_s: int):
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        allowed_tables = tuple(
            t.strip()
            for t in os.environ.get("SUPABASE_ALLOWED_TABLES", "").split(",")
            if t.strip()
        )
        if supabase_url and supabase_key and not allowed_tables:
            logger.warning(
                "Supabase creds configured but SUPABASE_ALLOWED_TABLES is empty; "
                "table whitelist is disabled (any table reachable by the service key)."
            )

        self.registry = ToolRegistry(timeout_s=tool_timeout_s)
        register_live_tools(
            self.registry,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            supabase_tables=allowed_tables,
            gmail_client_id=os.environ.get("GMAIL_CLIENT_ID", ""),
            gmail_client_secret=os.environ.get("GMAIL_CLIENT_SECRET", ""),
            gmail_refresh_token=os.environ.get("GMAIL_REFRESH_TOKEN", ""),
            timeout_s=float(tool_timeout_s),
        )
        self.trajectory = Trajectory(database_path)
        self.memory = MemoryFile(memory_path)
        self.processor = LogicProcessor(max_steps=max_steps)
        self.mirror = TrajectoryMirror(
            trajectory=self.trajectory,
            url=supabase_url,
            service_key=supabase_key,
        )
        snapshot_dir = os.environ.get(
            "AGENTTRACE_SNAPSHOT_DIR", os.path.join(os.path.dirname(database_path), ".snapshots")
        )
        self.runner = AgentRunner(
            registry=self.registry,
            memory=self.memory,
            trajectory=self.trajectory,
            processor=self.processor,
            snapshotter=MemorySnapshotter(
                local_dir=snapshot_dir,
                supabase_url=supabase_url,
                supabase_key=supabase_key,
            ),
            max_steps=max_steps,
        )

    def submit(self, task: str, task_type: str) -> str:
        """Submit a task and return immediately (202 accepted).

        The run record is created synchronously so the observer can poll
        immediately; the agent loop executes in a background thread.
        """
        run_id = self.runner.start_run(task, task_type)
        thread = threading.Thread(
            target=self._execute_background,
            args=(run_id, task, task_type),
            daemon=True,
        )
        thread.start()
        return run_id

    def _execute_background(self, run_id: str, task: str, task_type: str) -> None:
        try:
            self.runner.execute(run_id, task, task_type)
        finally:
            try:
                self.mirror.sync_run(run_id)
            except Exception as exc:  # noqa: BLE001 - mirror must not break the API
                logger.warning("mirror sync failed for run %s: %s", run_id, exc)
