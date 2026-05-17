"""Tests for mcp_common.parsing.tree_sitter.grammars."""

from __future__ import annotations

import builtins
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from mcp_common.parsing.tree_sitter import grammars
from mcp_common.parsing.tree_sitter.models import SupportedLanguage


@pytest.fixture(autouse=True)
def reset_grammar_state() -> None:
    grammars._loaded_languages = set()


def _fake_import(name: str, *, language_raises: Exception | None = None) -> None:
    tree_sitter_mod = ModuleType("tree_sitter")

    class FakeLanguage:
        def __init__(self, value: object) -> None:
            if language_raises is not None:
                raise language_raises
            self.value = value

    tree_sitter_mod.Language = FakeLanguage  # type: ignore[attr-defined]
    sys.modules["tree_sitter"] = tree_sitter_mod


class TestLoadPythonGrammar:
    def test_success_registers_grammar_and_handler(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tree_sitter_mod = ModuleType("tree_sitter")

        class FakeLanguage:
            def __init__(self, value: object) -> None:
                self.value = value

        tree_sitter_mod.Language = FakeLanguage  # type: ignore[attr-defined]
        python_mod = ModuleType("tree_sitter_python")
        python_mod.language = lambda: b"python-grammar"  # type: ignore[attr-defined]
        handlers_mod = ModuleType("mcp_common.parsing.tree_sitter.handlers.python")

        class FakePythonHandler:
            pass

        handlers_mod.PythonHandler = FakePythonHandler  # type: ignore[attr-defined]

        set_grammar = MagicMock()
        register = MagicMock()
        monkeypatch.setitem(sys.modules, "tree_sitter", tree_sitter_mod)
        monkeypatch.setitem(sys.modules, "tree_sitter_python", python_mod)
        monkeypatch.setitem(
            sys.modules, "mcp_common.parsing.tree_sitter.handlers.python", handlers_mod
        )
        monkeypatch.setattr(grammars.LanguageRegistry, "set_grammar", set_grammar)
        monkeypatch.setattr(grammars.LanguageRegistry, "register", register)

        language = grammars.load_python_grammar()

        assert isinstance(language, FakeLanguage)
        assert language.value == b"python-grammar"
        set_grammar.assert_called_once()
        register.assert_called_once()
        assert SupportedLanguage.PYTHON in grammars._loaded_languages

    def test_import_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original_import = builtins.__import__

        def raising_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"tree_sitter", "tree_sitter_python"}:
                raise ImportError("missing python grammar")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", raising_import)

        assert grammars.load_python_grammar() is None

    def test_unexpected_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tree_sitter_mod = ModuleType("tree_sitter")

        class FakeLanguage:
            def __init__(self, value: object) -> None:
                raise RuntimeError("boom")

        tree_sitter_mod.Language = FakeLanguage  # type: ignore[attr-defined]
        python_mod = ModuleType("tree_sitter_python")
        python_mod.language = lambda: b"python-grammar"  # type: ignore[attr-defined]

        monkeypatch.setitem(sys.modules, "tree_sitter", tree_sitter_mod)
        monkeypatch.setitem(sys.modules, "tree_sitter_python", python_mod)

        assert grammars.load_python_grammar() is None


class TestLoadGoGrammar:
    def test_success_registers_grammar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tree_sitter_mod = ModuleType("tree_sitter")

        class FakeLanguage:
            def __init__(self, value: object) -> None:
                self.value = value

        tree_sitter_mod.Language = FakeLanguage  # type: ignore[attr-defined]
        go_mod = ModuleType("tree_sitter_go")
        go_mod.language = lambda: b"go-grammar"  # type: ignore[attr-defined]

        set_grammar = MagicMock()
        monkeypatch.setitem(sys.modules, "tree_sitter", tree_sitter_mod)
        monkeypatch.setitem(sys.modules, "tree_sitter_go", go_mod)
        monkeypatch.setattr(grammars.LanguageRegistry, "set_grammar", set_grammar)

        language = grammars.load_go_grammar()

        assert isinstance(language, FakeLanguage)
        assert language.value == b"go-grammar"
        set_grammar.assert_called_once()
        assert SupportedLanguage.GO in grammars._loaded_languages

    def test_import_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original_import = builtins.__import__

        def raising_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"tree_sitter", "tree_sitter_go"}:
                raise ImportError("missing go grammar")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", raising_import)

        assert grammars.load_go_grammar() is None

    def test_unexpected_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tree_sitter_mod = ModuleType("tree_sitter")

        class FakeLanguage:
            def __init__(self, value: object) -> None:
                raise RuntimeError("boom")

        tree_sitter_mod.Language = FakeLanguage  # type: ignore[attr-defined]
        go_mod = ModuleType("tree_sitter_go")
        go_mod.language = lambda: b"go-grammar"  # type: ignore[attr-defined]

        monkeypatch.setitem(sys.modules, "tree_sitter", tree_sitter_mod)
        monkeypatch.setitem(sys.modules, "tree_sitter_go", go_mod)

        assert grammars.load_go_grammar() is None


class TestGrammarRegistryHelpers:
    def test_load_all_grammars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(grammars, "load_python_grammar", lambda: "python")
        monkeypatch.setattr(grammars, "load_go_grammar", lambda: "go")

        assert grammars.load_all_grammars() == {
            SupportedLanguage.PYTHON: "python",
            SupportedLanguage.GO: "go",
        }

    def test_is_and_get_loaded_languages(self) -> None:
        grammars._loaded_languages = {SupportedLanguage.PYTHON}

        assert grammars.is_language_loaded(SupportedLanguage.PYTHON) is True
        assert grammars.is_language_loaded(SupportedLanguage.GO) is False
        assert grammars.get_loaded_languages() == {SupportedLanguage.PYTHON}

    def test_ensure_language_loaded_when_already_loaded(self) -> None:
        grammars._loaded_languages = {SupportedLanguage.GO}

        assert grammars.ensure_language_loaded(SupportedLanguage.GO) is True

    def test_ensure_language_loaded_unknown_language(self) -> None:
        assert grammars.ensure_language_loaded(SupportedLanguage.UNKNOWN) is False

    def test_ensure_language_loaded_calls_loader(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(grammars, "load_python_grammar", lambda: object())

        assert grammars.ensure_language_loaded(SupportedLanguage.PYTHON) is True

    def test_ensure_language_loaded_loader_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(grammars, "load_go_grammar", lambda: None)

        assert grammars.ensure_language_loaded(SupportedLanguage.GO) is False
