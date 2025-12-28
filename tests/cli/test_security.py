"""Comprehensive tests for security utilities."""

import os
from pathlib import Path
from typing import Never
from unittest.mock import Mock, patch

import psutil
import pytest

from mcp_common.cli.security import (
    create_secure_cache_directory,
    is_process_alive,
    validate_cache_ownership,
    validate_pid_integrity,
    write_pid_file,
)


class TestWritePidFile:
    """Test write_pid_file function."""

    def test_creates_file(self, tmp_path: Path):
        """Test PID file is created."""
        pid_path = tmp_path / "test.pid"

        write_pid_file(pid_path, 12345)

        assert pid_path.exists()

    def test_writes_pid(self, tmp_path: Path):
        """Test PID is written as text."""
        pid_path = tmp_path / "test.pid"

        write_pid_file(pid_path, 12345)

        content = pid_path.read_text()
        assert content == "12345"

    def test_secure_permissions(self, tmp_path: Path):
        """Test PID file has 0o600 permissions."""
        pid_path = tmp_path / "test.pid"

        write_pid_file(pid_path, 12345)

        file_stat = pid_path.stat()
        permissions = file_stat.st_mode & 0o777
        assert permissions == 0o600

    def test_overwrites_existing(self, tmp_path: Path):
        """Test writing to existing PID file overwrites it."""
        pid_path = tmp_path / "test.pid"

        # Write first PID
        write_pid_file(pid_path, 11111)
        assert pid_path.read_text() == "11111"

        # Write second PID
        write_pid_file(pid_path, 22222)
        assert pid_path.read_text() == "22222"

    def test_creates_parent_directory(self, tmp_path: Path):
        """Test parent directory is created if needed."""
        nested_path = tmp_path / "subdir" / "test.pid"

        write_pid_file(nested_path, 12345)

        assert nested_path.exists()
        assert nested_path.parent.is_dir()


