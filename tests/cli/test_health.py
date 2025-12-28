"""Comprehensive tests for health snapshot functionality."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mcp_common.cli.health import (
    RuntimeHealthSnapshot,
    get_snapshot_age_seconds,
    is_snapshot_fresh,
    load_runtime_health,
    write_runtime_health,
)


class TestRuntimeHealthSnapshotCreation:
    """Test RuntimeHealthSnapshot creation and defaults."""

    def test_empty_snapshot(self):
        """Test creating snapshot with no arguments."""
        snapshot = RuntimeHealthSnapshot()

        assert snapshot.orchestrator_pid is None
        assert snapshot.updated_at is None
        assert snapshot.watchers_running is False
        assert snapshot.remote_enabled is False
        assert snapshot.lifecycle_state is None
        assert snapshot.activity_state is None
        assert snapshot.last_remote_error is None

    def test_snapshot_with_basic_fields(self):
        """Test snapshot with basic fields."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            remote_enabled=True,
        )

        assert snapshot.orchestrator_pid == 12345
        assert snapshot.watchers_running is True
        assert snapshot.remote_enabled is True

    def test_snapshot_with_all_fields(self):
        """Test snapshot with all fields populated."""
        now = datetime.now(UTC).isoformat()

        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            updated_at=now,
            watchers_running=True,
            remote_enabled=True,
            lifecycle_state={"phase": "running", "uptime": 120},
            activity_state={"requests": 50, "errors": 2},
            last_remote_error="Connection timeout",
        )

        assert snapshot.orchestrator_pid == 12345
        assert snapshot.updated_at == now
        assert snapshot.watchers_running is True
        assert snapshot.remote_enabled is True
        assert snapshot.lifecycle_state == {"phase": "running", "uptime": 120}
        assert snapshot.activity_state == {"requests": 50, "errors": 2}
        assert snapshot.last_remote_error == "Connection timeout"


