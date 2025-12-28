"""Rich UI panels for MCP servers.

Provides beautiful terminal UI components using Rich library.
"""

from __future__ import annotations

import typing as t
from datetime import UTC, datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Create console instance (Oneiric pattern - direct Rich usage)
console = Console()


class ServerPanels:
    """Rich UI panel components for MCP servers.

    Provides consistent, beautiful terminal output for common MCP server scenarios
    using Rich library.

    All methods are static and use a shared console instance.

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
            lines.extend(("", "[bold]Available Features:[/bold]"))
            lines.extend(f"  • {feature}" for feature in features)

        if metadata:
            lines.extend(("", "[bold]Configuration:[/bold]"))
            for key, value in metadata.items():
                # Format key nicely (snake_case -> Title Case)
                display_key = key.replace("_", " ").title()
                lines.append(f"  • {display_key}: {value}")

        lines.append("")
        start_time = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"[dim]Started at: {start_time}[/dim]")

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
            lines.extend(("", "[bold yellow]💡 Suggestion:[/bold yellow]"))
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
            lines.extend(f"  • {detail}" for detail in details)

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
        lines = [f"[bold cyan]i  {message}[/bold cyan]"]

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

    # --- Generic helpers for reusable tables/panels ----------------------

    @staticmethod
    def config_table(title: str, items: dict[str, t.Any]) -> None:
        """Display a simple key/value configuration table."""
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        for key, value in items.items():
            table.add_row(key, str(value))
        console.print(table)

    @staticmethod
    def simple_table(
        title: str,
        headers: list[str],
        rows: t.Sequence[t.Iterable[t.Any]],
        border_style: str = "cyan",
    ) -> None:
        """Display a generic table with provided headers and rows."""
        table = Table(title=title, show_header=True, header_style=f"bold {border_style}")
        for header in headers:
            table.add_column(header)
        for row in rows:
            table.add_row(*[str(col) for col in row])
        console.print(table)

    @staticmethod
    def process_list(
        processes: list[t.Mapping[str, t.Any]] | list[t.Iterable[t.Any]],
        *,
        title: str = "Running Processes",
        headers: tuple[str, str, str] = ("PID", "Memory (MB)", "CPU %"),
    ) -> None:
        """Display a standardized process list table.

        Accepts either a list of dict-like objects with keys 'pid', 'memory_mb',
        'cpu_percent', or a list of iterables ordered as (pid, memory_mb, cpu_percent).
        """
        rows: list[list[str]] = []
        for p in processes:
            if isinstance(p, dict):
                rows.append(
                    [
                        str(p.get("pid", "-")),
                        f"{p.get('memory_mb', 0):.1f}",
                        f"{p.get('cpu_percent', 0):.1f}",
                    ]
                )
            else:
                pid, mem, cpu = list(p)[:3]
                rows.append([str(pid), f"{float(mem):.1f}", f"{float(cpu):.1f}"])

        ServerPanels.simple_table(title=title, headers=list(headers), rows=rows)

    @staticmethod
    def status_panel(
        title: str,
        status_text: str,
        *,
        description: str | None = None,
        items: dict[str, t.Any] | None = None,
        severity: str = "info",
    ) -> None:
        """Display a standardized status panel with optional details.

        - severity: one of "success", "warning", "error", "info" controls border color
        - items: key/value lines to render under a Details section
        """
        color_map = {
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "info": "cyan",
        }
        lines: list[str] = [status_text]
        if description:
            lines.extend(("", description))
        if items:
            lines.extend(("", "[bold]Details:[/bold]"))
            for k, v in items.items():
                lines.append(f"  • [dim]{k}:[/dim] {v}")

        panel = Panel(
            "\n".join(lines),
            title=title,
            border_style=color_map.get(severity, "cyan"),
            padding=(1, 2),
        )
        console.print(panel)

    @staticmethod
    def backups_table(
        backups: list[t.Any],
        *,
        title: str = "Configuration Backups",
    ) -> None:
        """Display a backups table from a list of backup objects or dicts.

        Expects attributes/keys: id, name, profile, created_at, description.
        """
        if not backups:
            ServerPanels.info(title=title, message="No backups found")
            return

        def _get(obj: t.Any, key: str, default: t.Any = "") -> t.Any:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        rows: list[list[str]] = []
        for b in backups:
            bid = str(_get(b, "id", ""))[:8]
            name = str(_get(b, "name", ""))
            profile = _get(b, "profile", "")
            if hasattr(profile, "value"):
                profile = profile.value
            created = _get(b, "created_at", None)
            if isinstance(created, (datetime,)):
                created_str = created.strftime("%Y-%m-%d %H:%M")
            else:
                created_str = str(created) if created is not None else ""
            description = str(_get(b, "description", ""))
            rows.append([bid, name, str(profile), created_str, description])

        ServerPanels.simple_table(
            title=title,
            headers=["ID", "Name", "Profile", "Created", "Description"],
            rows=rows,
        )

    @staticmethod
    def server_status_table(
        rows: t.Sequence[t.Iterable[t.Any]],
        *,
        title: str = "Server Status",
        headers: tuple[str, ...] = ("Component", "Status", "PID", "Details"),
    ) -> None:
        """Display a server status table with best-effort colorization.

        If the status cell (second column) does not include Rich markup, simple
        keywords like 'Running', 'Stopped', 'Healthy', 'Unhealthy', 'Warning'
        will be colorized automatically.
        """
        table = Table(title=title, show_header=True, header_style="bold cyan")
        for h in headers:
            table.add_column(h)

        def style_status(val: str) -> Text:
            txt = val
            # If already contains Rich markup, keep as-is
            if "[" in txt and "]" in txt:
                return Text.from_markup(txt)
            lv = txt.lower()
            if any(k in lv for k in ("running", "healthy", "ok", "success")):
                return Text(txt, style="green")
            if any(k in lv for k in ("stopped", "failed", "error", "down", "unhealthy")):
                return Text(txt, style="red")
            if "warn" in lv or "degrad" in lv:
                return Text(txt, style="yellow")
            return Text(txt)

        status_col_index = 1
        min_status_cols = 2

        for row in rows:
            cells = list(row)
            if len(cells) >= min_status_cols:
                cells[status_col_index] = style_status(str(cells[status_col_index]))
            table.add_row(*[c if isinstance(c, Text) else str(c) for c in cells])

        console.print(table)

    # --- Additional convenience wrappers -----------------------------------

    @staticmethod
    def endpoint_panel(
        *,
        title: str = "Server Endpoints",
        http_endpoint: str | None = None,
        websocket_monitor: str | None = None,
        extra: dict[str, t.Any] | None = None,
        severity: str = "info",
    ) -> None:
        """Display a panel summarizing endpoints with optional extras."""
        items: dict[str, t.Any] = {}
        if http_endpoint:
            items["HTTP Endpoint"] = http_endpoint
        if websocket_monitor:
            items["WebSocket Monitor"] = websocket_monitor
        if extra:
            items.update(extra)
        ServerPanels.status_panel(
            title=title,
            status_text="[cyan]Endpoints[/cyan]",
            items=items,
            severity=severity,
        )

    @staticmethod
    def warning_panel(
        title: str,
        message: str,
        *,
        description: str | None = None,
        items: dict[str, t.Any] | None = None,
    ) -> None:
        """Shortcut for a warning-styled status panel."""
        ServerPanels.status_panel(
            title=title,
            status_text=message,
            description=description,
            items=items,
            severity="warning",
        )

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
