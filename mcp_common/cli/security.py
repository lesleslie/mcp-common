"""Security utilities for CLI factory.

Provides file permission enforcement, cache ownership validation,
process validation for impersonation prevention, and atomic write operations.
"""

import json
import os
from pathlib import Path
from typing import Any

import psutil


def create_secure_cache_directory(cache_root: Path) -> None:
    """Create cache directory with secure permissions.

    Creates directory with mode 0o700 (rwx------, owner only) to prevent
    unauthorized access to PID files and snapshots.

    Args:
        cache_root: Path to .oneiric_cache directory
    """
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root.chmod(0o700)  # Owner read/write/execute only


def write_pid_file(pid_path: Path, pid: int) -> None:
    """Write PID file with secure permissions atomically.

    Creates PID file with mode 0o600 (rw-------, owner read/write only)
    using atomic tmp file + replace pattern for crash-safety.

    Args:
        pid_path: Path to PID file
        pid: Process ID to write
    """
    pid_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Atomic write: tmp file → replace
    tmp = pid_path.with_suffix(".tmp")
    tmp.write_text(str(pid))
    tmp.chmod(0o600)  # Owner read/write only
    tmp.replace(pid_path)


def validate_cache_ownership(cache_root: Path) -> None:
    """Validate cache directory is owned by current user.

    Prevents snapshot injection attacks if directory is world-writable
    or owned by another user.

    Args:
        cache_root: Path to .oneiric_cache directory

    Raises:
        PermissionError: If directory owned by another user
    """
    if not cache_root.exists():
        return

    stat = cache_root.stat()
    current_uid = os.getuid()

    if stat.st_uid != current_uid:
        msg = (
            f"Cache directory {cache_root} owned by UID {stat.st_uid}, "
            f"but current user is UID {current_uid}. "
            f"Refusing to use potentially compromised cache."
        )
        raise PermissionError(msg)


def is_process_alive(pid: int, server_name: str) -> bool:
    """Check if PID is alive and matches expected server.

    Validates both process existence and command line signature to
    prevent false positives from PID reuse.

    Args:
        pid: Process ID to check
        server_name: Expected server name (for command line validation)

    Returns:
        True if process is alive AND matches server signature
    """
    try:
        # Step 1: Check if PID exists (send null signal)
        os.kill(pid, 0)
    except ProcessLookupError:
        # Process doesn't exist
        return False
    except PermissionError:
        # Process exists but we can't signal it (owned by another user)
        # Conservative: assume alive
        return True

    # Step 2: Validate process command line (prevent impersonation)
    try:
        process = psutil.Process(pid)
        cmdline = " ".join(process.cmdline())

        # Check for server signature in command line
        server_slug = server_name.replace("-", "_")
        result = server_slug in cmdline or server_name in cmdline
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Can't validate, assume dead
        result = False

    return result


def validate_pid_integrity(
    pid: int,
    pid_path: Path,
    server_name: str,
) -> tuple[bool, str]:
    """Validate PID file points to legitimate server process.

    Prevents impersonation attacks with two-layer validation:
    1. Command line must match server signature
    2. Process start time must predate PID file creation

    Args:
        pid: Process ID from PID file
        pid_path: Path to PID file
        server_name: Expected server name

    Returns:
        (is_valid, reason) tuple
    """
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return (False, f"Process {pid} not found")

    # Check 1: Command line matches server signature
    try:
        cmdline = " ".join(process.cmdline())
        server_slug = server_name.replace("-", "_")

        if server_slug not in cmdline and server_name not in cmdline:
            return (
                False,
                f"Process {pid} command line does not match server '{server_name}': {cmdline}",
            )
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        # Can't read cmdline, conservative: assume invalid
        return (False, f"Cannot validate process {pid} (access denied)")

    # Check 2: Process start time predates PID file creation (prevent race)
    try:
        pid_file_mtime = pid_path.stat().st_mtime
        process_create_time = process.create_time()

        # PID file should be created AFTER process started
        # Allow 1 second tolerance for clock skew
        if process_create_time > pid_file_mtime + 1.0:
            return (False, f"Process {pid} started after PID file created (possible impersonation)")
    except (OSError, psutil.NoSuchProcess):
        # Can't validate timing, fail safe
        return (False, f"Cannot validate process {pid} timing")

    return (True, "Process validated")


def atomic_write_json(path: Path, data: dict[str, Any], mode: int = 0o600) -> None:
    """Atomically write JSON file with secure permissions.

    Uses tmp file + replace pattern for crash-safety during write.

    Args:
        path: Target file path
        data: JSON-serializable data
        mode: File permissions (octal, default 0o600)

    Raises:
        OSError: If write fails
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2))
        tmp.chmod(mode)
        tmp.replace(path)  # Atomic on POSIX systems
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
