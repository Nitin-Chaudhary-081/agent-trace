"""MEMORY.md persistence with file locking.

MEMORY.md is the agent's durable state file. It must survive process
restarts and support concurrent reads from the observer UI, so every
write happens under an exclusive advisory lock.
"""

import re
import uuid
from pathlib import Path

MEMORY_SECTIONS = (
    "GOAL",
    "STATUS",
    "PROGRESS",
    "COMPLETED_STEPS",
    "NEXT_ACTIONS",
    "FAILURES",
    "SESSION_ID",
)

DEFAULT_STATUS = "PENDING"
SUMMARIZE_THRESHOLD_CHARS = 4000
_MAX_PROGRESS_ENTRIES = 1000


class MemoryError(Exception):
    """Typed error for MEMORY.md operations."""


class MemoryFile:
    def __init__(self, path: str | Path):
        path = Path(path)
        if not str(path) or not path.name:
            raise MemoryError("MEMORY.md path is empty")
        if path.exists() and path.is_dir():
            raise MemoryError(f"MEMORY.md path is a directory: {path}")
        self.path = path

    def read(self) -> dict[str, str]:
        sections = {name: "" for name in MEMORY_SECTIONS}
        sections["STATUS"] = DEFAULT_STATUS
        if self.path.exists():
            sections = self._parse(self.path.read_text(encoding="utf-8"))
        if not sections["SESSION_ID"]:
            sections["SESSION_ID"] = self.new_session_id()
        return sections

    def _parse(self, text: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        current: str | None = None
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            match = re.match(r"^\[([A-Z_]+)\]$", stripped)
            if match and match.group(1) in MEMORY_SECTIONS:
                current = match.group(1)
                sections[current] = ""
                continue
            if current is not None and stripped:
                sections[current] = (sections[current] + "\n" if sections[current] else "") + stripped

        for name in MEMORY_SECTIONS:
            sections.setdefault(name, "")
        if not sections["STATUS"]:
            sections["STATUS"] = DEFAULT_STATUS

        if not sections["SESSION_ID"]:
            sections["SESSION_ID"] = self.new_session_id()
        return sections

    def write(self, **sections: str) -> None:
        data = self.read()
        for name, value in sections.items():
            if name not in MEMORY_SECTIONS:
                raise MemoryError(f"Unknown section: {name}")
            data[name] = value
        if not data["SESSION_ID"]:
            data["SESSION_ID"] = self.new_session_id()

        rendered = ["# AgentTrace Memory", ""]
        for name in MEMORY_SECTIONS:
            value = data[name]
            rendered.append(f"[{name}]")
            if value:
                rendered.append(value)
            rendered.append("")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            self.path.write_text("\n".join(rendered), encoding="utf-8")

    def update(self, patch: dict[str, str]) -> None:
        self.write(**patch)

    def new_session_id(self) -> str:
        return str(uuid.uuid4())

    def has_incomplete_session(self) -> bool:
        if not self.path.exists():
            return False
        data = self.read()
        return data["STATUS"] in ("PENDING", "RUNNING")

    def append_completed_step(self, step: str) -> None:
        data = self.read()
        existing = data["COMPLETED_STEPS"]
        existing = (existing + "\n" if existing else "") + step
        self.write(COMPLETED_STEPS=existing)

    def append_progress(self, entry: str) -> None:
        data = self.read()
        existing = data["PROGRESS"]
        existing = (existing + "\n" if existing else "") + entry
        self.write(PROGRESS=existing)
        self._roll_progress()

    def append_failure(self, message: str) -> None:
        data = self.read()
        existing = data["FAILURES"]
        existing = (existing + "\n" if existing else "") + message
        self.write(FAILURES=existing)

    def _roll_progress(self) -> None:
        """Rolling deque summarization: drop oldest PROGRESS entries once the
        rendered MEMORY.md exceeds the summarization threshold. Keeps the most
        recent context; deterministic and testable — no LLM dependency."""

        for _ in range(_MAX_PROGRESS_ENTRIES):
            data = self.read()
            lines = data["PROGRESS"].splitlines()
            if len(lines) <= 1:
                return
            estimate = self._estimate_chars(data)
            if estimate <= SUMMARIZE_THRESHOLD_CHARS:
                return
            self.write(PROGRESS="\n".join(lines[1:]))
        # final pass: hard cap line count as a safety net
        data = self.read()
        lines = data["PROGRESS"].splitlines()
        self.write(PROGRESS="\n".join(lines[-(_MAX_PROGRESS_ENTRIES // 2):]))

    def _estimate_chars(self, data: dict[str, str]) -> int:
        return sum(len(v) for v in data.values()) + 12 * len(data)

    def start_or_resume(self) -> dict[str, str]:
        """Session discovery.

        Returns mode `resumed` when an incomplete session exists (a GOAL is
        present and the run never reached COMPLETED), else mode `fresh` with a
        new SESSION_ID written to disk. STOPPED_MAX_STEPS and FAILED are
        resumable.
        """
        data = self.read()
        resumable = bool(data["GOAL"]) and data["STATUS"] != "COMPLETED"
        if resumable:
            return {
                "mode": "resumed",
                "session_id": data["SESSION_ID"],
                "goal": data["GOAL"],
                "completed_steps": [
                    line for line in data["COMPLETED_STEPS"].splitlines() if line
                ],
            }
        sid = self.new_session_id()
        self.write(SESSION_ID=sid, STATUS="PENDING", COMPLETED_STEPS="", FAILURES="")
        return {"mode": "fresh", "session_id": sid}

    def render(self) -> str:
        data = self.read()
        rendered = ["# AgentTrace Memory", ""]
        for name in MEMORY_SECTIONS:
            value = data[name]
            rendered.append(f"[{name}]")
            if value:
                rendered.append(value)
            rendered.append("")
        return "\n".join(rendered)

    def _locked(self):
        if not hasattr(self, "_lock_file"):
            self._lock_file = self.path.with_suffix(self.path.suffix + ".lock")
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            self._lock_fh = self._lock_file.open("a+", encoding="utf-8")
        return _FileLock(self._lock_fh)


class _FileLock:
    """Advisory exclusive lock using fcntl (POSIX); no-op elsewhere."""

    def __init__(self, fh):
        self._fh = fh

    def __enter__(self):
        try:
            import fcntl
        except ImportError:
            return self
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        try:
            import fcntl
        except ImportError:
            return False
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        return False


class Memory:
    """In-memory facade for the agent loop (no disk writes)."""

    def __init__(self, initial: dict[str, str] | None = None):
        self._data = {
            name: "" for name in MEMORY_SECTIONS
        }
        self._data["STATUS"] = DEFAULT_STATUS
        self._data["SESSION_ID"] = str(uuid.uuid4())
        if initial:
            self._data.update(initial)

    def get(self, name: str) -> str:
        return self._data.get(name, "")

    def set(self, name: str, value: str) -> None:
        if name not in MEMORY_SECTIONS:
            raise MemoryError(f"Unknown section: {name}")
        self._data[name] = value

    def to_dict(self) -> dict[str, str]:
        return dict(self._data)
