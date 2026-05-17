"""Branch-focused tests for mcp_common.backends.pyobjc."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_common.backends import pyobjc as backend_mod
from mcp_common.prompting.exceptions import (
    BackendUnavailableError,
    DialogDisplayError,
    NotificationError,
)
from mcp_common.prompting.models import DialogResult, NotificationLevel, PromptAdapterSettings


class _AllocInit:
    last_instance = None

    @classmethod
    def alloc(cls):
        return cls()

    def init(self):
        type(self).last_instance = self
        return self


class _FakeAlert(_AllocInit):
    default_run_modal_response = 1000

    def __init__(self) -> None:
        self.message = None
        self.informative = None
        self.buttons: list[str] = []
        self.style = None
        self.accessory = None
        self.run_modal_response = type(self).default_run_modal_response

    def setMessageText_(self, value: str) -> None:
        self.message = value

    def setInformativeText_(self, value: str) -> None:
        self.informative = value

    def addButtonWithTitle_(self, value: str) -> None:
        self.buttons.append(value)

    def setAlertStyle_(self, value: object) -> None:
        self.style = value

    def setAccessoryView_(self, value: object) -> None:
        self.accessory = value

    def runModal(self) -> int:
        return self.run_modal_response


class _FakeTextField(_AllocInit):
    def __init__(self) -> None:
        self.placeholder = None
        self.value = None

    def setPlaceholderString_(self, value: str) -> None:
        self.placeholder = value

    def setStringValue_(self, value: str) -> None:
        self.value = value

    def stringValue(self) -> str:
        return self.value


class _FakePopUpButton(_AllocInit):
    def __init__(self) -> None:
        self.items: list[str] = []
        self.selected_index = 0

    def addItemsWithTitles_(self, choices: list[str]) -> None:
        self.items = list(choices)

    def selectItemAtIndex_(self, index: int) -> None:
        self.selected_index = index

    def indexOfSelectedItem(self) -> int:
        return self.selected_index


class _FakeURL:
    def __init__(self, value: str) -> None:
        self._value = value

    def path(self) -> str:
        return self._value


class _FakeURLList:
    def __init__(self, values: list[str]) -> None:
        self.values = values

    def firstObject(self) -> _FakeURL | None:
        return _FakeURL(self.values[0]) if self.values else None

    def __iter__(self):
        return iter([_FakeURL(value) for value in self.values])


class _FakeOpenPanel(_AllocInit):
    def __init__(self) -> None:
        self.title = None
        self.can_choose_files = None
        self.can_choose_directories = None
        self.allows_multiple_selection = None
        self.allowed_file_types = None
        self.run_modal_response = 1
        self.urls = _FakeURLList([])

    @classmethod
    def openPanel(cls):
        return cls()

    def setTitle_(self, value: str) -> None:
        self.title = value

    def setCanChooseFiles_(self, value: bool) -> None:
        self.can_choose_files = value

    def setCanChooseDirectories_(self, value: bool) -> None:
        self.can_choose_directories = value

    def setAllowsMultipleSelection_(self, value: bool) -> None:
        self.allows_multiple_selection = value

    def setAllowedFileTypes_(self, value: list[str]) -> None:
        self.allowed_file_types = value

    def runModal(self) -> int:
        return self.run_modal_response

    def URLs(self) -> _FakeURLList:
        return self.urls


class _FakeNotification(_AllocInit):
    def __init__(self) -> None:
        self.title = None
        self.message = None
        self.sound = None

    def setTitle_(self, value: str) -> None:
        self.title = value

    def setInformativeText_(self, value: str) -> None:
        self.message = value

    def setSoundName_(self, value: str) -> None:
        self.sound = value


class _FakeNotificationCenter:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.delivered: list[_FakeNotification] = []

    def deliverNotification_(self, note: _FakeNotification) -> None:
        self.delivered.append(note)

    @classmethod
    def defaultUserNotificationCenter(cls):
        return cls.last_instance


class _ImmediateLoop:
    async def run_in_executor(self, executor, func, *args):
        return func(*args)


class _FailingLoop:
    async def run_in_executor(self, executor, func, *args):
        raise RuntimeError("boom")


def _install_fake_frameworks(monkeypatch: pytest.MonkeyPatch, *, notifications_enabled: bool = True) -> None:
    appkit = SimpleNamespace(
        NSAlert=_FakeAlert,
        NSTextField=_FakeTextField,
        NSSecureTextField=_FakeTextField,
        NSPopUpButton=_FakePopUpButton,
        NSOpenPanel=_FakeOpenPanel,
        NSAlertStyleInformational="informational",
        NSAlertStyleWarning="warning",
        NSAlertStyleCritical="critical",
        NSOKButton=1,
    )
    center = _FakeNotificationCenter(enabled=notifications_enabled)
    _FakeNotificationCenter.last_instance = center
    foundation = SimpleNamespace(
        NSUserNotificationCenter=SimpleNamespace(
            defaultUserNotificationCenter=_FakeNotificationCenter.defaultUserNotificationCenter
        ),
        NSUserNotification=_FakeNotification,
    )

    monkeypatch.setattr(backend_mod, "AppKit", appkit)
    monkeypatch.setattr(backend_mod, "Foundation", foundation)
    monkeypatch.setattr(backend_mod, "PYOBJC_AVAILABLE", True)
    monkeypatch.setattr(backend_mod.sys, "platform", "darwin")
    monkeypatch.setattr(backend_mod.asyncio, "get_event_loop", lambda: _ImmediateLoop())
    return None


@pytest.fixture(autouse=True)
def reset_backend_state() -> None:
    _FakeAlert.last_instance = None
    _FakeAlert.default_run_modal_response = 1000
    _FakeTextField.last_instance = None
    _FakePopUpButton.last_instance = None
    _FakeOpenPanel.last_instance = None
    _FakeNotification.last_instance = None
    _FakeNotificationCenter.last_instance = None


class TestAvailabilityAndLifecycle:
    def test_unavailable_constructor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(backend_mod, "PYOBJC_AVAILABLE", False)
        monkeypatch.setattr(backend_mod.sys, "platform", "linux")

        with pytest.raises(BackendUnavailableError):
            backend_mod.PyObjCPromptBackend(PromptAdapterSettings())

    def test_initialize_and_shutdown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_frameworks(monkeypatch)
        backend = backend_mod.PyObjCPromptBackend(PromptAdapterSettings())
        executor = MagicMock()
        backend._executor = executor

        assert backend.is_available() is True
        assert backend.backend_name == "pyobjc"

        asyncio.run(backend.initialize())
        assert backend._initialized is True

        asyncio.run(backend.shutdown())
        executor.shutdown.assert_called_once_with(wait=True)
        assert backend._executor is None
        assert backend._initialized is False


class TestDialogs:
    @pytest.mark.asyncio
    async def test_alert_confirm_and_wrapped_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_frameworks(monkeypatch)
        backend = backend_mod.PyObjCPromptBackend(PromptAdapterSettings())

        result = await backend.alert(
            "Title",
            "Message",
            detail="More",
            buttons=None,
            default_button=None,
            style="warning",
        )
        assert isinstance(result, DialogResult)
        assert result.button_clicked == "OK"
        assert _FakeAlert.last_instance.buttons == ["OK"]
        assert _FakeAlert.last_instance.informative == "Message\n\nMore"
        assert _FakeAlert.last_instance.style == "warning"

        _FakeAlert.default_run_modal_response = 1001
        cancelled = backend._alert_sync("T", "M", None, ["Yes"], None, "unknown")
        assert cancelled.cancelled is True

        monkeypatch.setattr(backend_mod.asyncio, "get_event_loop", lambda: _FailingLoop())
        with pytest.raises(DialogDisplayError):
            await backend.alert("T", "M")

    @pytest.mark.asyncio
    async def test_confirm_prompt_text_and_choice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_frameworks(monkeypatch)
        backend = backend_mod.PyObjCPromptBackend(PromptAdapterSettings())

        backend.alert = AsyncMock(return_value=DialogResult(button_clicked="Yes"))  # type: ignore[method-assign]
        assert await backend.confirm("T", "M", default=True) is True

        _FakeAlert.default_run_modal_response = 1000
        assert backend._prompt_text_sync("T", "M", "default", "ph", False) == "default"
        _FakeAlert.default_run_modal_response = 1001
        assert backend._prompt_text_sync("T", "M", "default", "ph", True) is None

        _FakeAlert.default_run_modal_response = 1000
        assert backend._prompt_choice_sync("T", "M", ["a", "b"], "b") == "b"
        assert backend._prompt_choice_sync("T", "M", ["a", "b"], "missing") == "a"
        _FakeAlert.default_run_modal_response = 1001
        assert backend._prompt_choice_sync("T", "M", ["a", "b"], None) is None

    @pytest.mark.asyncio
    async def test_prompt_text_wrapper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_frameworks(monkeypatch)
        backend = backend_mod.PyObjCPromptBackend(PromptAdapterSettings())
        assert await backend.prompt_text("T", "M", default="x", placeholder="p", secure=True) == "x"


class TestNotificationsAndFiles:
    @pytest.mark.asyncio
    async def test_notify_and_selection_helpers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_frameworks(monkeypatch)
        backend = backend_mod.PyObjCPromptBackend(PromptAdapterSettings())

        assert backend._notify_sync("Title", "Body", NotificationLevel.INFO, True) is True
        assert _FakeNotificationCenter.last_instance.delivered[0].sound == "NSUserNotificationDefaultSoundName"

        _FakeNotificationCenter.last_instance = None
        assert backend._notify_sync("Title", "Body", NotificationLevel.INFO, False) is False

        panel = _FakeOpenPanel.openPanel()
        panel.run_modal_response = 1
        panel.urls = _FakeURLList(["/tmp/a.txt", "/tmp/b.txt"])
        monkeypatch.setattr(backend_mod.AppKit, "NSOpenPanel", SimpleNamespace(openPanel=lambda: panel))
        result = backend._select_file_sync("Pick", ["txt"], True)
        assert result == [Path("/tmp/a.txt"), Path("/tmp/b.txt")]

        panel.run_modal_response = 0
        assert backend._select_file_sync("Pick", None, False) is None

        panel = _FakeOpenPanel.openPanel()
        panel.run_modal_response = 1
        panel.urls = _FakeURLList(["/tmp/dir"])
        monkeypatch.setattr(backend_mod.AppKit, "NSOpenPanel", SimpleNamespace(openPanel=lambda: panel))
        assert backend._select_directory_sync("Pick") == Path("/tmp/dir")

    @pytest.mark.asyncio
    async def test_wrapped_notification_and_file_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_frameworks(monkeypatch)
        backend = backend_mod.PyObjCPromptBackend(PromptAdapterSettings())

        monkeypatch.setattr(backend_mod.asyncio, "get_event_loop", lambda: _FailingLoop())
        with pytest.raises(NotificationError):
            await backend.notify("T", "M")

        with pytest.raises(DialogDisplayError):
            await backend.select_file("T")

        with pytest.raises(DialogDisplayError):
            await backend.select_directory("T")
