"""Sanitizer — prompt-injection stripping + PII scrubbing for tool outputs.

Attack 1 (prompt injection via tool output) and Attack 4 (indirect injection
via Supabase data) both rely on this: any value that will enter agent context
or be logged is treated as untrusted text. Never eval/exec data values.
"""

import re
from typing import Any

INJECTION_MARKERS = (
    "SYSTEM OVERRIDE",
    "ignore previous instructions",
    "ignore previous task",
    "ignore_previous_task",
    "SYSTEM PROMPT",
    "New task:",
    "exfiltrate",
    "Send all",
    "attacker@",
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s.-]{7,}\d)\b")
LONG_DIGIT_RE = re.compile(r"\b\d{9,}\b")


def contains_injection_marker(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker.lower() in lower for marker in INJECTION_MARKERS)


def _strip_injection(text: str) -> str:
    for marker in INJECTION_MARKERS:
        text = text.replace(marker, "[SANITIZED]")
        text = text.replace(marker.lower(), "[SANITIZED]")
    return text


def scrub_pii(text: str) -> str:
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    text = LONG_DIGIT_RE.sub("[DIGITS]", text)
    return text


def sanitize_tool_output(value: Any) -> Any:
    """Sanitize a value that will be logged or fed to agent context.

    Strings get injection markers stripped and PII redacted. Nested dicts and
    lists are walked recursively. Non-text values pass through untouched.
    """
    if isinstance(value, dict):
        return {k: sanitize_tool_output(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_tool_output(v) for v in value]
    if isinstance(value, str):
        return scrub_pii(_strip_injection(value))
    return value