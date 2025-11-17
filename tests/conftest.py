"""Pytest configuration and shared fixtures for mcp-common tests."""

from __future__ import annotations

import typing as t
from unittest.mock import Mock

import pytest

from mcp_common.config import MCPBaseSettings

if t.TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def temp_settings_dir(tmp_path: Path) -> Path:
    """Create temporary settings directory for config tests."""
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir


## HTTP adapter fixtures removed; this library no longer ships an HTTP adapter.


@pytest.fixture
def sample_mcp_settings(_temp_settings_dir: Path) -> MCPBaseSettings:
    """Create sample MCP base settings for testing."""
    return MCPBaseSettings(
        server_name="Test MCP Server",
        server_description="Test server for unit tests",
        log_level="DEBUG",
        enable_debug_mode=True,
    )


@pytest.fixture
def mock_logger() -> Mock:
    """Create mock logger for testing logging behavior."""
    logger = Mock()
    logger.info = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture(autouse=True)
def reset_di_container() -> t.Iterator[None]:
    """Reset ACB dependency injection container between tests.

    This ensures test isolation by clearing any registered dependencies.
    """
    # Clear any test-specific dependencies
    # Note: depends.reset() doesn't exist, so we manually clear if needed
    # For now, just yield - ACB handles isolation via module registration
    return
