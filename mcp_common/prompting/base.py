"""Abstract base interface for prompting backends."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mcp_common.prompting.models import DialogResult, NotificationLevel

if TYPE_CHECKING:
    from pathlib import Path


class PromptBackend(ABC):
    """Abstract base class for prompting backends.

    All backends must implement these methods to provide a unified interface
    for user interaction across different platforms and UI frameworks.
    """

    @abstractmethod
    async def alert(
        self,
        title: str,
        message: str,
        detail: str | None = None,
        buttons: list[str] | None = None,
        default_button: str | None = None,
        style: str = "info",
    ) -> DialogResult:
        """Display an alert dialog with optional buttons.

        Args:
            title: Dialog title
            message: Primary message
            detail: Additional detailed information (optional)
            buttons: List of button labels (default: ["OK"])
            default_button: Label of default button (optional)
            style: Dialog style (info, warning, error)

        Returns:
            DialogResult with clicked button

        Raises:
            BackendUnavailableError: If backend cannot be used
            PromptAdapterError: If dialog fails to display
        """
        pass

    @abstractmethod
    async def confirm(
        self,
        title: str,
        message: str,
        default: bool = False,
        yes_label: str = "Yes",
        no_label: str = "No",
    ) -> bool:
        """Display a confirmation dialog (Yes/No).

        Args:
            title: Dialog title
            message: Confirmation message
            default: Default selection (True=Yes, False=No)
            yes_label: Label for yes button
            no_label: Label for no button

        Returns:
            True if user clicked Yes, False if No

        Raises:
            BackendUnavailableError: If backend cannot be used
            PromptAdapterError: If dialog fails to display
        """
        pass

    @abstractmethod
    async def prompt_text(
        self,
        title: str,
        message: str,
        default: str = "",
        placeholder: str = "",
        secure: bool = False,
    ) -> str | None:
        """Prompt user for text input.

        Args:
            title: Dialog title
            message: Prompt message
            default: Default text value
            placeholder: Placeholder text
            secure: If True, use password masking

        Returns:
            User input text, or None if cancelled

        Raises:
            BackendUnavailableError: If backend cannot be used
            PromptAdapterError: If prompt fails to display
        """
        pass

    @abstractmethod
    async def prompt_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        default: str | None = None,
    ) -> str | None:
        """Prompt user to select from a list of choices.

        Args:
            title: Dialog title
            message: Prompt message
            choices: List of choices to display
            default: Default selection (optional)

        Returns:
            Selected choice, or None if cancelled

        Raises:
            BackendUnavailableError: If backend cannot be used
            PromptAdapterError: If prompt fails to display
        """
        pass

    @abstractmethod
    async def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        sound: bool = True,
    ) -> bool:
        """Send a system notification.

        Args:
            title: Notification title
            message: Notification message
            level: Notification level (info, warning, error)
            sound: Whether to play notification sound

        Returns:
            True if notification was delivered successfully

        Raises:
            BackendUnavailableError: If backend cannot be used
            PromptAdapterError: If notification fails to send
        """
        pass

    @abstractmethod
    async def select_file(
        self,
        title: str,
        allowed_types: list[str] | None = None,
        multiple: bool = False,
    ) -> "list[Path] | None":
        """Display file selection dialog.

        Args:
            title: Dialog title
            allowed_types: File extensions to allow (e.g., ["py", "txt"])
            multiple: Allow multiple file selection

        Returns:
            List of selected file paths, or None if cancelled

        Raises:
            BackendUnavailableError: If backend cannot be used
            PromptAdapterError: If dialog fails to display
        """
        pass

    @abstractmethod
    async def select_directory(
        self,
        title: str,
    ) -> "Path | None":
        """Display directory selection dialog.

        Args:
            title: Dialog title

        Returns:
            Selected directory path, or None if cancelled

        Raises:
            BackendUnavailableError: If backend cannot be used
            PromptAdapterError: If dialog fails to display
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current platform.

        Returns:
            True if backend can be used, False otherwise
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize backend resources.

        This method is called when the backend is first created to load
        resources, validate configuration, or establish connections.

        Raises:
            BackendUnavailableError: If backend cannot be initialized
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup backend resources.

        This method is called when the backend is no longer needed to release
        resources, close connections, or perform cleanup.

        Implementations should be idempotent (safe to call multiple times).
        """
        pass

    async def __aenter__(self) -> "PromptBackend":
        """Context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        """Context manager exit."""
        await self.shutdown()

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Get the name of this backend.

        Returns:
            Backend name (e.g., "pyobjc", "prompt-toolkit")
        """
        pass
