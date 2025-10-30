"""Tests for ServerPanels Rich UI components.

Note: These tests verify that panel methods execute without errors.
Visual output verification is done manually or with snapshot testing tools.
ACB's console singleton makes programmatic output capture complex in unit tests.
"""

from __future__ import annotations

import pytest

from mcp_common.ui import ServerPanels


@pytest.mark.unit
class TestServerPanelsStartup:
    """Tests for startup_success panel."""

    def test_startup_success_basic(self) -> None:
        """Test basic startup success panel executes without error."""
        ServerPanels.startup_success(
            server_name="Test MCP",
            version="1.0.0",
        )

    def test_startup_success_with_features(self) -> None:
        """Test startup panel with features list."""
        ServerPanels.startup_success(
            server_name="Feature MCP",
            version="2.0.0",
            features=["Feature A", "Feature B", "Feature C"],
        )

    def test_startup_success_with_endpoint(self) -> None:
        """Test startup panel with endpoint."""
        ServerPanels.startup_success(
            server_name="HTTP MCP",
            endpoint="http://localhost:8000",
        )

    def test_startup_success_with_metadata(self) -> None:
        """Test startup panel with metadata."""
        ServerPanels.startup_success(
            server_name="Config MCP",
            api_region="US",
            max_connections=100,
            enable_cache=True,
        )

    def test_startup_success_complete(self) -> None:
        """Test startup panel with all parameters."""
        ServerPanels.startup_success(
            server_name="Complete MCP",
            version="1.0.0",
            features=["Feature 1", "Feature 2"],
            endpoint="http://localhost:8000",
            region="US-WEST",
            debug_mode=True,
        )


@pytest.mark.unit
class TestServerPanelsError:
    """Tests for error panel."""

    def test_error_basic(self) -> None:
        """Test basic error panel."""
        ServerPanels.error(
            title="Configuration Error",
            message="API key not found",
        )

    def test_error_with_suggestion(self) -> None:
        """Test error panel with suggestion."""
        ServerPanels.error(
            title="API Error",
            message="Connection failed",
            suggestion="Check your network connection",
        )

    def test_error_with_type(self) -> None:
        """Test error panel with error type."""
        ServerPanels.error(
            title="Validation Error",
            message="Invalid configuration",
            error_type="ValueError",
        )

    def test_error_complete(self) -> None:
        """Test error panel with all parameters."""
        ServerPanels.error(
            title="Complete Error",
            message="Something went wrong",
            suggestion="Try restarting the server",
            error_type="RuntimeError",
        )


@pytest.mark.unit
class TestServerPanelsWarning:
    """Tests for warning panel."""

    def test_warning_basic(self) -> None:
        """Test basic warning panel."""
        ServerPanels.warning(
            title="Rate Limit Warning",
            message="Approaching rate limit",
        )

    def test_warning_with_details(self) -> None:
        """Test warning panel with details."""
        ServerPanels.warning(
            title="Performance Warning",
            message="High memory usage detected",
            details=["Current: 900MB", "Limit: 1GB", "Threshold: 90%"],
        )


@pytest.mark.unit
class TestServerPanelsInfo:
    """Tests for info panel."""

    def test_info_basic(self) -> None:
        """Test basic info panel."""
        ServerPanels.info(
            title="Server Status",
            message="All systems operational",
        )

    def test_info_with_items(self) -> None:
        """Test info panel with key-value items."""
        ServerPanels.info(
            title="Statistics",
            message="Current metrics",
            items={
                "Requests": "1,234",
                "Response Time": "45ms",
                "Success Rate": "99.8%",
            },
        )


@pytest.mark.unit
class TestServerPanelsStatusTable:
    """Tests for status_table panel."""

    def test_status_table_basic(self) -> None:
        """Test basic status table."""
        ServerPanels.status_table(
            title="Health Check",
            rows=[
                ("API", "✅ Healthy", "Response: 23ms"),
                ("Database", "✅ Healthy", "Connections: 5/20"),
                ("Cache", "⚠️ Degraded", "Hit rate: 45%"),
            ],
        )

    def test_status_table_custom_headers(self) -> None:
        """Test status table with custom headers."""
        ServerPanels.status_table(
            title="Services",
            rows=[
                ("Service A", "Running", "Port 8001"),
                ("Service B", "Running", "Port 8002"),
            ],
            headers=("Service", "State", "Info"),
        )


@pytest.mark.unit
class TestServerPanelsFeatureList:
    """Tests for feature_list table."""

    def test_feature_list(self) -> None:
        """Test feature list table."""
        ServerPanels.feature_list(
            server_name="Test MCP",
            features={
                "send_email": "Send transactional emails",
                "track_delivery": "Track email delivery status",
                "manage_lists": "Manage mailing lists",
            },
        )


@pytest.mark.unit
class TestServerPanelsUtilities:
    """Tests for utility methods."""

    def test_simple_message(self) -> None:
        """Test simple message output."""
        ServerPanels.simple_message("Test message", style="green")

    def test_simple_message_default_style(self) -> None:
        """Test simple message with default style."""
        ServerPanels.simple_message("Default style message")

    def test_separator(self) -> None:
        """Test separator line."""
        ServerPanels.separator()

    def test_separator_custom(self) -> None:
        """Test separator with custom character."""
        ServerPanels.separator(char="=", count=40)


@pytest.mark.integration
class TestServerPanelsIntegration:
    """Integration tests for ServerPanels workflow."""

    def test_complete_startup_workflow(self) -> None:
        """Test complete server startup workflow."""
        # Startup message
        ServerPanels.startup_success(
            server_name="Integration MCP",
            version="1.0.0",
            features=["Feature 1", "Feature 2"],
            endpoint="http://localhost:8000",
        )

        # Status check
        ServerPanels.status_table(
            title="Initial Health Check",
            rows=[
                ("API", "✅ Healthy", "Ready"),
                ("Cache", "✅ Healthy", "Connected"),
            ],
        )

        # Info message
        ServerPanels.info(
            title="Ready",
            message="Server ready to accept requests",
        )

    def test_error_handling_workflow(self) -> None:
        """Test error handling workflow."""
        # Warning
        ServerPanels.warning(
            title="Configuration Issue",
            message="Missing optional setting",
            details=["Using default value"],
        )

        # Error
        ServerPanels.error(
            title="Startup Failed",
            message="Cannot connect to database",
            suggestion="Check database connection string",
            error_type="ConnectionError",
        )
