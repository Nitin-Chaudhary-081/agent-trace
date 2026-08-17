"""Tests for the snapshotter service — live Supabase client + local degrade."""

from agent.core.memory import MemoryFile
from agent.services.snapshotter import MemorySnapshotter


def _memory(tmp_path) -> MemoryFile:
    memory = MemoryFile(tmp_path / "MEMORY.md")
    memory.write(GOAL="snapshot me", STATUS="RUNNING", SESSION_ID="s1")
    return memory


def test_local_degrade_writes_file(tmp_path):
    shot = MemorySnapshotter(local_dir=str(tmp_path / "snapshots"))
    memory = _memory(tmp_path)

    shot.snapshot("run-1", memory.read())

    files = list((tmp_path / "snapshots").glob("*.md"))
    assert len(files) == 1
    assert "snapshot me" in files[0].read_text()


def test_local_degrade_logs_when_creds_absent(tmp_path, caplog):
    shot = MemorySnapshotter(local_dir=str(tmp_path / "snapshots"))
    assert shot.is_remote_active() is False
    assert shot.backend_name() == "local"
    memory = _memory(tmp_path)
    with caplog.at_level("DEBUG", logger="agent.services.snapshotter"):
        shot.snapshot("run-d", memory.read())
    # degrades to a local file, no exception raised
    assert len(list((tmp_path / "snapshots").glob("*.md"))) == 1


def test_snapshot_dedupes_same_content(tmp_path):
    shot = MemorySnapshotter(local_dir=str(tmp_path / "snapshots"))
    memory = _memory(tmp_path)
    data = memory.read()

    shot.snapshot("run-1", data)
    shot.snapshot("run-1", data)

    files = list((tmp_path / "snapshots").glob("*.md"))
    assert len(files) == 1


def test_snapshot_accumulates_changes(tmp_path):
    shot = MemorySnapshotter(local_dir=str(tmp_path / "snapshots"))
    memory = _memory(tmp_path)

    shot.snapshot("run-1", memory.read())
    memory.append_completed_step("web_search")
    shot.snapshot("run-1", memory.read())

    files = list((tmp_path / "snapshots").glob("*.md"))
    assert len(files) == 2


def test_remote_requires_url_and_key(tmp_path):
    shot = MemorySnapshotter(
        local_dir=str(tmp_path / "snapshots"),
        supabase_url="https://x.supabase.co",
        supabase_key=None,
    )

    assert shot.is_remote_active() is False


def test_local_dir_created(tmp_path):
    shot = MemorySnapshotter(local_dir=str(tmp_path / "nested" / "dir"))
    memory = _memory(tmp_path)

    shot.snapshot("run-1", memory.read())

    assert (tmp_path / "nested" / "dir").exists()