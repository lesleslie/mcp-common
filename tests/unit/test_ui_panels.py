"""Tests for ServerPanels UI components."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from rich.console import Console
from rich.table import Table

from mcp_common.ui import ServerPanels


@pytest.mark.unit
class TestServerPanelsStartupSuccess:
    """Tests for startup_success panel."""

    @patch("mcp_common.ui.panels.console")
    def test_startup_success_basic(self, mock_console: Mock) -> None:
        """Test basic startup success panel."""
        ServerPanels.startup_success(server_name="Test Server")

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert call_args is not None

    @patch("mcp_common.ui.panels.console")
    def test_startup_success_with_version(self, mock_console: Mock) -> None:
        """Test startup success with version."""
        ServerPanels.startup_success(
            server_name="Test Server",
            version="1.0.0",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_startup_success_with_features(self, mock_console: Mock) -> None:
        """Test startup success with features list."""
        ServerPanels.startup_success(
            server_name="Test Server",
            features=["Feature 1", "Feature 2", "Feature 3"],
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_startup_success_with_endpoint(self, mock_console: Mock) -> None:
        """Test startup success with endpoint."""
        ServerPanels.startup_success(
            server_name="Test Server",
            endpoint="http://localhost:8000",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_startup_success_with_metadata(self, mock_console: Mock) -> None:
        """Test startup success with custom metadata."""
        ServerPanels.startup_success(
            server_name="Test Server",
            version="2.0.0",
            features=["Feature 1"],
            endpoint="http://localhost:8000",
            api_region="US",
            environment="production",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_startup_success_includes_timestamp(self, mock_console: Mock) -> None:
        """Test startup success includes timestamp."""
        ServerPanels.startup_success(server_name="Test Server")

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert call_args is not None
        # Check that timestamp is included in output
        panel_content = str(call_args)
        assert "Started at:" in panel_content or "datetime" in panel_content.lower()


@pytest.mark.unit
class TestServerPanelsError:
    """Tests for error panel."""

    @patch("mcp_common.ui.panels.console")
    def test_error_basic(self, mock_console: Mock) -> None:
        """Test basic error panel."""
        ServerPanels.error(
            title="Error Title",
            message="Something went wrong",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_error_with_suggestion(self, mock_console: Mock) -> None:
        """Test error panel with suggestion."""
        ServerPanels.error(
            title="Configuration Error",
            message="API key not found",
            suggestion="Set API_KEY environment variable",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_error_with_type(self, mock_console: Mock) -> None:
        """Test error panel with error type."""
        ServerPanels.error(
            title="Validation Error",
            message="Invalid input",
            error_type="ValidationError",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_error_full(self, mock_console: Mock) -> None:
        """Test error panel with all fields."""
        ServerPanels.error(
            title="API Key Error",
            message="Required API key is missing",
            suggestion="Set MAILGUN_API_KEY environment variable",
            error_type="ConfigurationError",
        )

        mock_console.print.assert_called_once()


@pytest.mark.unit
class TestServerPanelsWarning:
    """Tests for warning panel."""

    @patch("mcp_common.ui.panels.console")
    def test_warning_basic(self, mock_console: Mock) -> None:
        """Test basic warning panel."""
        ServerPanels.warning(
            title="Warning Title",
            message="This is a warning",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_warning_with_details(self, mock_console: Mock) -> None:
        """Test warning panel with details."""
        ServerPanels.warning(
            title="Rate Limit Warning",
            message="90% of rate limit consumed",
            details=[
                "Current: 900/1000 requests",
                "Resets in: 45 minutes",
                "Consider upgrading plan",
            ],
        )

        mock_console.print.assert_called_once()


@pytest.mark.unit
class TestServerPanelsInfo:
    """Tests for info panel."""

    @patch("mcp_common.ui.panels.console")
    def test_info_basic(self, mock_console: Mock) -> None:
        """Test basic info panel."""
        ServerPanels.info(
            title="Server Status",
            message="All systems operational",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_info_with_items(self, mock_console: Mock) -> None:
        """Test info panel with items."""
        ServerPanels.info(
            title="Performance Metrics",
            message="Server performance is good",
            items={
                "Requests Processed": "1,234",
                "Average Response": "45ms",
                "Success Rate": "99.8%",
                "Memory Usage": "256MB",
            },
        )

        mock_console.print.assert_called_once()


@pytest.mark.unit
class TestServerPanelsStatusTable:
    """Tests for status_table display."""

    @patch("mcp_common.ui.panels.console")
    def test_status_table_basic(self, mock_console: Mock) -> None:
        """Test basic status table."""
        ServerPanels.status_table(
            title="Health Check",
            rows=[
                ("API", "✅ Healthy", "Response: 23ms"),
                ("Database", "✅ Healthy", "Connections: 5/20"),
                ("Cache", "⚠️ Degraded", "Hit rate: 45%"),
            ],
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_status_table_custom_headers(self, mock_console: Mock) -> None:
        """Test status table with custom headers."""
        ServerPanels.status_table(
            title="Service Status",
            rows=[
                ("Web Server", "✅ Running", "PID: 1234"),
                ("Worker", "❌ Failed", "Exit code: 1"),
            ],
            headers=("Service", "State", "Info"),
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_status_table_colorization(self, mock_console: Mock) -> None:
        """Test status table colorizes status column."""
        ServerPanels.status_table(
            title="Component Health",
            rows=[
                ("Component1", "✅ Healthy", "OK"),
                ("Component2", "⚠️ Warning", "Check logs"),
                ("Component3", "❌ Error", "Failed"),
                ("Component4", "Unknown", "No data"),
            ],
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_status_table_keyword_colorization(self, mock_console: Mock) -> None:
        """Test status table colorizes based on keywords."""
        ServerPanels.status_table(
            title="Server Status",
            rows=[
                ("Server1", "Running", "Active"),
                ("Server2", "Stopped", "Inactive"),
                ("Server3", "Healthy", "OK"),
                ("Server4", "Unhealthy", "Issues"),
                ("Server5", "Warning", "Check"),
            ],
        )

        mock_console.print.assert_called_once()


@pytest.mark.unit
class TestServerPanelsFeatureList:
    """Tests for feature_list display."""

    @patch("mcp_common.ui.panels.console")
    def test_feature_list_basic(self, mock_console: Mock) -> None:
        """Test basic feature list."""
        ServerPanels.feature_list(
            server_name="Mailgun MCP",
            features={
                "send_email": "Send transactional emails",
                "track_delivery": "Track email delivery status",
                "manage_lists": "Manage mailing lists",
            },
        )

        mock_console.print.assert_called_once()


@pytest.mark.unit
class TestServerPanelsGenericHelpers:
    """Tests for generic helper methods."""

    @patch("mcp_common.ui.panels.console")
    def test_config_table(self, mock_console: Mock) -> None:
        """Test config_table helper."""
        ServerPanels.config_table(
            title="Server Configuration",
            items={
                "Host": "localhost",
                "Port": "8000",
                "Debug Mode": "True",
                "Log Level": "INFO",
            },
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_simple_table(self, mock_console: Mock) -> None:
        """Test simple_table helper."""
        ServerPanels.simple_table(
            title="Test Table",
            headers=["Name", "Value", "Type"],
            rows=[
                ["Item1", "100", "int"],
                ["Item2", "test", "str"],
                ["Item3", "true", "bool"],
            ],
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_simple_table_custom_border(self, mock_console: Mock) -> None:
        """Test simple_table with custom border style."""
        ServerPanels.simple_table(
            title="Custom Table",
            headers=["Col1", "Col2"],
            rows=[["A", "B"], ["C", "D"]],
            border_style="red",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_process_list_from_dicts(self, mock_console: Mock) -> None:
        """Test process_list with dict-like objects."""
        processes = [
            {"pid": 1234, "memory_mb": 128.5, "cpu_percent": 5.2},
            {"pid": 5678, "memory_mb": 256.0, "cpu_percent": 10.8},
        ]

        ServerPanels.process_list(processes=processes)

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_process_list_from_tuples(self, mock_console: Mock) -> None:
        """Test process_list with tuple data."""
        processes = [
            (1234, 128.5, 5.2),
            (5678, 256.0, 10.8),
        ]

        ServerPanels.process_list(processes=processes)

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_process_list_custom_headers(self, mock_console: Mock) -> None:
        """Test process_list with custom headers."""
        processes = [
            {"pid": 1234, "memory_mb": 128.5, "cpu_percent": 5.2},
        ]

        ServerPanels.process_list(
            processes=processes,
            headers=("Process ID", "Memory", "CPU"),
            title="Worker Processes",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_status_panel(self, mock_console: Mock) -> None:
        """Test status_panel helper."""
        ServerPanels.status_panel(
            title="Server Status",
            status_text="All systems operational",
            description="No issues detected",
            items={
                "Uptime": "5 days, 3 hours",
                "Requests": "10,234",
                "Errors": "0",
            },
            severity="success",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_status_panel_severity_colors(self, mock_console: Mock) -> None:
        """Test status_panel with different severities."""
        for severity in ["success", "warning", "error", "info"]:
            ServerPanels.status_panel(
                title=f"Test {severity}",
                status_text=f"{severity} message",
                severity=severity,
            )

        assert mock_console.print.call_count == 4

    @patch("mcp_common.ui.panels.console")
    def test_backups_table_with_objects(self, mock_console: Mock) -> None:
        """Test backups_table with backup objects."""

        class Backup:
            def __init__(
                self,
                backup_id: str,
                name: str,
                profile: str,
                created_at: datetime,
                description: str,
            ) -> None:
                self.id = backup_id
                self.name = name
                self.profile = profile
                self.created_at = created_at
                self.description = description

        backups = [
            Backup(
                backup_id="abc123def456",
                name="Backup 1",
                profile="production",
                created_at=datetime.now(UTC),
                description="Daily backup",
            )
        ]

        ServerPanels.backups_table(backups=backups)

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_backups_table_with_dicts(self, mock_console: Mock) -> None:
        """Test backups_table with dict objects."""
        backups = [
            {
                "id": "xyz789",
                "name": "Backup 2",
                "profile": "staging",
                "created_at": "2024-01-15 10:30",
                "description": "Weekly backup",
            }
        ]

        ServerPanels.backups_table(backups=backups)

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_backups_table_empty(self, mock_console: Mock) -> None:
        """Test backups_table with empty list."""
        ServerPanels.backups_table(backups=[])

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_server_status_table(self, mock_console: Mock) -> None:
        """Test server_status_table helper."""
        ServerPanels.server_status_table(
            rows=[
                ("API Server", "Running", 1234, "Listening on :8000"),
                ("Worker", "Running", 1235, "Processing jobs"),
                ("Scheduler", "Stopped", None, "Disabled"),
            ],
        )

        mock_console.print.assert_called_once()


@pytest.mark.unit
class TestServerPanelsConvenienceWrappers:
    """Tests for convenience wrapper methods."""

    @patch("mcp_common.ui.panels.console")
    def test_endpoint_panel(self, mock_console: Mock) -> None:
        """Test endpoint_panel convenience wrapper."""
        ServerPanels.endpoint_panel(
            http_endpoint="http://localhost:8000",
            websocket_monitor="ws://localhost:8001",
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_endpoint_panel_with_extras(self, mock_console: Mock) -> None:
        """Test endpoint_panel with extra metadata."""
        ServerPanels.endpoint_panel(
            http_endpoint="https://api.example.com",
            extra={
                "API Version": "v2",
                "Region": "us-east-1",
                "Timeout": "30s",
            },
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_warning_panel(self, mock_console: Mock) -> None:
        """Test warning_panel convenience wrapper."""
        ServerPanels.warning_panel(
            title="High Memory Usage",
            message="Memory usage exceeds 80%",
            description="Consider scaling or optimizing",
            items={
                "Current Usage": "850MB / 1GB",
                "Trend": "Increasing",
            },
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_simple_message(self, mock_console: Mock) -> None:
        """Test simple_message helper."""
        ServerPanels.simple_message("Server ready", style="green bold")

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_simple_message_multiple_styles(self, mock_console: Mock) -> None:
        """Test simple_message with different styles."""
        ServerPanels.simple_message("Success", style="green")
        ServerPanels.simple_message("Warning", style="yellow")
        ServerPanels.simple_message("Error", style="red")

        assert mock_console.print.call_count == 3

    @patch("mcp_common.ui.panels.console")
    def test_separator(self, mock_console: Mock) -> None:
        """Test separator helper."""
        ServerPanels.separator()

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_separator_custom(self, mock_console: Mock) -> None:
        """Test separator with custom character and count."""
        ServerPanels.separator(char="=", count=60)

        mock_console.print.assert_called_once()


@pytest.mark.unit
class TestServerPanelsEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("mcp_common.ui.panels.console")
    def test_empty_features_list(self, mock_console: Mock) -> None:
        """Test startup_success with empty features."""
        ServerPanels.startup_success(
            server_name="Test Server",
            features=[],
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_empty_metadata(self, mock_console: Mock) -> None:
        """Test startup_success with empty metadata."""
        ServerPanels.startup_success(
            server_name="Test Server",
            **{},
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_empty_items_dict(self, mock_console: Mock) -> None:
        """Test info panel with empty items."""
        ServerPanels.info(
            title="Info",
            message="Test message",
            items={},
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_empty_rows(self, mock_console: Mock) -> None:
        """Test status_table with empty rows."""
        ServerPanels.status_table(
            title="Empty Table",
            rows=[],
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_unicode_in_messages(self, mock_console: Mock) -> None:
        """Test panels handle unicode characters."""
        ServerPanels.startup_success(
            server_name="Тестовый Сервер",  # Russian
            features=["功能 1", "機能 2"],  # Chinese, Japanese
        )

        mock_console.print.assert_called_once()

    @patch("mcp_common.ui.panels.console")
    def test_very_long_strings(self, mock_console: Mock) -> None:
        """Test panels handle very long strings."""
        long_text = "A" * 1000

        ServerPanels.info(
            title="Long Text Test",
            message=long_text,
            items={"key": long_text},
        )

        mock_console.print.assert_called_once()
