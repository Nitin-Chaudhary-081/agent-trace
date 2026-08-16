"""Live Gmail tool — Google OAuth2 + Gmail REST API via pure-Python requests.

Operations: list_inbox (unread, last N), read_email (by id), send_email.
Auth: GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET + GMAIL_REFRESH_TOKEN from env;
the tool exchanges the refresh token for an access token on each invocation.
Typed errors only: not_configured / invalid_operation / invalid_input /
timeout / auth_error / api_error.
"""

import base64
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any

import requests

from agent.core.types import ToolResult
from agent.tools import BaseTool

DEFAULT_TIMEOUT_S = 60.0
VALID_OPERATIONS = ("list_inbox", "read_email", "send_email")
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


@dataclass(frozen=True)
class GmailTool(BaseTool):
    name: str = "gmail"
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    timeout_s: float = DEFAULT_TIMEOUT_S
    session: Any = field(default=None, repr=False)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        session = self.session or requests.Session()
        kwargs.setdefault("timeout", self.timeout_s)
        return session.request(method, url, **kwargs)

    def _bounded(self, fn, *args, **kwargs) -> Any:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn, *args, **kwargs)
            return future.result(timeout=self.timeout_s)

    def _access_token(self) -> str:
        resp = self._request(
            "POST",
            TOKEN_ENDPOINT,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code != 200:
            raise ValueError("token_exchange_failed")
        token = resp.json().get("access_token")
        if not token:
            raise ValueError("token_exchange_failed")
        return token

    def _invoke_with_token(self, operation: str, token: str, **params: Any) -> ToolResult:
        headers = {"Authorization": f"Bearer {token}"}

        if operation == "list_inbox":
            limit = params.get("limit", 10)
            q = "is:unread" if params.get("unread_only") else ""
            resp = self._request(
                "GET",
                f"{GMAIL_API}/messages",
                headers=headers,
                params={"q": q, "maxResults": limit},
            )
            if resp.status_code != 200:
                return ToolResult.failure("api_error")
            messages = resp.json().get("messages", [])
            return ToolResult(
                success=True, output={"messages": messages}, error=None, duration_ms=0
            )

        if operation == "read_email":
            message_id = params.get("message_id", "")
            if not message_id:
                return ToolResult.failure("invalid_input")
            resp = self._request(
                "GET",
                f"{GMAIL_API}/messages/{message_id}",
                headers=headers,
                params={"format": "metadata"},
            )
            if resp.status_code != 200:
                return ToolResult.failure("api_error")
            payload = resp.json()
            snippet = payload.get("snippet", "")
            subject = ""
            for h in payload.get("payload", {}).get("headers", []):
                if h.get("name", "").lower() == "subject":
                    subject = h.get("value", "")
            return ToolResult(
                success=True,
                output={
                    "messages": [
                        {
                            "id": message_id,
                            "subject": subject,
                            "snippet": snippet,
                        }
                    ]
                },
                error=None,
                duration_ms=0,
            )

        if operation == "send_email":
            to = params.get("to", "")
            subject = params.get("subject", "")
            body = params.get("body", "")
            if not to or not subject or not body:
                return ToolResult.failure("invalid_input")
            msg = EmailMessage()
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(body)
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            resp = self._request(
                "POST",
                f"{GMAIL_API}/messages/send",
                headers=headers,
                json={"raw": raw},
            )
            if resp.status_code != 200:
                return ToolResult.failure("api_error")
            sent = resp.json().get("id", "")
            return ToolResult(
                success=True,
                output={"messages": [{"id": sent}]},
                error=None,
                duration_ms=0,
            )

        return ToolResult.failure("invalid_operation")

    def invoke(self, operation: str = "", **params: Any) -> ToolResult:
        if operation not in VALID_OPERATIONS:
            return ToolResult.failure("invalid_operation")
        if operation == "send_email":
            if not (params.get("to") and params.get("subject") and params.get("body")):
                return ToolResult.failure("invalid_input")
        if operation == "read_email" and not params.get("message_id"):
            return ToolResult.failure("invalid_input")
        if not (self.client_id and self.client_secret and self.refresh_token):
            return ToolResult.failure("not_configured")

        start = time.monotonic()
        try:
            token = self._bounded(self._access_token)
            result = self._invoke_with_token(operation, token, **params)
        except TimeoutError:
            return ToolResult.failure("timeout")
        except (requests.RequestException, ValueError) as exc:
            err = "auth_error" if "token" in str(exc) else "api_error"
            return ToolResult.failure(err)
        elapsed = int((time.monotonic() - start) * 1000)
        return ToolResult(
            success=result.success,
            output=result.output,
            error=result.error,
            duration_ms=elapsed,
        )