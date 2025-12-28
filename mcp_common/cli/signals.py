"""Signal handler for graceful server shutdown.

Handles SIGTERM, SIGINT for graceful shutdown and optionally SIGHUP
for configuration reload.
"""

import contextlib
import signal
import sys
from collections.abc import Callable
from typing import Any


class SignalHandler:
    """Signal handler for graceful shutdown.

    Registers handlers for SIGTERM and SIGINT to enable graceful shutdown,
    and optionally SIGHUP for configuration reload without restart.

    Example:
        >>> def shutdown():
        ...     print("Shutting down gracefully...")
        ...     # Cleanup resources, update snapshots, remove PID file
        ...
        >>> handler = SignalHandler(on_shutdown=shutdown)
        >>> handler.register()
        >>> # Server runs... on SIGTERM/SIGINT, shutdown() is called
    """

    def __init__(
        self,
        on_shutdown: Callable[[], None],
        on_reload: Callable[[], None] | None = None,
    ) -> None:
        """Initialize signal handler.

        Args:
            on_shutdown: Callback invoked on SIGTERM/SIGINT for graceful shutdown
            on_reload: Optional callback for SIGHUP configuration reload
        """
        self.on_shutdown = on_shutdown
        self.on_reload = on_reload
        self._shutdown_called = False

    def register(self) -> None:
        """Register signal handlers for SIGTERM, SIGINT, and optionally SIGHUP."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        if self.on_reload is not None:
            signal.signal(signal.SIGHUP, self._handle_reload)

    def _handle_shutdown(self, _signum: int, _frame: Any) -> None:
        """Handle SIGTERM/SIGINT for graceful shutdown.

        Only calls on_shutdown once - subsequent signals are ignored to
        prevent double-shutdown issues.

        Args:
            _signum: Signal number (SIGTERM or SIGINT, unused)
            _frame: Current stack frame (unused)
        """
        if self._shutdown_called:
            return

        self._shutdown_called = True

        try:
            self.on_shutdown()
        except Exception:
            sys.exit(1)

        sys.exit(0)

    def _handle_reload(self, _signum: int, _frame: Any) -> None:
        """Handle SIGHUP for configuration reload.

        Args:
            _signum: Signal number (SIGHUP, unused)
            _frame: Current stack frame (unused)
        """
        if self.on_reload is None:
            return

        with contextlib.suppress(Exception):
            self.on_reload()