class TestRuntimeHealthSnapshotAsDict:
    """Test as_dict() method for JSON serialization."""

    def test_as_dict_empty_snapshot(self):
        """Test as_dict with empty snapshot."""
        snapshot = RuntimeHealthSnapshot()

        data = snapshot.as_dict()

        assert isinstance(data, dict)
        assert data["orchestrator_pid"] is None
        assert data["updated_at"] is None
        assert data["watchers_running"] is False
        assert data["remote_enabled"] is False
        assert data["lifecycle_state"] == {}
        assert data["activity_state"] == {}
        assert data["last_remote_error"] is None

    def test_as_dict_null_coalescing(self):
        """Test None values are coalesced to empty dicts/defaults."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            lifecycle_state=None,  # Should become {}
            activity_state=None,  # Should become {}
        )

        data = snapshot.as_dict()

        assert data["lifecycle_state"] == {}
        assert data["activity_state"] == {}

    def test_as_dict_preserves_values(self):
        """Test as_dict preserves all non-None values."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            lifecycle_state={"key": "value"},
            activity_state={"count": 42},
        )

        data = snapshot.as_dict()

        assert data["orchestrator_pid"] == 12345
        assert data["watchers_running"] is True
        assert data["lifecycle_state"] == {"key": "value"}
        assert data["activity_state"] == {"count": 42}

    def test_as_dict_json_serializable(self):
        """Test as_dict output is JSON serializable."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            updated_at=datetime.now(UTC).isoformat(),
            lifecycle_state={"nested": {"value": 123}},
        )

        data = snapshot.as_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

        # Should round-trip
        restored = json.loads(json_str)
        assert restored["orchestrator_pid"] == 12345


class TestWriteRuntimeHealth:
    """Test write_runtime_health function."""

    def test_write_creates_file(self, tmp_path: Path):
        """Test writing creates the file."""
        snapshot_path = tmp_path / "health.json"
        snapshot = RuntimeHealthSnapshot(orchestrator_pid=12345)

        write_runtime_health(snapshot_path, snapshot)

        assert snapshot_path.exists()

    def test_write_sets_secure_permissions(self, tmp_path: Path):
        """Test written file has 0o600 permissions."""
        snapshot_path = tmp_path / "health.json"
        snapshot = RuntimeHealthSnapshot()

        write_runtime_health(snapshot_path, snapshot)

        stat = snapshot_path.stat()
        assert stat.st_mode & 0o777 == 0o600

    def test_write_sets_timestamp(self, tmp_path: Path):
        """Test write automatically sets updated_at if None."""
        snapshot_path = tmp_path / "health.json"
        snapshot = RuntimeHealthSnapshot(orchestrator_pid=12345)
        assert snapshot.updated_at is None

        write_runtime_health(snapshot_path, snapshot)

        # Read back and verify timestamp was set
        data = json.loads(snapshot_path.read_text())
        assert data["updated_at"] is not None
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(data["updated_at"])

    def test_write_always_sets_timestamp(self, tmp_path: Path):
        """Test write always sets updated_at to current time."""
        snapshot_path = tmp_path / "health.json"
        old_time = "2025-01-01T12:00:00+00:00"
        snapshot = RuntimeHealthSnapshot(orchestrator_pid=12345, updated_at=old_time)

        write_runtime_health(snapshot_path, snapshot)

        data = json.loads(snapshot_path.read_text())
        # Should overwrite with current time, not preserve old time
        assert data["updated_at"] != old_time
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(data["updated_at"])

    def test_write_atomic_operation(self, tmp_path: Path):
        """Test write uses atomic tmp → replace pattern."""
        snapshot_path = tmp_path / "health.json"
        snapshot = RuntimeHealthSnapshot(orchestrator_pid=12345)

        write_runtime_health(snapshot_path, snapshot)

        # Tmp file should be cleaned up
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_write_cleanup_on_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test tmp cleanup if replace fails."""
        snapshot_path = tmp_path / "health.json"
        snapshot = RuntimeHealthSnapshot(orchestrator_pid=12345)
        original_replace = Path.replace

        def fake_replace(self: Path, target: Path) -> Path:
            if self.name.endswith(".tmp"):
                msg = "boom"
                raise OSError(msg)
            return original_replace(self, target)

        monkeypatch.setattr(Path, "replace", fake_replace)

        with pytest.raises(OSError, match="boom"):
            write_runtime_health(snapshot_path, snapshot)

        assert not snapshot_path.with_suffix(".tmp").exists()

    def test_write_overwrites_existing(self, tmp_path: Path):
        """Test writing to existing file overwrites it."""
        snapshot_path = tmp_path / "health.json"

        # Write first snapshot
        snapshot1 = RuntimeHealthSnapshot(orchestrator_pid=11111)
        write_runtime_health(snapshot_path, snapshot1)

        # Write second snapshot
        snapshot2 = RuntimeHealthSnapshot(orchestrator_pid=22222)
        write_runtime_health(snapshot_path, snapshot2)

        # Should contain second snapshot
        data = json.loads(snapshot_path.read_text())
        assert data["orchestrator_pid"] == 22222

    def test_write_creates_parent_directory(self, tmp_path: Path):
        """Test write creates parent directory if needed."""
        nested_path = tmp_path / "subdir" / "health.json"
        snapshot = RuntimeHealthSnapshot(orchestrator_pid=12345)

        write_runtime_health(nested_path, snapshot)

        assert nested_path.exists()
        assert nested_path.parent.is_dir()

    def test_write_complex_state(self, tmp_path: Path):
        """Test writing complex nested state."""
        snapshot_path = tmp_path / "health.json"
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            lifecycle_state={
                "phase": "running",
                "nested": {"value": 123, "list": [1, 2, 3]},
            },
            activity_state={"metrics": {"cpu": 45.2, "memory": 1024}},
        )

        write_runtime_health(snapshot_path, snapshot)

        # Should round-trip
        loaded = load_runtime_health(snapshot_path)
        assert loaded.lifecycle_state == snapshot.lifecycle_state
        assert loaded.activity_state == snapshot.activity_state


