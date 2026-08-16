"""LogicProcessor — keyword-based reasoning stub.

Module 1 ships a deterministic stub that maps task keywords to a typed
action sequence. The real LLM-backed reasoning slot stays behind the same
`decide()` interface (Module 3+).

Interface:
    plan_for_task(task) -> list[Action]
    decide(memory, observations) -> Action | None
    describe_plan(task_type) -> str
"""

from agent.core.memory import MemoryFile
from agent.core.types import Action
import os

DEFAULT_FALLBACK_STEPS = ("web_search", "supabase_select", "gmail_send")


class LogicProcessor:
    def __init__(self, max_steps: int = 5):
        self.max_steps = max_steps

    def plan_for_task(self, task: str) -> list[Action]:
        if not task or not task.strip():
            return []

        lower = task.lower()

        if "research" in lower or "search" in lower or "web" in lower:
            return [
                Action("web_search", {"query": task}),
                Action("supabase_insert", {"table": "public_data"}),
                Action("gmail_send", {"to": os.environ.get("GMAIL_TEST_TO", "self"), "subject": "Research summary", "body": "See attached research notes."}),
            ]

        if "inbox" in lower or "summarize" in lower or "email" in lower:
            return [
                Action("gmail_list_inbox", {"unread_only": True, "limit": 10}),
                Action("gmail_read_email", {}),
                Action("supabase_insert", {"table": "public_data"}),
            ]

        if "query" in lower or "table" in lower or "lookup" in lower:
            return [
                Action("supabase_select", {"table": "public_data", "limit": 50}),
                Action("gmail_send", {"to": os.environ.get("GMAIL_TEST_TO", "self"), "subject": "Data report", "body": "See attached data report."}),
            ]

        # Unknown task type: bounded fallback loop so the runner exercises
        # max_steps handling deterministically.
        fallback = [Action(tool, {}) for tool in DEFAULT_FALLBACK_STEPS]
        return (fallback * ((self.max_steps // len(fallback)) + 1))[: self.max_steps]

    def decide(self, memory: MemoryFile, observations: dict) -> Action | None:
        data = memory.read() if isinstance(memory, MemoryFile) else memory
        goal = data.get("GOAL", "")
        plan = self.plan_for_task(goal)
        if not plan:
            return None

        completed = [line for line in data.get("COMPLETED_STEPS", "").splitlines() if line]
        index = len(completed)
        if index >= len(plan):
            return None
        return plan[index]

    def describe_plan(self, task_type: str) -> str:
        sample = "research a topic"
        if task_type == "inbox_summarize":
            sample = "summarize my inbox"
        elif task_type == "data_lookup_report":
            sample = "query table and report"
        tools = ", ".join(a.tool for a in self.plan_for_task(sample))
        return f"task_type={task_type or 'unknown'}: {tools}"
