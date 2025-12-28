"""Runtime health snapshot management.

Provides dataclass and I/O functions for Oneiric runtime health snapshots
with graceful degradation and atomic writes for crash-safety.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("mcp_common.cli.health")


@dataclass
class RuntimeHealthSnapshot:
    """Runtime health snapshot matching Oneiric schema.

    This dataclass matches the structure expected by Oneiric's
    LifecycleManager for runtime health monitoring.

    Attributes:
        orchestrator_pid: Process ID of the MCP server orchestrator
        updated_at: ISO timestamp of last update
        watchers_running: Whether lifecycle watchers are active
        remote_enabled: Whether remote sync is enabled
        last_remote_sync_at: ISO timestamp of last successful remote sync
        last_remote_error: Last remote sync error message (if any)
        lifecycle_state: Lifecycle state details (component-specific)
        activity_state: Activity state details (component-specific)
    """

    orchestrator_pid: int | None = None
    updated_at: str | None = None
    watchers_running: bool = False
    remote_enabled: bool = False
    last_remote_sync_at: str | None = None
    last_remote_error: str | None = None
    lifecycle_state: dict[str, Any] | None = None
    activity_state: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Convert to dict with null coalescing.

        Returns:
            Dictionary representation with empty dicts for None state fields
        """
        data = asdict(self)
        if data.get("lifecycle_state") is None:
            data["lifecycle_state"] = {}
        if data.get("activity_state") is None:
            data["activity_state"] = {}
        return data


def load_runtime_health(path: Path) -> RuntimeHealthSnapshot:
    """Load runtime health snapshot with graceful degradation.

    This function NEVER raises exceptions - it returns an empty snapshot
    if the file is missing or corrupted. This ensures CLI commands remain
    functional even when snapshots are damaged.

    Args:
        path: Path to runtime_health.json

    Returns:
        RuntimeHealthSnapshot (empty if file missing or corrupted)

    Example:
        >>> snapshot = load_runtime_health(Path(".oneiric_cache/runtime_health.json"))
        >>> if snapshot.orchestrator_pid:
        ...     print(f"Server running with PID {snapshot.orchestrator_pid}")
    """
    if not path.exists():
        return RuntimeHealthSnapshot()

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        # Corrupted or unreadable - log warning, return empty
        logger.warning("Corrupted health snapshot at %s: %s", path, e)
        return RuntimeHealthSnapshot()

    if not isinstance(data, dict):
        logger.warning("Invalid health snapshot format at %s: not a dict", path)
        return RuntimeHealthSnapshot()

    # Populate snapshot with validation
    snapshot = RuntimeHealthSnapshot()
    snapshot.orchestrator_pid = data.get("orchestrator_pid")
    snapshot.updated_at = data.get("updated_at")
    snapshot.watchers_running = bool(data.get("watchers_running", False))
    snapshot.remote_enabled = bool(data.get("remote_enabled", False))
    snapshot.last_remote_sync_at = data.get("last_remote_sync_at")
    snapshot.last_remote_error = data.get("last_remote_error")
    snapshot.lifecycle_state = data.get("lifecycle_state") or {}
    snapshot.activity_state = data.get("activity_state") or {}

    return snapshot


def write_runtime_health(path: Path, snapshot: RuntimeHealthSnapshot) -> None:
    """Write runtime health snapshot atomically.

    Uses atomic tmp file + replace pattern for crash-safety. Creates parent
    directories with secure permissions. Updates snapshot.updated_at to
    current timestamp automatically.

    Args:
        path: Path to runtime_health.json
        snapshot: Snapshot to write

    Raises:
        OSError: If write fails (disk full, permissions, etc.)

    Example:
        >>> snapshot = RuntimeHealthSnapshot(
        ...     orchestrator_pid=os.getpid(),
        ...     watchers_running=True
        ... )
        >>> write_runtime_health(
        ...     Path(".oneiric_cache/runtime_health.json"),
        ...     snapshot
        ... )
    """
    # Create cache directory with secure permissions
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Update timestamp
    snapshot.updated_at = datetime.now(UTC).isoformat()

    # Atomic write: tmp file → replace
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(snapshot.as_dict(), indent=2))
        tmp.chmod(0o600)  # Owner read/write only
        tmp.replace(path)  # Atomic on POSIX systems
    except OSError:
        # Cleanup tmp file on error
        tmp.unlink(missing_ok=True)
        raise


def is_snapshot_fresh(snapshot: RuntimeHealthSnapshot, ttl_seconds: float) -> bool:
    """Check if snapshot is within TTL threshold.

    Args:
        snapshot: Runtime health snapshot
        ttl_seconds: Maximum age in seconds

    Returns:
        True if snapshot.updated_at is within TTL, False otherwise

    Example:
        >>> snapshot = load_runtime_health(health_path)
        >>> if is_snapshot_fresh(snapshot, ttl_seconds=60.0):
        ...     print("Snapshot is fresh")
        ... else:
        ...     print("Snapshot is stale, run --health --probe")
    """
    if snapshot.updated_at is None:
        return False

    try:
        updated_at = datetime.fromisoformat(snapshot.updated_at)
    except (ValueError, TypeError):
        return False

    age = datetime.now(UTC) - updated_at
    return age <= timedelta(seconds=ttl_seconds)


def get_snapshot_age_seconds(snapshot: RuntimeHealthSnapshot) -> float | None:
    """Calculate snapshot age in seconds.

    Args:
        snapshot: Runtime health snapshot

    Returns:
        Age in seconds, or None if timestamp invalid

    Example:
        >>> age = get_snapshot_age_seconds(snapshot)
        >>> if age and age > 300:
        ...     print(f"Warning: Snapshot is {age:.1f} seconds old")
    """
    if snapshot.updated_at is None:
        return None

    try:
        updated_at = datetime.fromisoformat(snapshot.updated_at)
    except (ValueError, TypeError):
        return None

    return (datetime.now(UTC) - updated_at).total_seconds()