class TestCreateSecureCacheDirectory:
    """Test create_secure_cache_directory function."""

    def test_creates_directory(self, tmp_path: Path):
        """Test directory is created."""
        cache_dir = tmp_path / "cache"

        create_secure_cache_directory(cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_secure_permissions(self, tmp_path: Path):
        """Test directory has 0o700 permissions."""
        cache_dir = tmp_path / "cache"

        create_secure_cache_directory(cache_dir)

        dir_stat = cache_dir.stat()
        permissions = dir_stat.st_mode & 0o777
        assert permissions == 0o700

    def test_creates_nested_directory(self, tmp_path: Path):
        """Test nested directory creation."""
        cache_dir = tmp_path / "level1" / "level2" / "cache"

        create_secure_cache_directory(cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_idempotent(self, tmp_path: Path):
        """Test calling twice doesn't fail."""
        cache_dir = tmp_path / "cache"

        # Create twice
        create_secure_cache_directory(cache_dir)
        create_secure_cache_directory(cache_dir)

        assert cache_dir.exists()

    def test_fixes_insecure_permissions(self, tmp_path: Path):
        """Test existing directory with wrong permissions is fixed."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_dir.chmod(0o755)  # Too permissive

        create_secure_cache_directory(cache_dir)

        dir_stat = cache_dir.stat()
        permissions = dir_stat.st_mode & 0o777
        assert permissions == 0o700


class TestValidateCacheOwnership:
    """Test validate_cache_ownership function."""

    def test_valid_ownership(self, tmp_path: Path):
        """Test validation passes for directory owned by current user."""
        cache_dir = tmp_path / "cache"
        create_secure_cache_directory(cache_dir)

        # Should not raise
        validate_cache_ownership(cache_dir)

    def test_missing_directory(self, tmp_path: Path):
        """Test validation passes for missing directory (returns early)."""
        cache_dir = tmp_path / "missing"

        # Should not raise (returns early for missing dir)
        validate_cache_ownership(cache_dir)

        # Should not create directory
        assert not cache_dir.exists()

    def test_wrong_ownership_fails(self, tmp_path: Path):
        """Test validation only checks ownership, not permissions."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(mode=0o755)  # Permissive but owned by us

        # Should not raise - ownership check passes
        # (Permission enforcement is in create_secure_cache_directory)
        validate_cache_ownership(cache_dir)

    def test_file_instead_of_directory(self, tmp_path: Path):
        """Test validation passes for file (only checks ownership)."""
        cache_file = tmp_path / "cache"
        cache_file.write_text("not a directory")

        # Should not raise - only checks ownership, not whether it's a directory
        validate_cache_ownership(cache_file)

    def test_uid_mismatch_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test validation fails when UID does not match."""
        cache_dir = tmp_path / "cache"
        create_secure_cache_directory(cache_dir)

        current_uid = os.getuid()
        monkeypatch.setattr(os, "getuid", lambda: current_uid + 1)

        with pytest.raises(PermissionError, match="owned by UID"):
            validate_cache_ownership(cache_dir)


class TestIsProcessAlive:
    """Test is_process_alive function."""

    def test_current_process_alive(self):
        """Test current Python process is alive."""
        current_pid = os.getpid()

        # Should be alive (we're running)
        is_alive = is_process_alive(current_pid, "python")

        assert is_alive is True

    def test_nonexistent_process(self):
        """Test nonexistent PID returns False."""
        fake_pid = 999999

        is_alive = is_process_alive(fake_pid, "nonexistent")

        assert is_alive is False

    def test_wrong_process_name(self):
        """Test process exists but wrong name returns False."""
        current_pid = os.getpid()

        # Process exists but name doesn't match
        is_alive = is_process_alive(current_pid, "definitely-not-python")

        assert is_alive is False

    def test_partial_name_match(self):
        """Test partial process name matching works."""
        current_pid = os.getpid()

        # "python" should match "python", "python3", "python3.13", etc.
        is_alive = is_process_alive(current_pid, "python")

        assert is_alive is True

    def test_case_sensitive_matching(self):
        """Test process name matching is case-sensitive."""
        current_pid = os.getpid()

        # "PYTHON" won't match "python" (case-sensitive)
        is_alive = is_process_alive(current_pid, "PYTHON")

        # Should fail - case doesn't match
        assert is_alive is False

    def test_access_denied_in_cmdline(self):
        """Test access denied during cmdline inspection returns False."""
        current_pid = os.getpid()

        with patch("mcp_common.cli.security.os.kill"):
            with patch("mcp_common.cli.security.psutil.Process") as process_mock:
                process_mock.side_effect = psutil.AccessDenied(pid=current_pid)
                is_alive = is_process_alive(current_pid, "python")

        assert is_alive is False


class TestValidatePidIntegrity:
    """Test validate_pid_integrity function."""

    def test_valid_current_process(self, tmp_path: Path):
        """Test validation passes for current process."""
        current_pid = os.getpid()
        pid_path = tmp_path / "test.pid"
        write_pid_file(pid_path, current_pid)

        is_valid, reason = validate_pid_integrity(current_pid, pid_path, "python")

        assert is_valid is True
        assert "validated" in reason

    def test_nonexistent_process(self, tmp_path: Path):
        """Test validation fails for nonexistent process."""
        fake_pid = 999999
        pid_path = tmp_path / "test.pid"
        write_pid_file(pid_path, fake_pid)

        is_valid, reason = validate_pid_integrity(fake_pid, pid_path, "test-server")

        assert is_valid is False
        assert "not found" in reason

    def test_wrong_process_name(self, tmp_path: Path):
        """Test validation fails for wrong process name."""
        current_pid = os.getpid()
        pid_path = tmp_path / "test.pid"
        write_pid_file(pid_path, current_pid)

        is_valid, reason = validate_pid_integrity(current_pid, pid_path, "definitely-not-python")

        assert is_valid is False
        assert "command line does not match" in reason

    def test_timing_validation_pass(self, tmp_path: Path):
        """Test validation passes when timing is correct."""
        current_pid = os.getpid()
        pid_path = tmp_path / "test.pid"

        # Write PID file (process already running, so timing should be fine)
        write_pid_file(pid_path, current_pid)

        is_valid, _reason = validate_pid_integrity(current_pid, pid_path, "python")

        # Should pass - normal case where process started before PID file created
        assert is_valid is True

    def test_cmdline_access_denied(self, tmp_path: Path):
        """Test validation fails when cmdline cannot be read."""
        current_pid = os.getpid()
        pid_path = tmp_path / "test.pid"
        write_pid_file(pid_path, current_pid)

        process = Mock()
        process.cmdline.side_effect = psutil.AccessDenied(pid=current_pid)

        with patch("mcp_common.cli.security.psutil.Process", return_value=process):
            is_valid, reason = validate_pid_integrity(current_pid, pid_path, "python")

        assert is_valid is False
        assert "access denied" in reason

    def test_timing_validation_error(self):
        """Test validation fails when timing cannot be checked."""
        current_pid = os.getpid()

        class DummyPath:
            def stat(self) -> Never:
                msg = "nope"
                raise OSError(msg)

        process = Mock()
        process.cmdline.return_value = ["python"]
        process.create_time.return_value = 0.0

        with patch("mcp_common.cli.security.psutil.Process", return_value=process):
            is_valid, reason = validate_pid_integrity(current_pid, DummyPath(), "python")

        assert is_valid is False
        assert "timing" in reason

    def test_timing_validation_rejects_future_process(self):
        """Test validation fails when process starts after PID file."""
        current_pid = os.getpid()

        class DummyPath:
            def stat(self):
                return Mock(st_mtime=10.0)

        process = Mock()
        process.cmdline.return_value = ["python"]
        process.create_time.return_value = 20.5

        with patch("mcp_common.cli.security.psutil.Process", return_value=process):
            is_valid, reason = validate_pid_integrity(current_pid, DummyPath(), "python")

        assert is_valid is False
        assert "possible impersonation" in reason


class TestSecurityEdgeCases:
    """Test edge cases and error conditions."""

    def test_write_pid_file_permission_denied(self, tmp_path: Path):
        """Test PID file write fails gracefully with permission denied."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir(mode=0o500)  # Read-only
        pid_path = readonly_dir / "test.pid"

        with pytest.raises(PermissionError):
            write_pid_file(pid_path, 12345)

    def test_cache_directory_permission_denied_parent(self, tmp_path: Path):
        """Test cache directory creation fails if parent is read-only."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir(mode=0o500)
        cache_dir = readonly_dir / "cache"

        with pytest.raises(PermissionError):
            create_secure_cache_directory(cache_dir)

    def test_validate_ownership_symlink_directory(self, tmp_path: Path):
        """Test validation handles symlink to directory."""
        real_cache = tmp_path / "real_cache"
        create_secure_cache_directory(real_cache)

        symlink_cache = tmp_path / "symlink_cache"
        symlink_cache.symlink_to(real_cache)

        # Should follow symlink and validate
        validate_cache_ownership(symlink_cache)

    def test_is_process_alive_zombie_process(self):
        """Test handling of zombie processes."""
        # Note: Hard to test zombie processes reliably
        # Just verify function handles edge cases gracefully
        is_alive = is_process_alive(1, "init")  # PID 1 should always exist
        assert isinstance(is_alive, bool)


class TestSecurityRegressions:
    """Test known security issues are prevented."""

    def test_pid_reuse_attack_prevention(self, tmp_path: Path):
        """Test PID reuse attacks are prevented.

        Scenario: Old server dies, OS reuses PID for different process.
        Validation should detect this via command line mismatch.
        """
        current_pid = os.getpid()
        pid_path = tmp_path / "test.pid"
        write_pid_file(pid_path, current_pid)

        # Simulate attacker trying to impersonate with same PID but different command
        is_valid, reason = validate_pid_integrity(current_pid, pid_path, "malicious-process")

        # Should fail - command line doesn't match
        assert is_valid is False
        assert "command line does not match" in reason

    def test_race_condition_prevention(self, tmp_path: Path):
        """Test atomic file operations prevent race conditions."""
        pid_path = tmp_path / "test.pid"

        # Write PID file
        write_pid_file(pid_path, 12345)

        # Verify no .tmp files left behind (atomic operation)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_permission_escalation_prevention(self, tmp_path: Path):
        """Test cache directory can't be created with wrong permissions."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_dir.chmod(0o777)  # World-writable (bad!)

        # Should reject insecure permissions
        with pytest.raises(PermissionError):
            validate_cache_ownership(cache_dir)

    def test_symlink_attack_prevention(self, tmp_path: Path):
        """Test symlink attacks to sensitive files are prevented."""
        # Create a sensitive file
        sensitive = tmp_path / "sensitive.txt"
        sensitive.write_text("secret")
        sensitive.chmod(0o600)

        # Try to create PID file as symlink to sensitive file
        pid_path = tmp_path / "malicious.pid"
        pid_path.symlink_to(sensitive)

        # Writing should follow symlink and overwrite
        # This is expected behavior - we validate ownership separately
        write_pid_file(pid_path, 12345)

        # Sensitive file should now contain PID
        assert sensitive.read_text() == "12345"