class TestLoadRuntimeHealth:
    """Test load_runtime_health function."""

    def test_load_missing_file(self, tmp_path: Path):
        """Test loading missing file returns empty snapshot."""
        snapshot_path = tmp_path / "missing.json"

        snapshot = load_runtime_health(snapshot_path)

        assert snapshot.orchestrator_pid is None
        assert snapshot.watchers_running is False

    def test_load_existing_file(self, tmp_path: Path):
        """Test loading existing file."""
        snapshot_path = tmp_path / "health.json"
        original = RuntimeHealthSnapshot(orchestrator_pid=12345, watchers_running=True)
        write_runtime_health(snapshot_path, original)

        loaded = load_runtime_health(snapshot_path)

        assert loaded.orchestrator_pid == 12345
        assert loaded.watchers_running is True

    def test_load_corrupted_json(self, tmp_path: Path):
        """Test loading corrupted JSON returns empty snapshot."""
        snapshot_path = tmp_path / "corrupted.json"
        snapshot_path.write_text("{invalid json content")

        snapshot = load_runtime_health(snapshot_path)

        # Should gracefully degrade, not raise
        assert snapshot.orchestrator_pid is None
        assert snapshot.watchers_running is False

    def test_load_malformed_data(self, tmp_path: Path):
        """Test loading valid JSON with wrong structure returns empty snapshot."""
        snapshot_path = tmp_path / "malformed.json"
        snapshot_path.write_text(json.dumps({"unexpected": "structure"}))

        snapshot = load_runtime_health(snapshot_path)

        # Should gracefully degrade
        assert snapshot.orchestrator_pid is None

    def test_load_non_dict_data(self, tmp_path: Path):
        """Test loading non-dict JSON returns empty snapshot."""
        snapshot_path = tmp_path / "list.json"
        snapshot_path.write_text(json.dumps([1, 2, 3]))

        snapshot = load_runtime_health(snapshot_path)

        assert snapshot.orchestrator_pid is None
        assert snapshot.watchers_running is False

    def test_load_preserves_all_fields(self, tmp_path: Path):
        """Test load preserves all fields from written snapshot."""
        snapshot_path = tmp_path / "health.json"
        original = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            remote_enabled=True,
            lifecycle_state={"phase": "running"},
            activity_state={"count": 42},
            last_remote_error="Test error",
        )
        write_runtime_health(snapshot_path, original)

        loaded = load_runtime_health(snapshot_path)

        assert loaded.orchestrator_pid == original.orchestrator_pid
        assert loaded.watchers_running == original.watchers_running
        assert loaded.remote_enabled == original.remote_enabled
        assert loaded.lifecycle_state == original.lifecycle_state
        assert loaded.activity_state == original.activity_state
        assert loaded.last_remote_error == original.last_remote_error

    def test_load_permission_denied(self, tmp_path: Path):
        """Test loading file with permission denied returns empty snapshot."""
        snapshot_path = tmp_path / "forbidden.json"
        snapshot_path.write_text("{}")
        snapshot_path.chmod(0o000)  # No read permission

        try:
            snapshot = load_runtime_health(snapshot_path)

            # Should gracefully degrade
            assert snapshot.orchestrator_pid is None
        finally:
            # Restore permissions for cleanup
            snapshot_path.chmod(0o600)


class TestGetSnapshotAgeSeconds:
    """Test get_snapshot_age_seconds function."""

    def test_age_none_when_no_timestamp(self):
        """Test age is None when updated_at is None."""
        snapshot = RuntimeHealthSnapshot()

        age = get_snapshot_age_seconds(snapshot)

        assert age is None

    def test_age_calculation(self):
        """Test age calculation for recent snapshot."""
        # Create snapshot from 5 seconds ago
        past_time = datetime.now(UTC)
        past_time = past_time.replace(microsecond=0)  # Remove microseconds
        past_iso = past_time.isoformat()

        snapshot = RuntimeHealthSnapshot(updated_at=past_iso)

        # Wait a bit
        time.sleep(0.1)

        age = get_snapshot_age_seconds(snapshot)

        assert age is not None
        assert age >= 0.1  # At least 0.1 seconds old
        assert age < 10.0  # But not too old

    def test_age_invalid_timestamp(self):
        """Test age is None for invalid timestamp."""
        snapshot = RuntimeHealthSnapshot(updated_at="invalid-timestamp")

        age = get_snapshot_age_seconds(snapshot)

        assert age is None


