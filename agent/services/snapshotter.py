"""MemorySnapshotter — snapshots MEMORY.md after every 5 steps.

Live Supabase backup: when SUPABASE_URL + a service key are configured, the
snapshot is inserted into the `agent_memory_snapshots` table via the Supabase
PostgREST API (pure-Python `requests`, aarch64-safe — the full `supabase-py`
client pulls in pydantic-core/Rust wheels which the project bans).

When remote credentials are absent the snapshot degrades to a local file in
`local_dir`, content-hash deduped (survives renames, auto-invalidates on
content change). Zero mocks — no fake client behind this interface.
"""

import hashlib
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

SNAPSHOT_TABLE = "agent_memory_snapshots"
_HASH_CHUNK = 65536


class SnapshotterError(Exception):
    """Typed error for snapshot failures."""


class MemorySnapshotter:
    def __init__(
        self,
        local_dir: str | Path = ".snapshots",
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        timeout_s: int = 10,
    ):
        self.local_dir = Path(local_dir)
        self.supabase_url = (supabase_url or "").rstrip("/")
        self.supabase_key = supabase_key or ""
        self.timeout_s = timeout_s
        self._seen_hashes: set[str] = set()

    def is_remote_active(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    def backend_name(self) -> str:
        return "supabase" if self.is_remote_active() else "local"

    def snapshot(self, run_id: str, memory_data: dict[str, str]) -> str:
        rendered = self._render(memory_data)
        content_hash = self._content_hash(rendered)
        if content_hash in self._seen_hashes:
            return content_hash

        if self.is_remote_active():
            self._snapshot_remote(run_id, rendered, content_hash)
        else:
            self._snapshot_local(run_id, rendered, content_hash)

        self._seen_hashes.add(content_hash)
        logger.info(
            "memory snapshot (%s): run=%s hash=%s",
            self.backend_name(),
            run_id,
            content_hash[:12],
        )
        return content_hash

    def _render(self, memory_data: dict[str, str]) -> str:
        lines = ["# AgentTrace Memory", ""]
        for name in ("GOAL", "STATUS", "PROGRESS", "COMPLETED_STEPS",
                     "NEXT_ACTIONS", "FAILURES", "SESSION_ID"):
            value = memory_data.get(name, "")
            lines.append(f"[{name}]")
            if value:
                lines.append(value)
            lines.append("")
        return "\n".join(lines)

    def _content_hash(self, text: str) -> str:
        sha = hashlib.sha256()
        sha.update(text.encode("utf-8"))
        return sha.hexdigest()

    def _snapshot_local(self, run_id: str, rendered: str, content_hash: str) -> None:
        self.local_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        path = self.local_dir / f"{ts}_{run_id[:8]}_{content_hash[:12]}.md"
        path.write_text(rendered, encoding="utf-8")

    def _snapshot_remote(self, run_id: str, rendered: str, content_hash: str) -> None:
        row = {
            "session_id": self._session_from(rendered),
            "run_id": run_id,
            "memory_md": rendered,
            "content_hash": content_hash,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        url = f"{self.supabase_url}/rest/v1/{SNAPSHOT_TABLE}"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        try:
            resp = requests.post(url, json=row, headers=headers, timeout=self.timeout_s)
            if resp.status_code not in (200, 201, 204):
                raise SnapshotterError(
                    f"supabase insert failed: {resp.status_code} {resp.text[:200]}"
                )
        except requests.RequestException as exc:
            raise SnapshotterError(f"supabase request failed: {exc}") from exc

    def _session_from(self, rendered: str) -> str:
        found = False
        for line in rendered.splitlines():
            if line.startswith("[SESSION_ID]"):
                found = True
                continue
            if found and line.strip():
                return line.strip()
        return ""

    def list_local(self) -> list[Path]:
        if not self.local_dir.exists():
            return []
        return sorted(self.local_dir.glob("*.md"))
