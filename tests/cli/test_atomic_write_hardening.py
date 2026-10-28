"""Atomic-write hardening for the CLI snapshot writers.

Every writer that publishes a file by writing a temp file and renaming
it over the destination used a *fixed* temp name -- ``path.with_suffix
(".tmp")``. That name is shared by every writer of the same destination,
which breaks in two ways:

* **Concurrent writers collide.** The server factory writes the health
  snapshot at startup, in its shutdown signal handler, and the CLI
  health probe writes it again -- three processes, one file. Whichever
  writer renames first moves the temp file out from under the others,
  whose rename then fails with ``FileNotFoundError``.
* **A stale temp file is reused**, and a symlink planted at that path
  is followed, so the write can land in -- and truncate -- an arbitrary
  file.

A uniquely named temp file (``tempfile.mkstemp``) closes both: fresh
file, unique name, 0600, and it refuses to follow an existing path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_common.cli.health import RuntimeHealthSnapshot, write_runtime_health
from mcp_common.cli.security import atomic_write_json, write_pid_file


def _nested_writer(monkeypatch: pytest.MonkeyPatch, write: object) -> None:
    """Make ``os.replace`` run a second, overlapping write first."""
    real_replace = os.replace
    state = {"nested": False}

    def replace_with_nested_writer(src: object, dst: object) -> None:
        if not state["nested"]:
            state["nested"] = True
            write()
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", replace_with_nested_writer)


def test_overlapping_health_writers_do_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two writers overlapping on the health snapshot must not race."""
    snapshot_path = tmp_path / "health.json"

    _nested_writer(
        monkeypatch,
        lambda: write_runtime_health(
            snapshot_path, RuntimeHealthSnapshot(orchestrator_pid=22222)
        ),
    )

    try:
        write_runtime_health(
            snapshot_path, RuntimeHealthSnapshot(orchestrator_pid=11111)
        )
    except FileNotFoundError as exc:
        pytest.fail(f"overlapping writers raced on a shared temp file: {exc}")

    published = json.loads(snapshot_path.read_text())
    assert published["orchestrator_pid"] in {11111, 22222}


def test_overlapping_json_writers_do_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two writers overlapping on a JSON snapshot must not race."""
    target = tmp_path / "snapshot.json"

    _nested_writer(monkeypatch, lambda: atomic_write_json(target, {"who": "second"}))

    try:
        atomic_write_json(target, {"who": "first"})
    except FileNotFoundError as exc:
        pytest.fail(f"overlapping writers raced on a shared temp file: {exc}")

    published = json.loads(target.read_text())
    assert published["who"] in {"first", "second"}


def test_overlapping_pid_writers_do_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two writers overlapping on the pid file must not race."""
    pid_path = tmp_path / "server.pid"

    _nested_writer(monkeypatch, lambda: write_pid_file(pid_path, 22222))

    try:
        write_pid_file(pid_path, 11111)
    except FileNotFoundError as exc:
        pytest.fail(f"overlapping writers raced on a shared temp file: {exc}")

    assert pid_path.read_text() in {"11111", "22222"}


def test_health_writer_does_not_reuse_a_stale_temp_file(tmp_path: Path) -> None:
    """A leftover temp file must not be reused for the new write."""
    snapshot_path = tmp_path / "health.json"
    stale = snapshot_path.with_suffix(".tmp")
    stale.write_text("stale payload")
    stale.chmod(0o644)

    write_runtime_health(snapshot_path, RuntimeHealthSnapshot(orchestrator_pid=7))

    assert stale.exists(), "the write consumed the pre-existing temp file"
    assert stale.read_text() == "stale payload"


def test_health_writer_does_not_follow_a_symlinked_temp_file(tmp_path: Path) -> None:
    """A symlink planted at the temp path must not be written through."""
    victim = tmp_path / "victim.txt"
    victim.write_text("do not touch")
    snapshot_path = tmp_path / "health.json"
    snapshot_path.with_suffix(".tmp").symlink_to(victim)

    write_runtime_health(snapshot_path, RuntimeHealthSnapshot(orchestrator_pid=7))

    assert victim.read_text() == "do not touch"


def test_json_writer_does_not_follow_a_symlinked_temp_file(tmp_path: Path) -> None:
    """A symlink planted at the temp path must not be written through."""
    victim = tmp_path / "victim.txt"
    victim.write_text("do not touch")
    target = tmp_path / "snapshot.json"
    target.with_suffix(".tmp").symlink_to(victim)

    atomic_write_json(target, {"ok": True})

    assert victim.read_text() == "do not touch"
    assert json.loads(target.read_text()) == {"ok": True}
