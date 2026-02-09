"""Custom exceptions for prompting adapter."""

from mcp_common.prompting.models import NotificationLevel


class PromptAdapterError(Exception):
    """Base exception for prompting adapter errors."""

    def __init__(self, message: str, backend: str | None = None):
        """Initialize prompt adapter error.

        Args:
            message: Error message
            backend: Backend that raised the error (optional)
        """
        self.backend = backend
        self.message = message
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with backend information."""
        if self.backend:
            return f"[{self.backend}] {self.message}"
        return self.message


class BackendUnavailableError(PromptAdapterError):
    """Raised when a requested backend is not available.

    This typically occurs when:
    - Backend dependencies are not installed
    - Backend is not supported on the current platform
    - Backend failed to initialize
    """

    def __init__(
        self,
        backend: str,
        reason: str | None = None,
        install_hint: str | None = None,
    ):
        """Initialize backend unavailable error.

        Args:
            backend: Backend name that is unavailable
            reason: Reason why backend is unavailable (optional)
            install_hint: Installation hint (optional)
        """
        self.backend = backend
        self.reason = reason
        self.install_hint = install_hint

        message = f"Backend '{backend}' is not available"
        if reason:
            message += f": {reason}"
        if install_hint:
            message += f"\n{install_hint}"

        super().__init__(message, backend=backend)


class DialogDisplayError(PromptAdapterError):
    """Raised when a dialog fails to display."""

    def __init__(
        self,
        backend: str,
        dialog_type: str,
        reason: str | None = None,
    ):
        """Initialize dialog display error.

        Args:
            backend: Backend that failed
            dialog_type: Type of dialog (e.g., "alert", "confirm")
            reason: Reason for failure (optional)
        """
        self.dialog_type = dialog_type
        self.reason = reason

        message = f"Failed to display {dialog_type} dialog"
        if reason:
            message += f": {reason}"

        super().__init__(message, backend=backend)


class NotificationError(PromptAdapterError):
    """Raised when a notification fails to send."""

    def __init__(
        self,
        backend: str,
        title: str,
        reason: str | None = None,
        level: NotificationLevel = NotificationLevel.INFO,
    ):
        """Initialize notification error.

        Args:
            backend: Backend that failed
            title: Notification title
            reason: Reason for failure (optional)
            level: Notification level
        """
        self.title = title
        self.reason = reason
        self.level = level

        message = f"Failed to send notification '{title}'"
        if reason:
            message += f": {reason}"

        super().__init__(message, backend=backend)


class UserCancelledError(PromptAdapterError):
    """Raised when user cancels a prompt (not an error, but useful control flow)."""

    def __init__(self, backend: str, prompt_type: str = "prompt"):
        """Initialize user cancelled error.

        Args:
            backend: Backend that was used
            prompt_type: Type of prompt (e.g., "text", "choice")
        """
        self.prompt_type = prompt_type
        super().__init__(f"User cancelled {prompt_type} prompt", backend=backend)


class ValidationError(PromptAdapterError):
    """Raised when user input fails validation."""

    def __init__(self, backend: str, field: str, value: str, reason: str):
        """Initialize validation error.

        Args:
            backend: Backend that was used
            field: Field name that failed validation
            value: The invalid value
            reason: Reason why validation failed
        """
        self.field = field
        self.value = value
        self.reason = reason

        message = f"Validation failed for '{field}': {reason}"
        super().__init__(message, backend=backend)
