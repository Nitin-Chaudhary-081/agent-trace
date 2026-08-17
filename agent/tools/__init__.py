"""Live tool integrations (Module 3).

Module 1 provides the abstract base class only. The three live tools —
Supabase, Gmail, Web Search — are implemented in Module 3 and registered
into the ToolRegistry. Each tool must enforce typed input/output schemas,
a 60s timeout, and typed errors.

`register_live_tools` wires the six tool names the LogicProcessor emits
(web_search, supabase_insert, supabase_select, gmail_send,
gmail_list_inbox, gmail_read_email) to the underlying tool implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from agent.core.tool_registry import ToolRegistry
from agent.core.types import ToolResult


@dataclass(frozen=True)
class BaseTool(ABC):
    name: str

    @abstractmethod
    def invoke(self, **params: Any) -> ToolResult:
        """Execute the tool against a live API."""

    def timeout_s(self) -> int:
        return 60


def _wrap(tool: BaseTool, operation: str):
    def _handler(**params: Any) -> ToolResult:
        return tool.invoke(operation=operation, **params)

    _handler.__name__ = f"{tool.name}_{operation}"
    return _handler


def register_live_tools(
    registry: ToolRegistry,
    supabase_url: str = "",
    supabase_key: str = "",
    supabase_tables: tuple[str, ...] = (),
    gmail_client_id: str = "",
    gmail_client_secret: str = "",
    gmail_refresh_token: str = "",
    timeout_s: float = 60.0,
) -> None:
    """Registers the six live tool names against real APIs.

    Tools whose credentials are absent degrade to typed ToolResult failures
    (not_configured) instead of raising — the runner loop handles that as a
    failed step.
    """
    from agent.tools.supabase_tool import SupabaseTool
    from agent.tools.gmail_tool import GmailTool
    from agent.tools.websearch_tool import WebSearchTool

    web = WebSearchTool(timeout_s=timeout_s)
    registry.register("web_search", web.invoke)

    supabase = SupabaseTool(
        url=supabase_url,
        service_key=supabase_key,
        allowed_tables=tuple(supabase_tables),
        timeout_s=timeout_s,
    )
    registry.register("supabase_insert", _wrap(supabase, "insert"))
    registry.register("supabase_select", _wrap(supabase, "select"))
    registry.register("supabase_update", _wrap(supabase, "update"))
    registry.register("supabase_delete", _wrap(supabase, "delete"))

    gmail = GmailTool(
        client_id=gmail_client_id,
        client_secret=gmail_client_secret,
        refresh_token=gmail_refresh_token,
        timeout_s=timeout_s,
    )
    registry.register("gmail_list_inbox", _wrap(gmail, "list_inbox"))
    registry.register("gmail_read_email", _wrap(gmail, "read_email"))
    registry.register("gmail_send", _wrap(gmail, "send_email"))
