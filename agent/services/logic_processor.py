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
from agent.security.sanitizer import sanitize_tool_output
import os

DEFAULT_FALLBACK_STEPS = ("web_search", "supabase_select", "gmail_send")

MAX_NOTE_CHARS = 2000


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
        return self._build_action(goal, plan, index, observations)

    def _build_action(
        self,
        goal: str,
        plan: list[Action],
        index: int,
        observations: dict,
    ) -> Action | None:
        """Resolve the action at `index`, threading the previous tool's output
        into the payload so data actually flows between steps.

        - supabase_insert carries a `data=[{"note": ...}]` payload (the
          observed content, or the goal as a fallback) so rows land in the
          table instead of an empty array insert.
        - gmail_read_email passes the message_id observed from list_inbox.
        - gmail_send only fires when the preceding data step actually stored
          or returned rows; otherwise it is gated (returns None) so no empty
          "see attached" emails are sent.
        """
        action = plan[index]
        tool = action.tool
        kind = self._plan_kind(goal)

        # Fallback loop (unknown task types): keep static actions so the
        # runner exercises max_steps handling deterministically.
        if kind == "fallback":
            return action

        if tool == "supabase_insert":
            note = sanitize_tool_output(self._content_from(observations)) or goal
            return Action(
                tool,
                {"table": "public_data", "data": [{"note": self._clip(note)}]},
            )

        if tool == "gmail_read_email":
            messages = (observations or {}).get("messages") or []
            message_id = messages[0].get("id") if messages else None
            if not message_id:
                return None
            return Action(tool, {"message_id": message_id})

        if tool == "gmail_send":
            if not self._has_stored_rows(observations):
                return None
            subject, body = self._email_for(tool, goal, observations)
            return Action(
                tool,
                {
                    "to": os.environ.get("GMAIL_TEST_TO", "self"),
                    "subject": subject,
                    "body": body,
                },
            )

        return action

    @staticmethod
    def _has_stored_rows(observations: dict) -> bool:
        """True when the preceding data step stored/returned content.

        An empty observations dict (data step skipped as not_configured, or
        not yet run) does not gate the send — in the offline path the email
        step will also degrade to a harmless skip. Only a real result that
        carried no rows (empty `data` / `rows_affected` == 0) gates.
        """
        if not isinstance(observations, dict):
            return False
        if "data" not in observations and "rows_affected" not in observations:
            return True
        rows = observations.get("data") or []
        rows_affected = observations.get("rows_affected", 0)
        return bool(rows) or int(rows_affected or 0) > 0

    @staticmethod
    def _content_from(observations: dict) -> str:
        if not isinstance(observations, dict):
            return ""
        if observations.get("content"):
            return str(observations["content"])
        rows = observations.get("data") or []
        if rows and isinstance(rows[0], dict) and rows[0].get("note"):
            return str(rows[0]["note"])
        messages = observations.get("messages") or []
        if messages and isinstance(messages[0], dict):
            msg = messages[0]
            subject = msg.get("subject") or ""
            snippet = msg.get("snippet") or ""
            return f"{subject}: {snippet}" if subject else snippet
        return ""

    @staticmethod
    def _clip(text: str) -> str:
        return text[:MAX_NOTE_CHARS]

    @staticmethod
    def _plan_kind(goal: str) -> str:
        lower = goal.lower()
        if "research" in lower or "search" in lower or "web" in lower:
            return "research"
        if "inbox" in lower or "summarize" in lower or "email" in lower:
            return "inbox"
        if "query" in lower or "table" in lower or "lookup" in lower:
            return "lookup"
        return "fallback"

    def _email_for(
        self, tool: str, goal: str, observations: dict
    ) -> tuple[str, str]:
        content = sanitize_tool_output(self._content_from(observations))
        if self._plan_kind(goal) == "research":
            subject = "Research summary"
            body = (
                f"Stored research notes for: {goal}\n\n"
                f"{content or 'No content available.'}"
            )
        else:
            subject = "Data report"
            body = (
                f"Here is the stored data for: {goal}\n\n"
                f"{content or 'No content available.'}"
            )
        return subject, body

    def describe_plan(self, task_type: str) -> str:
        sample = "research a topic"
        if task_type == "inbox_summarize":
            sample = "summarize my inbox"
        elif task_type == "data_lookup_report":
            sample = "query table and report"
        tools = ", ".join(a.tool for a in self.plan_for_task(sample))
        return f"task_type={task_type or 'unknown'}: {tools}"
