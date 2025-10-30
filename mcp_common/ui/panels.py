"""Rich UI panels for MCP servers.

Provides beautiful terminal UI components using ACB console and Rich library.
"""

from __future__ import annotations

import typing as t
from datetime import datetime

from acb.console import console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class ServerPanels:
    """Rich UI panel components for MCP servers.

    Provides consistent, beautiful terminal output for common MCP server scenarios
    using ACB's console and Rich library.

    All methods are static and use ACB's pre-configured console singleton.

    Example:
        >>> from mcp_common.ui import ServerPanels
        >>>
        >>> # Show startup success
        >>> ServerPanels.startup_success(
        ...     server_name="Mailgun MCP",
        ...     version="1.0.0",
        ...     features=["Send Email", "Track Deliveries"]
        ... )
        >>>
        >>> # Show error
        >>> ServerPanels.error(
        ...     title="Configuration Error",
        ...     message="API key not found",
        ...     suggestion="Set MAILGUN_API_KEY environment variable"
        ... )
    """

    @staticmethod
    def startup_success(
        server_name: str,
        version: str | None = None,
        features: list[str] | None = None,
        endpoint: str | None = None,
        **metadata: t.Any,
    ) -> None:
        """Display successful server startup panel.

        Args:
            server_name: Display name of the MCP server
            version: Server version (optional)
            features: List of available features (optional)
            endpoint: HTTP endpoint if applicable (optional)
            **metadata: Additional metadata to display

        Example:
            >>> ServerPanels.startup_success(
            ...     server_name="Mailgun MCP",
            ...     version="2.0.0",
            ...     features=["Send Email", "Track Deliveries", "Manage Lists"],
            ...     endpoint="http://localhost:8000",
            ...     api_region="US"
            ... )
        """
        # Build content lines
        lines = [f"[bold green]✅ {server_name} started successfully![/bold green]"]

        if version:
            lines.append(f"[dim]Version:[/dim] {version}")

        if endpoint:
            lines.append(f"[dim]Endpoint:[/dim] {endpoint}")

        if features:
            lines.append("")
            lines.append("[bold]Available Features:[/bold]")
            for feature in features:
                lines.append(f"  • {feature}")

        if metadata:
            lines.append("")
            lines.append("[bold]Configuration:[/bold]")
            for key, value in metadata.items():
                # Format key nicely (snake_case -> Title Case)
                display_key = key.replace("_", " ").title()
                lines.append(f"  • {display_key}: {value}")

        lines.append("")
        lines.append(f"[dim]Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")

        # Create and print panel
        panel = Panel(
            "\n".join(lines),
            title=f"[bold]{server_name}[/bold]",
            border_style="green",
            padding=(1, 2),
        )
        console.print(panel)

    @staticmethod
    def error(
        title: str,
        message: str,
        suggestion: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """Display error panel with details and suggestions.

        Args:
            title: Error title
            message: Error message
            suggestion: Suggested fix (optional)
            error_type: Type of error (optional)

        Example:
            >>> ServerPanels.error(
            ...     title="API Key Missing",
            ...     message="Required API key not found in environment",
            ...     suggestion="Set MAILGUN_API_KEY environment variable",
            ...     error_type="ConfigurationError"
            ... )
        """
        lines = [f"[bold red]❌ {message}[/bold red]"]

        if error_type:
            lines.append(f"[dim]Type:[/dim] {error_type}")

        if suggestion:
            lines.append("")
            lines.append("[bold yellow]💡 Suggestion:[/bold yellow]")
            lines.append(f"   {suggestion}")

        panel = Panel(
            "\n".join(lines),
            title=f"[bold red]{title}[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
        console.print(panel)

    @staticmethod
    def warning(
        title: str,
        message: str,
        details: list[str] | None = None,
    ) -> None:
        """Display warning panel.

        Args:
            title: Warning title
            message: Warning message
            details: Additional warning details (optional)

        Example:
            >>> ServerPanels.warning(
            ...     title="Rate Limit Approaching",
            ...     message="90% of rate limit consumed",
            ...     details=["Current: 900/1000 requests", "Resets in: 45 minutes"]
            ... )
        """
        lines = [f"[bold yellow]⚠️  {message}[/bold yellow]"]

        if details:
            lines.append("")
            for detail in details:
                lines.append(f"  • {detail}")

        panel = Panel(
            "\n".join(lines),
            title=f"[bold yellow]{title}[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
        console.print(panel)

    @staticmethod
    def info(
        title: str,
        message: str,
        items: dict[str, str] | None = None,
    ) -> None:
        """Display informational panel.

        Args:
            title: Info panel title
            message: Info message
            items: Key-value items to display (optional)

        Example:
            >>> ServerPanels.info(
            ...     title="Server Status",
            ...     message="All systems operational",
            ...     items={
            ...         "Requests Processed": "1,234",
            ...         "Average Response": "45ms",
            ...         "Success Rate": "99.8%"
            ...     }
            ... )
        """
        lines = [f"[bold cyan]ℹ️  {message}[/bold cyan]"]

        if items:
            lines.append("")
            for key, value in items.items():
                lines.append(f"  • [dim]{key}:[/dim] {value}")

        panel = Panel(
            "\n".join(lines),
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(panel)

    @staticmethod
    def status_table(
        title: str,
        rows: list[tuple[str, str, str]],
        headers: tuple[str, str, str] = ("Component", "Status", "Details"),
    ) -> None:
        """Display status table.

        Args:
            title: Table title
            rows: List of (component, status, details) tuples
            headers: Column headers (default: Component, Status, Details)

        Example:
            >>> ServerPanels.status_table(
            ...     title="Health Check",
            ...     rows=[
            ...         ("API", "✅ Healthy", "Response: 23ms"),
            ...         ("Database", "✅ Healthy", "Connections: 5/20"),
            ...         ("Cache", "⚠️ Degraded", "Hit rate: 45%")
            ...     ]
            ... )
        """
        table = Table(title=title, show_header=True, header_style="bold")

        # Add columns
        table.add_column(headers[0], style="cyan", no_wrap=True)
        table.add_column(headers[1], style="white")
        table.add_column(headers[2], style="dim")

        # Add rows
        for component, status, details in rows:
            # Color status based on content
            if "✅" in status or "Healthy" in status:
                status_style = "green"
            elif "⚠️" in status or "Warning" in status or "Degraded" in status:
                status_style = "yellow"
            elif "❌" in status or "Error" in status or "Failed" in status:
                status_style = "red"
            else:
                status_style = "white"

            table.add_row(
                component,
                Text(status, style=status_style),
                details,
            )

        console.print(table)

    @staticmethod
    def feature_list(
        server_name: str,
        features: dict[str, str],
    ) -> None:
        """Display feature list table.

        Args:
            server_name: Name of the server
            features: Dictionary of feature names and descriptions

        Example:
            >>> ServerPanels.feature_list(
            ...     server_name="Mailgun MCP",
            ...     features={
            ...         "send_email": "Send transactional emails",
            ...         "track_delivery": "Track email delivery status",
            ...         "manage_lists": "Manage mailing lists",
            ...     }
            ... )
        """
        table = Table(
            title=f"{server_name} - Available Features",
            show_header=True,
            header_style="bold cyan",
        )

        table.add_column("Feature", style="green", no_wrap=True)
        table.add_column("Description", style="white")

        for feature, description in features.items():
            table.add_row(feature, description)

        console.print(table)

    @staticmethod
    def simple_message(
        message: str,
        style: str = "white",
    ) -> None:
        """Display simple colored message.

        Args:
            message: Message to display
            style: Rich style string (default: white)

        Example:
            >>> ServerPanels.simple_message("Server ready", style="green bold")
            >>> ServerPanels.simple_message("Warning: High memory usage", style="yellow")
        """
        console.print(f"[{style}]{message}[/{style}]")

    @staticmethod
    def separator(char: str = "─", count: int = 80) -> None:
        """Print a separator line.

        Args:
            char: Character to use for separator
            count: Number of characters

        Example:
            >>> ServerPanels.separator()
            >>> ServerPanels.separator(char="=", count=60)
        """
        console.print("[dim]" + (char * count) + "[/dim]")
