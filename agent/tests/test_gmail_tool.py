"""Tests for the live Gmail tool (Module 3).

Gmail needs OAuth2 credentials which are provided later. Offline tests cover
the creds-absent path, input validation, and typed errors; live send test runs
when GMAIL_REFRESH_TOKEN + a test address are configured.
"""

import os

import pytest

from agent.tools.gmail_tool import GmailTool
from agent.core.types import ToolResult


def _gmail_creds():
    return {
        "client_id": os.environ.get("GMAIL_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("GMAIL_CLIENT_SECRET", "").strip(),
        "refresh_token": os.environ.get("GMAIL_REFRESH_TOKEN", "").strip(),
    }


def _has_gmail_creds():
    return all(_gmail_creds().values())


def test_absent_creds_returns_typed_failure(monkeypatch):
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GMAIL_REFRESH_TOKEN", raising=False)
    tool = GmailTool()
    result = tool.invoke(operation="list_inbox", limit=5)
    assert result.success is False
    assert result.error == "not_configured"


def test_invalid_operation_rejected():
    tool = GmailTool(client_id="c", client_secret="s", refresh_token="t")
    result = tool.invoke(operation="delete_all", limit=5)
    assert result.success is False
    assert result.error == "invalid_operation"


def test_send_requires_recipient_subject_body():
    tool = GmailTool(client_id="c", client_secret="s", refresh_token="t")
    result = tool.invoke(operation="send_email", to="", subject="", body="")
    assert result.success is False
    assert result.error == "invalid_input"


def test_success_schema_matches_spec():
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"messages": [{"id": "abc123", "threadId": "t1"}]}

        def raise_for_status(self):
            return None

    class FakeSession:
        def request(self, method, url, **kwargs):
            if "oauth2.googleapis.com" in url:
                class Tok:
                    status_code = 200
                    text = ""

                    def json(self):
                        return {"access_token": "tok"}

                    def raise_for_status(self):
                        return None

                return Tok()
            assert "gmail.googleapis.com" in url
            return FakeResponse()

    tool = GmailTool(
        client_id="c",
        client_secret="s",
        refresh_token="t",
        session=FakeSession(),
    )
    result = tool.invoke(
        operation="list_inbox",
        unread_only=True,
        limit=2,
    )
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.error is None
    assert set(result.output) == {"messages"}
    assert result.output["messages"][0]["id"] == "abc123"


@pytest.mark.skipif(
    not (_has_gmail_creds() and os.environ.get("GMAIL_TEST_TO", "")),
    reason="Gmail creds or GMAIL_TEST_TO not set",
)
def test_live_send_email_to_self():
    tool = GmailTool(**_gmail_creds())
    to = os.environ["GMAIL_TEST_TO"]
    result = tool.invoke(
        operation="send_email",
        to=to,
        subject="AgentTrace test",
        body="Module 3 live test",
    )
    assert result.success is True, result.error