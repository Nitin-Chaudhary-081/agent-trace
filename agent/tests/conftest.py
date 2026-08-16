"""Shared pytest fixtures for AgentTrace agent-core tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "agent", ROOT / "api", ROOT / "api" / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
