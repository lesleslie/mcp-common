"""PyObjC backend for native macOS dialogs and notifications.

This backend uses PyObjC to provide native macOS user interface elements:
- NSAlert for dialog boxes
- NSUserNotification for system notifications
- NSOpenPanel/NSSavePanel for file selection
- NSTextField for text input

Platform: macOS only
Dependencies: pyobjc-core, pyobjc-framework-Cocoa (optional)
"""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Literal

from mcp_common.prompting.base import PromptBackend
from mcp_common.prompting.exceptions import (
    BackendUnavailableError,
    DialogDisplayError,
    NotificationError,
    UserCancelledError,
)
from mcp_common.prompting.models import DialogResult, NotificationLevel, PromptAdapterSettings, PromptConfig

if TYPE_CHECKING:
    from pathlib import Path

# PyObjC imports (lazy, will fail if not installed)
try:
    import AppKit
    import Foundation

    PYOBJC_AVAILABLE = True
except ImportError:
    PYOBJC_AVAILABLE = False

    # Create stubs for type checking
    AppKit = None  # type: ignore
    Foundation = None  # type: ignore


class PyObjCPromptBackend(PromptBackend):
    """Native macOS prompting backend using PyObjC.

    Provides native macOS dialogs and notifications through AppKit and
    Foundation frameworks. All GUI operations run on the main thread
    via an executor to avoid blocking the async event loop.
    """

    def __init__(self, config: PromptAdapterSettings):
        """Initialize PyObjC backend.

        Args:
            config: Configuration for the backend

        Raises:
            BackendUnavailableError: If PyObjC is not installed or not on macOS
        """
        if not self.is_available_static():
            raise BackendUnavailableError(
                backend="pyobjc",
                reason="PyObjC is not installed or not on macOS",
                install_hint="Install with: pip install 'mcp-common[macos-prompts]'",
            )

        self.config = config
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pyobjc_gui")
        self._initialized = False

    @staticmethod
    def is_available_static() -> bool:
        """Check if PyObjC backend is available without importing.

        Returns:
            True if on macOS and PyObjC is installed
        """
        return sys.platform == "darwin" and PYOBJC_AVAILABLE

    def is_available(self) -> bool:
        """Check if this backend is available.

        Returns:
            True if PyObjC is installed and platform is macOS
        """
        return self.is_available_static()

    @property
    def backend_name(self) -> str:
        """Get backend name.

        Returns:
            Backend name identifier
        """
        return "pyobjc"

    # ===== Lifecycle Methods =====

    async def initialize(self) -> None:
        """Initialize PyObjC backend.

        Validates that PyObjC is available and the executor is ready.
        """
        if not self.is_available_static():
            raise BackendUnavailableError(
                backend="pyobjc",
                reason="PyObjC is not installed or not on macOS",
            )

        self._initialized = True

    async def shutdown(self) -> None:
        """Cleanup PyObjC backend resources.

        Shuts down the thread pool executor used for main thread GUI operations.
        """
        if hasattr(self, "_executor") and self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

        self._initialized = False

    # ===== Dialog Methods =====

    async def alert(
        self,
        title: str,
        message: str,
        detail: str | None = None,
        buttons: list[str] | None = None,
        default_button: str | None = None,
        style: str = "info",
    ) -> DialogResult:
        """Display an alert dialog (runs on main thread)."""
        if not buttons:
            buttons = ["OK"]

        try:
            return await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._alert_sync,
                title,
                message,
                detail,
                buttons,
                default_button,
                style,
            )
        except Exception as e:
            raise DialogDisplayError(
                backend="pyobjc", dialog_type="alert", reason=str(e)
            ) from e

    def _alert_sync(
        self,
        title: str,
        message: str,
        detail: str | None,
        buttons: list[str],
        default_button: str | None,
        style: str,
    ) -> DialogResult:
        """Synchronous alert dialog (must run on main thread)."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)

        if detail:
            alert.setInformativeText_(f"{message}\n\n{detail}")

        # Add buttons
        for button_label in buttons:
            alert.addButtonWithTitle_(button_label)

        # Set alert style
        style_map = {
            "info": AppKit.NSAlertStyleInformational,
            "warning": AppKit.NSAlertStyleWarning,
            "error": AppKit.NSAlertStyleCritical,
        }
        alert.setAlertStyle_(style_map.get(style, AppKit.NSAlertStyleInformational))

        # Run modal (blocks until user clicks)
        response = alert.runModal()

        # Map response to button (NSAlertFirstButtonReturn = 1000, etc.)
        button_index = response - 1000
        if 0 <= button_index < len(buttons):
            return DialogResult(button_clicked=buttons[button_index])

        return DialogResult(cancelled=True, button_clicked=None)

    async def confirm(
        self,
        title: str,
        message: str,
        default: bool = False,
        yes_label: str = "Yes",
        no_label: str = "No",
    ) -> bool:
        """Display a confirmation dialog (Yes/No)."""
        buttons = [yes_label, no_label]
        default_button = yes_label if default else no_label

        result = await self.alert(title, message, buttons=buttons, default_button=default_button)

        return result.button_clicked == yes_label

    async def prompt_text(
        self,
        title: str,
        message: str,
        default: str = "",
        placeholder: str = "",
        secure: bool = False,
    ) -> str | None:
        """Prompt for text input (uses NSTextField)."""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._prompt_text_sync,
                title,
                message,
                default,
                placeholder,
                secure,
            )
        except Exception as e:
            raise DialogDisplayError(
                backend="pyobjc", dialog_type="text input", reason=str(e)
            ) from e

    def _prompt_text_sync(
        self,
        title: str,
        message: str,
        default: str,
        placeholder: str,
        secure: bool,
    ) -> str | None:
        """Synchronous text input prompt."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)

        # Create text field
        if secure:
            text_field = AppKit.NSSecureTextField.alloc().init()
        else:
            text_field = AppKit.NSTextField.alloc().init()

        text_field.setPlaceholderString_(placeholder)
        text_field.setStringValue_(default)

        # Set as accessory view
        alert.setAccessoryView_(text_field)

        # Add OK/Cancel buttons
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        # Run modal
        response = alert.runModal()

        if response == 1000:  # OK button (first button)
            return text_field.stringValue()

        return None  # Cancelled

    async def prompt_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        default: str | None = None,
    ) -> str | None:
        """Prompt user to select from choices (uses NSPopUpButton)."""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._prompt_choice_sync,
                title,
                message,
                choices,
                default,
            )
        except Exception as e:
            raise DialogDisplayError(
                backend="pyobjc", dialog_type="choice", reason=str(e)
            ) from e

    def _prompt_choice_sync(
        self,
        title: str,
        message: str,
        choices: list[str],
        default: str | None,
    ) -> str | None:
        """Synchronous choice prompt."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)

        # Create popup button
        popup = AppKit.NSPopUpButton.alloc().init()
        popup.addItemsWithTitles_(choices)

        if default and default in choices:
            popup.selectItemAtIndex_(choices.index(default))

        alert.setAccessoryView_(popup)

        # Add OK/Cancel buttons
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        # Run modal
        response = alert.runModal()

        if response == 1000:  # OK button
            selected_index = popup.indexOfSelectedItem()
            if 0 <= selected_index < len(choices):
                return choices[selected_index]

        return None

    # ===== Notification Method =====

    async def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        sound: bool = True,
    ) -> bool:
        """Send a system notification via NSUserNotificationCenter."""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._notify_sync,
                title,
                message,
                level,
                sound,
            )
        except Exception as e:
            raise NotificationError(
                backend="pyobjc", title=title, reason=str(e), level=level
            ) from e

    def _notify_sync(
        self,
        title: str,
        message: str,
        level: NotificationLevel,
        sound: bool,
    ) -> bool:
        """Synchronous notification delivery."""
        center = Foundation.NSUserNotificationCenter.defaultUserNotificationCenter()

        # Check if notifications are enabled for this app
        if not center:
            return False

        note = Foundation.NSUserNotification.alloc().init()
        note.setTitle_(title)
        note.setInformativeText_(message)

        # Set sound
        if sound:
            note.setSoundName_("NSUserNotificationDefaultSoundName")

        # Deliver notification
        center.deliverNotification_(note)

        return True

    # ===== File Selection Methods =====

    async def select_file(
        self,
        title: str,
        allowed_types: list[str] | None = None,
        multiple: bool = False,
    ) -> "list[Path] | None":
        """Display file selection dialog."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._select_file_sync,
                title,
                allowed_types,
                multiple,
            )
            return result
        except Exception as e:
            raise DialogDisplayError(
                backend="pyobjc", dialog_type="file selection", reason=str(e)
            ) from e

    def _select_file_sync(
        self,
        title: str,
        allowed_types: list[str] | None,
        multiple: bool,
    ) -> "list[Path] | None":
        """Synchronous file selection."""
        panel = AppKit.NSOpenPanel.openPanel()
        panel.setTitle_(title)
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(False)
        panel.setAllowsMultipleSelection_(multiple)

        if allowed_types:
            panel.setAllowedFileTypes_(allowed_types)

        response = panel.runModal()

        if response == AppKit.NSOKButton:
            urls = panel.URLs()
            paths = [url.path() for url in urls]
            return [Path(p) for p in paths]

        return None

    async def select_directory(
        self,
        title: str,
    ) -> "Path | None":
        """Display directory selection dialog."""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._select_directory_sync,
                title,
            )
        except Exception as e:
            raise DialogDisplayError(
                backend="pyobjc", dialog_type="directory selection", reason=str(e)
            ) from e

    def _select_directory_sync(self, title: str) -> "Path | None":
        """Synchronous directory selection."""
        panel = AppKit.NSOpenPanel.openPanel()
        panel.setTitle_(title)
        panel.setCanChooseFiles_(False)
        panel.setCanChooseDirectories_(True)

        response = panel.runModal()

        if response == AppKit.NSOKButton:
            url = panel.URLs().firstObject()
            return Path(url.path()) if url else None

        return None


__all__ = ["PyObjCPromptBackend"]
