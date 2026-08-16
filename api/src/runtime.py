"""Runtime manager — builds an agent runtime bound to the current settings.

A runtime holds the tool registry, trajectory store, memory file, and
agent runner. It is created per-app so tests get isolated instances.
"""

import os

from agent.core.memory import MemoryFile
from agent.core.runner import AgentRunner
from agent.core.tool_registry import ToolRegistry
from agent.core.trajectory import Trajectory
from agent.services.logic_processor import LogicProcessor
from agent.services.trajectory_mirror import TrajectoryMirror
from agent.tools import register_live_tools


class AgentRuntime:
    def __init__(self, database_path: str, memory_path: str, max_steps: int, tool_timeout_s: int):
        self.registry = ToolRegistry(timeout_s=tool_timeout_s)
        register_live_tools(
            self.registry,
            supabase_url=os.environ.get("SUPABASE_URL", ""),
            supabase_key=os.environ.get("SUPABASE_SERVICE_KEY", ""),
            supabase_tables=tuple(
                t.strip()
                for t in os.environ.get("SUPABASE_ALLOWED_TABLES", "").split(",")
                if t.strip()
            ),
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
            url=os.environ.get("SUPABASE_URL", ""),
            service_key=os.environ.get("SUPABASE_SERVICE_KEY", ""),
        )
        self.runner = AgentRunner(
            registry=self.registry,
            memory=self.memory,
            trajectory=self.trajectory,
            processor=self.processor,
            max_steps=max_steps,
        )

    def submit(self, task: str, task_type: str) -> str:
        run_id = self.runner.run(task, task_type)
        self.mirror.sync_run(run_id)
        return run_id
