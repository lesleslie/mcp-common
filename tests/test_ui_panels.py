"""Tests for ServerPanels Rich UI components.

Note: These tests verify that panel methods execute without errors.
Visual output verification is done manually or with snapshot testing tools.
ACB's console singleton makes programmatic output capture complex in unit tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

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


@pytest.mark.unit
class TestServerPanelsConfigTable:
    """Tests for config_table method."""

    def test_config_table_basic(self) -> None:
        """Test basic configuration table."""
        ServerPanels.config_table(
            title="Server Configuration",
            items={
                "API Key": "sk-...abc123",
                "Region": "US-WEST",
                "Timeout": "30s",
            },
        )

    def test_config_table_with_various_types(self) -> None:
        """Test config table with different value types."""
        ServerPanels.config_table(
            title="Settings",
            items={
                "string": "value",
                "integer": 42,
                "boolean": True,
                "list": [1, 2, 3],
            },
        )


@pytest.mark.unit
class TestServerPanelsSimpleTable:
    """Tests for simple_table method."""

    def test_simple_table_basic(self) -> None:
        """Test basic simple table."""
        ServerPanels.simple_table(
            title="Data Table",
            headers=["Name", "Value", "Status"],
            rows=[
                ["Item 1", "100", "Active"],
                ["Item 2", "200", "Inactive"],
            ],
        )

    def test_simple_table_custom_border(self) -> None:
        """Test simple table with custom border style."""
        ServerPanels.simple_table(
            title="Custom Table",
            headers=["Col1", "Col2"],
            rows=[["A", "B"], ["C", "D"]],
            border_style="green",
        )


@pytest.mark.unit
class TestServerPanelsProcessList:
    """Tests for process_list method."""

    def test_process_list_with_dicts(self) -> None:
        """Test process list with dict entries."""
        processes = [
            {"pid": 1234, "memory_mb": 45.2, "cpu_percent": 12.5},
            {"pid": 5678, "memory_mb": 32.1, "cpu_percent": 8.3},
        ]
        ServerPanels.process_list(processes)

    def test_process_list_with_tuples(self) -> None:
        """Test process list with tuple entries."""
        processes = [
            (1234, 45.2, 12.5),
            (5678, 32.1, 8.3),
        ]
        ServerPanels.process_list(processes)

    def test_process_list_custom_title(self) -> None:
        """Test process list with custom title."""
        processes = [{"pid": 1234, "memory_mb": 45.2, "cpu_percent": 12.5}]
        ServerPanels.process_list(
            processes,
            title="Custom Process List",
        )

    def test_process_list_custom_headers(self) -> None:
        """Test process list with custom headers."""
        processes = [(1234, 45.2, 12.5)]
        ServerPanels.process_list(
            processes,
            title="Processes",
            headers=("ID", "Mem (MB)", "CPU"),
        )


@pytest.mark.unit
class TestServerPanelsStatusPanel:
    """Tests for status_panel method."""

    def test_status_panel_basic(self) -> None:
        """Test basic status panel."""
        ServerPanels.status_panel(
            title="Status",
            status_text="System operational",
        )

    def test_status_panel_with_description(self) -> None:
        """Test status panel with description."""
        ServerPanels.status_panel(
            title="Health Check",
            status_text="All systems healthy",
            description="All components are functioning normally",
        )

    def test_status_panel_with_items(self) -> None:
        """Test status panel with key-value items."""
        ServerPanels.status_panel(
            title="Metrics",
            status_text="Performance metrics",
            items={
                "Requests/sec": "1,234",
                "Response time": "45ms",
                "Error rate": "0.01%",
            },
        )

    def test_status_panel_severity_levels(self) -> None:
        """Test status panel with different severity levels."""
        for severity in ["success", "warning", "error", "info"]:
            ServerPanels.status_panel(
                title=f"{severity.title()} Status",
                status_text=f"This is a {severity} message",
                severity=severity,
            )

    def test_status_panel_complete(self) -> None:
        """Test status panel with all parameters."""
        ServerPanels.status_panel(
            title="Complete Status",
            status_text="Detailed status information",
            description="Additional context here",
            items={"Key": "Value", "Another": "Item"},
            severity="warning",
        )


@pytest.mark.unit
class TestServerPanelsBackupsTable:
    """Tests for backups_table method."""

    def test_backups_table_empty(self) -> None:
        """Test backups table with no backups."""
        ServerPanels.backups_table([])

    def test_backups_table_with_dicts(self) -> None:
        """Test backups table with dict entries."""
        backups = [
            {
                "id": "backup-123",
                "name": "Daily Backup",
                "profile": "production",
                "created_at": datetime.now(UTC),
                "description": "Automated daily backup",
            },
        ]
        ServerPanels.backups_table(backups)

    def test_backups_table_with_objects(self) -> None:
        """Test backups table with object entries."""

        class Backup:
            def __init__(self) -> None:
                self.id = "backup-456"
                self.name = "Weekly Backup"
                self.profile = "staging"
                self.created_at = datetime.now(UTC)
                self.description = "Weekly backup"

        backups = [Backup()]
        ServerPanels.backups_table(backups)

    def test_backups_table_custom_title(self) -> None:
        """Test backups table with custom title."""
        ServerPanels.backups_table(
            [
                {
                    "id": "123",
                    "name": "Test",
                    "profile": "dev",
                    "created_at": None,
                    "description": "",
                }
            ],
            title="Custom Backup List",
        )


@pytest.mark.unit
class TestServerPanelsServerStatusTable:
    """Tests for server_status_table method."""

    def test_server_status_table_basic(self) -> None:
        """Test basic server status table."""
        rows = [
            ("API Server", "Running", "1234", "Port 8000"),
            ("Worker", "Stopped", "5678", "Idle"),
        ]
        ServerPanels.server_status_table(rows)

    def test_server_status_table_custom_headers(self) -> None:
        """Test server status table with custom headers."""
        rows = [
            ("Service A", "Healthy", "9999", "OK"),
        ]
        ServerPanels.server_status_table(
            rows,
            headers=("Service", "Health", "Process", "Notes"),
        )

    def test_server_status_table_with_rich_markup(self) -> None:
        """Test server status table with Rich markup in status."""
        rows = [
            ("API", "[green]Running[/green]", "1234", "Active"),
            ("DB", "[red]Failed[/red]", "5678", "Connection lost"),
        ]
        ServerPanels.server_status_table(rows)

    def test_server_status_table_auto_colorization(self) -> None:
        """Test automatic status colorization."""
        rows = [
            ("Service 1", "Running", "1111", "Details"),
            ("Service 2", "Healthy", "2222", "Details"),
            ("Service 3", "Stopped", "3333", "Details"),
            ("Service 4", "Failed", "4444", "Details"),
            ("Service 5", "Warning", "5555", "Details"),
        ]
        ServerPanels.server_status_table(rows)


@pytest.mark.unit
class TestServerPanelsEndpointPanel:
    """Tests for endpoint_panel method."""

    def test_endpoint_panel_basic(self) -> None:
        """Test basic endpoint panel."""
        ServerPanels.endpoint_panel()

    def test_endpoint_panel_with_http(self) -> None:
        """Test endpoint panel with HTTP endpoint."""
        ServerPanels.endpoint_panel(
            http_endpoint="http://localhost:8000",
        )

    def test_endpoint_panel_with_websocket(self) -> None:
        """Test endpoint panel with WebSocket monitor."""
        ServerPanels.endpoint_panel(
            websocket_monitor="ws://localhost:8001",
        )

    def test_endpoint_panel_with_extras(self) -> None:
        """Test endpoint panel with extra items."""
        ServerPanels.endpoint_panel(
            http_endpoint="http://localhost:8000",
            websocket_monitor="ws://localhost:8001",
            extra={"GraphQL": "http://localhost:8000/graphql", "Health": "/health"},
        )

    def test_endpoint_panel_with_custom_severity(self) -> None:
        """Test endpoint panel with custom severity."""
        ServerPanels.endpoint_panel(
            http_endpoint="http://localhost:8000",
            severity="success",
        )


@pytest.mark.unit
class TestServerPanelsWarningPanel:
    """Tests for warning_panel method."""

    def test_warning_panel_basic(self) -> None:
        """Test basic warning panel."""
        ServerPanels.warning_panel(
            title="Warning",
            message="Something needs attention",
        )

    def test_warning_panel_with_description(self) -> None:
        """Test warning panel with description."""
        ServerPanels.warning_panel(
            title="Performance Warning",
            message="High memory usage",
            description="Memory usage is above 80% threshold",
        )

    def test_warning_panel_with_items(self) -> None:
        """Test warning panel with detail items."""
        ServerPanels.warning_panel(
            title="Rate Limit Warning",
            message="Approaching rate limit",
            items={
                "Current": "900/1000 requests",
                "Resets in": "45 minutes",
            },
        )


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

    def test_comprehensive_dashboard(self) -> None:
        """Test creating a comprehensive server dashboard."""
        # Server header
        ServerPanels.startup_success(
            server_name="Production MCP",
            version="2.0.0",
            features=["API", "WebSocket", "GraphQL"],
            endpoint="http://localhost:8000",
        )

        # Endpoints
        ServerPanels.endpoint_panel(
            http_endpoint="http://localhost:8000",
            websocket_monitor="ws://localhost:8001",
            extra={"Admin": "http://localhost:8000/admin"},
        )

        # Process list
        ServerPanels.process_list(
            [
                {"pid": 1234, "memory_mb": 128.5, "cpu_percent": 15.2},
                {"pid": 5678, "memory_mb": 64.3, "cpu_percent": 8.7},
            ],
            title="Active Processes",
        )

        # Status table
        ServerPanels.server_status_table(
            [
                ("API", "Running", "1234", "Healthy"),
                ("Worker", "Running", "5678", "Healthy"),
                ("Cache", "Healthy", "-", "Connected"),
            ],
            title="Component Status",
        )

        # Configuration
        ServerPanels.config_table(
            title="Configuration",
            items={
                "Environment": "production",
                "Debug Mode": False,
                "Log Level": "INFO",
            },
        )

        # Backups
        ServerPanels.backups_table(
            [
                {
                    "id": "backup-001",
                    "name": "Daily",
                    "profile": "prod",
                    "created_at": datetime.now(UTC),
                    "description": "Automated",
                }
            ],
            title="Recent Backups",
        )