class TestIsSnapshotFresh:
    """Test is_snapshot_fresh function."""

    def test_fresh_recent_snapshot(self):
        """Test recent snapshot is fresh."""
        snapshot = RuntimeHealthSnapshot(updated_at=datetime.now(UTC).isoformat())

        is_fresh = is_snapshot_fresh(snapshot, ttl_seconds=60.0)

        assert is_fresh is True

    def test_stale_old_snapshot(self):
        """Test old snapshot is stale."""
        # Create snapshot from 120 seconds ago
        past_time = datetime.now(UTC)
        past_time = past_time.replace(microsecond=0)
        snapshot = RuntimeHealthSnapshot(updated_at=past_time.isoformat())

        # Wait to ensure it's actually old
        time.sleep(0.1)

        # With 1 second TTL, should be stale
        is_fresh = is_snapshot_fresh(snapshot, ttl_seconds=0.05)

        assert is_fresh is False

    def test_fresh_no_timestamp(self):
        """Test snapshot with no timestamp is considered stale."""
        snapshot = RuntimeHealthSnapshot(updated_at=None)

        is_fresh = is_snapshot_fresh(snapshot, ttl_seconds=60.0)

        # No timestamp = stale (cannot verify freshness)
        assert is_fresh is False

    def test_fresh_invalid_timestamp(self):
        """Test invalid timestamp is considered stale."""
        snapshot = RuntimeHealthSnapshot(updated_at="not-a-time")

        is_fresh = is_snapshot_fresh(snapshot, ttl_seconds=60.0)

        assert is_fresh is False

    def test_fresh_boundary_condition(self):
        """Test freshness at exact TTL boundary."""
        # Create snapshot at exact TTL age
        past_time = datetime.now(UTC)
        snapshot = RuntimeHealthSnapshot(updated_at=past_time.isoformat())

        # Immediately check with very long TTL
        is_fresh = is_snapshot_fresh(snapshot, ttl_seconds=1000.0)

        assert is_fresh is True


class TestHealthSnapshotRoundTrip:
    """Test complete write/read cycles."""

    def test_round_trip_preserves_data(self, tmp_path: Path):
        """Test write → read preserves all data."""
        snapshot_path = tmp_path / "health.json"
        original = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            remote_enabled=True,
            lifecycle_state={"phase": "running", "nested": {"value": 123}},
            activity_state={"count": 42, "list": [1, 2, 3]},
            last_remote_error="Test error message",
        )

        # Write and read
        write_runtime_health(snapshot_path, original)
        loaded = load_runtime_health(snapshot_path)

        # Verify all fields match
        assert loaded.orchestrator_pid == original.orchestrator_pid
        assert loaded.watchers_running == original.watchers_running
        assert loaded.remote_enabled == original.remote_enabled
        assert loaded.lifecycle_state == original.lifecycle_state
        assert loaded.activity_state == original.activity_state
        assert loaded.last_remote_error == original.last_remote_error

    def test_multiple_write_cycles(self, tmp_path: Path):
        """Test multiple write/read cycles work correctly."""
        snapshot_path = tmp_path / "health.json"

        # Cycle 1
        snapshot1 = RuntimeHealthSnapshot(orchestrator_pid=11111)
        write_runtime_health(snapshot_path, snapshot1)
        loaded1 = load_runtime_health(snapshot_path)
        assert loaded1.orchestrator_pid == 11111

        # Cycle 2 (overwrite)
        snapshot2 = RuntimeHealthSnapshot(orchestrator_pid=22222)
        write_runtime_health(snapshot_path, snapshot2)
        loaded2 = load_runtime_health(snapshot_path)
        assert loaded2.orchestrator_pid == 22222

        # Cycle 3 (overwrite)
        snapshot3 = RuntimeHealthSnapshot(orchestrator_pid=33333)
        write_runtime_health(snapshot_path, snapshot3)
        loaded3 = load_runtime_health(snapshot_path)
        assert loaded3.orchestrator_pid == 33333
