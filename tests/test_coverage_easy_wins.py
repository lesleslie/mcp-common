"""Targeted tests for uncovered lines in high-coverage mcp-common modules."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ── descriptions.py (line 56: break on section header in first paragraph) ──

class TestTrimDescriptionSectionBreak:
    """Cover the 'break on section header' branch in trim_description."""

    def test_section_header_in_first_paragraph_stops_collection(self):
        """A section header like 'Args:' in the first paragraph triggers break."""
        from mcp_common.tools.descriptions import trim_description

        docstring = (
            "Do a thing.\n"
            "Args:\n"
            "    x: The input value.\n"
            "Returns:\n"
            "    The result."
        )
        result = trim_description(docstring)
        assert "Args:" not in result
        assert "Do a thing." in result

    def test_examples_header_stops(self):
        from mcp_common.tools.descriptions import trim_description

        result = trim_description("Parse data.\nExamples:\n  >>> parse('x')")
        assert "Examples:" not in result
        assert "Parse data." in result

    def test_notes_header_stops(self):
        from mcp_common.tools.descriptions import trim_description

        result = trim_description("Check health.\nNotes:\n  Must be called after init.")
        assert "Notes:" not in result


# ── websocket/auth.py (lines 106-107: JWT not available path) ──

class TestWebSocketAuthJWTUnavailable:
    """Cover verify_token when PyJWT is not installed."""

    def test_verify_token_no_jwt(self):
        from mcp_common.websocket.auth import WebSocketAuthenticator

        auth = WebSocketAuthenticator(secret="test-secret")

        with patch("mcp_common.websocket.auth.JWT_AVAILABLE", False):
            result = auth.verify_token("some-token")
        assert result is None


# ── prompting/base.py (lines 228-229, 233: async context manager) ──

class TestPromptBackendContextManager:
    """Cover __aenter__ and __aexit__ on PromptBackend."""

    @pytest.mark.asyncio
    async def test_aenter_initializes_and_returns_self(self):
        from mcp_common.prompting.base import PromptBackend

        init_called = False
        shutdown_called = False

        class ConcreteBackend(PromptBackend):
            @property
            def backend_name(self) -> str:
                return "test"

            @property
            def is_available(self) -> bool:
                return True

            async def initialize(self) -> None:
                nonlocal init_called
                init_called = True

            async def shutdown(self) -> None:
                nonlocal shutdown_called
                shutdown_called = True

            async def alert(self, message, level=None):
                pass

            async def confirm(self, message, default=True):
                return True

            async def notify(self, message, level=None):
                pass

            async def prompt_text(self, message, default="", **kwargs):
                return default

            async def prompt_choice(self, message, choices, **kwargs):
                return choices[0] if choices else None

            async def select_file(self, message, **kwargs):
                return None

            async def select_directory(self, message, **kwargs):
                return None

        backend = ConcreteBackend()
        async with backend as ctx:
            assert ctx is backend
            assert init_called is True

        assert shutdown_called is True


# ── websocket/protocol.py (lines 80, 92, 99, 115) ──

class TestWebSocketProtocolFactoryMethods:
    """Cover WebSocketProtocol static factory methods."""

    def test_create_request_generates_correlation_id(self):
        from mcp_common.websocket.protocol import WebSocketProtocol

        msg = WebSocketProtocol.create_request("test_event", {"key": "val"})
        assert msg.correlation_id is not None
        assert len(msg.correlation_id) > 0
        assert msg.event == "test_event"

    def test_create_request_preserves_explicit_correlation_id(self):
        from mcp_common.websocket.protocol import WebSocketProtocol

        msg = WebSocketProtocol.create_request("ev", {}, correlation_id="my-id")
        assert msg.correlation_id == "my-id"

    def test_create_response_success(self):
        from mcp_common.websocket.protocol import MessageType, WebSocketProtocol

        request = WebSocketProtocol.create_request("ev", {})
        response = WebSocketProtocol.create_response(request, {"result": 1})
        assert response.type == MessageType.RESPONSE
        assert response.correlation_id == request.correlation_id
        assert response.error_message is None

    def test_create_response_error(self):
        from mcp_common.websocket.protocol import MessageType, WebSocketProtocol

        request = WebSocketProtocol.create_request("ev", {})
        response = WebSocketProtocol.create_response(request, {}, error="something failed")
        assert response.type == MessageType.ERROR
        assert response.error_message == "something failed"

    def test_create_event(self):
        from mcp_common.websocket.protocol import MessageType, WebSocketProtocol

        msg = WebSocketProtocol.create_event("room_event", {"data": 1}, room="room1")
        assert msg.type == MessageType.EVENT
        assert msg.room == "room1"

    def test_create_event_no_room(self):
        from mcp_common.websocket.protocol import MessageType, WebSocketProtocol

        msg = WebSocketProtocol.create_event("evt", {"data": 1})
        assert msg.type == MessageType.EVENT
        assert msg.room is None

    def test_create_error(self):
        from mcp_common.websocket.protocol import MessageType, WebSocketProtocol

        msg = WebSocketProtocol.create_error("ERR_001", "bad thing", correlation_id="c123")
        assert msg.type == MessageType.ERROR
        assert msg.error_code == "ERR_001"
        assert msg.error_message == "bad thing"
        assert msg.correlation_id == "c123"

    def test_create_error_no_correlation(self):
        from mcp_common.websocket.protocol import MessageType, WebSocketProtocol

        msg = WebSocketProtocol.create_error("E", "msg")
        assert msg.type == MessageType.ERROR
        assert msg.correlation_id is None


# ── prompting/models.py (lines 97-102: oneiric import path) ──

class TestPromptAdapterSettingsFromOneiric:
    """Cover PromptAdapterSettings.from_settings() with and without oneiric."""

    def test_from_settings_without_oneiric(self):
        from mcp_common.prompting.models import PromptAdapterSettings

        result = PromptAdapterSettings.from_settings()
        assert isinstance(result, PromptAdapterSettings)

    def test_from_settings_with_oneiric(self):
        from mcp_common.prompting.models import PromptAdapterSettings

        mock_load = MagicMock(return_value={
            "prompting": {"max_tokens": 500, "temperature": 0.9}
        })
        with patch.dict("sys.modules", {"oneiric": MagicMock(load_config=mock_load)}):
            result = PromptAdapterSettings.from_settings()
        assert result.max_tokens == 500
        assert result.temperature == 0.9


# ── parsing/tree_sitter/queries.py (lines 122-148) ──

class TestTreeSitterQueries:
    """Cover get_query and list_queries functions."""

    def test_get_query_python(self):
        from mcp_common.parsing.tree_sitter.queries import get_query

        result = get_query("python", "functions")
        assert result is not None
        assert "function" in result.lower()

    def test_get_query_unknown_language(self):
        from mcp_common.parsing.tree_sitter.queries import get_query

        assert get_query("rust", "function") is None

    def test_get_query_unknown_query_name(self):
        from mcp_common.parsing.tree_sitter.queries import get_query

        assert get_query("python", "nonexistent_query_xyz") is None

    def test_list_queries_python(self):
        from mcp_common.parsing.tree_sitter.queries import list_queries

        result = list_queries("python")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_list_queries_unknown_language(self):
        from mcp_common.parsing.tree_sitter.queries import list_queries

        assert list_queries("rust") == []


# ── prompting/factory.py ──

class TestPromptAdapterFactory:
    """Cover create_prompt_adapter and list_available_backends."""

    def test_list_available_backends_empty(self):
        """Both backends unavailable returns empty list."""
        from mcp_common.prompting.factory import list_available_backends

        with patch.dict("sys.modules", {
            "mcp_common.backends.pyobjc": None,
            "mcp_common.backends.toolkit": None,
        }):
            assert list_available_backends() == []

    def test_create_prompt_adapter_pyobjc_import_error(self):
        """Requesting pyobjc when not installed raises BackendUnavailableError."""
        from mcp_common.prompting.factory import create_prompt_adapter
        from mcp_common.prompting.exceptions import BackendUnavailableError

        with patch.dict("sys.modules", {"mcp_common.backends.pyobjc": None}):
            with pytest.raises(BackendUnavailableError, match="PyObjC is not installed"):
                create_prompt_adapter(backend="pyobjc")

    def test_create_prompt_adapter_toolkit_import_error(self):
        """Requesting prompt-toolkit when not installed raises BackendUnavailableError."""
        from mcp_common.prompting.factory import create_prompt_adapter
        from mcp_common.prompting.exceptions import BackendUnavailableError

        with patch.dict("sys.modules", {"mcp_common.backends.toolkit": None}):
            with pytest.raises(BackendUnavailableError, match="prompt-toolkit is not installed"):
                create_prompt_adapter(backend="prompt-toolkit")

    def test_create_prompt_adapter_toolkit_init_error(self):
        """Import succeeds but instantiation fails catches generic Exception."""
        from mcp_common.prompting.factory import create_prompt_adapter
        from mcp_common.prompting.exceptions import BackendUnavailableError

        mock_module = MagicMock()
        mock_module.PromptToolkitBackend = MagicMock(side_effect=RuntimeError("init failed"))
        with patch.dict("sys.modules", {"mcp_common.backends.toolkit": mock_module}):
            with pytest.raises(BackendUnavailableError, match="Failed to initialize"):
                create_prompt_adapter(backend="prompt-toolkit")

    def test_list_available_backends_toolkit_available(self):
        """When prompt-toolkit is available, it appears in the list."""
        from mcp_common.prompting.factory import list_available_backends

        mock_module = MagicMock()
        mock_module.PromptToolkitBackend.is_available_static.return_value = True
        with patch.dict("sys.modules", {
            "mcp_common.backends.pyobjc": None,
            "mcp_common.backends.toolkit": mock_module,
        }):
            result = list_available_backends()
        assert "prompt-toolkit" in result

    def test_resolve_backend_no_backends_available(self):
        """Auto-detect when neither backend is available raises error."""
        from mcp_common.prompting.factory import _resolve_backend
        from mcp_common.prompting.exceptions import BackendUnavailableError
        from mcp_common.prompting.models import PromptAdapterSettings

        with patch.dict("sys.modules", {
            "mcp_common.backends.pyobjc": None,
            "mcp_common.backends.toolkit": None,
        }):
            with pytest.raises(BackendUnavailableError, match="No suitable prompting backend"):
                _resolve_backend("auto", PromptAdapterSettings())


# ── ui/panels.py (line 421: profile.value, line 467: default status style) ──

class TestServerPanelsEdgeCases:
    """Cover profile.value extraction and default status styling."""

    def test_backups_table_profile_with_value_attribute(self):
        """Profile as an enum-like object with .value should use .value."""
        from mcp_common.ui.panels import ServerPanels

        class FakeProfile:
            value = "standard"

        ServerPanels.backups_table([
            {"id": "a" * 8, "name": "test", "profile": FakeProfile(),
             "created_at": datetime(2026, 1, 1, 12, 0), "description": "desc"}
        ])

    def test_server_status_table_unknown_status(self):
        """Status value that matches no keyword gets default (unstyled) Text."""
        from mcp_common.ui.panels import ServerPanels

        ServerPanels.server_status_table([
            ["svc", "initializing", "1234", "warming up"]
        ])
