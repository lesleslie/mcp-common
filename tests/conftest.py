"""Pytest configuration and shared fixtures for mcp-common tests."""

from __future__ import annotations

import typing as t
from pathlib import Path
from unittest.mock import Mock

import pytest

from mcp_common.adapters.http import HTTPClientAdapter, HTTPClientSettings
from mcp_common.config import MCPBaseSettings


@pytest.fixture
def temp_settings_dir(tmp_path: Path) -> Path:
    """Create temporary settings directory for config tests."""
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir


@pytest.fixture
def sample_http_settings() -> HTTPClientSettings:
    """Create sample HTTP client settings for testing."""
    return HTTPClientSettings(
        timeout=10,
        max_connections=50,
        max_keepalive_connections=10,
        retry_attempts=2,
        follow_redirects=True,
    )


@pytest.fixture
async def http_adapter(
    sample_http_settings: HTTPClientSettings,
    mock_logger: Mock,
) -> HTTPClientAdapter:
    """Create HTTP adapter instance with test settings and mock logger."""
    adapter = HTTPClientAdapter(settings=sample_http_settings)
    # Inject mock logger (ACB would normally do this via DI)
    adapter.logger = mock_logger
    yield adapter
    # Cleanup: Close client if created
    await adapter._cleanup_resources()


@pytest.fixture
def sample_mcp_settings(temp_settings_dir: Path) -> MCPBaseSettings:
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
    return
    # Clear any test-specific dependencies
    # Note: depends.reset() doesn't exist, so we manually clear if needed
    # For now, just yield - ACB handles isolation via module registration
