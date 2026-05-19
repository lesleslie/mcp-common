"""Branch-focused tests for mcp_common.parsing.tree_sitter.core."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from mcp_common.parsing.tree_sitter import core
from mcp_common.parsing.tree_sitter.exceptions import (
    FileTooLargeError,
    LanguageNotSupportedError,
)
from mcp_common.parsing.tree_sitter.models import (
    ComplexityMetrics,
    ParseResult,
    SupportedLanguage,
)


class _FakeNode:
    def __init__(self, node_type: str, children: list[_FakeNode] | None = None) -> None:
        self.type = node_type
        self.children = children or []


class _FakeTree:
    def __init__(self, root_node: _FakeNode) -> None:
        self.root_node = root_node


class _FakeParser:
    def __init__(self, grammar: object) -> None:
        self.grammar = grammar

    def parse(self, content: bytes) -> _FakeTree:
        return _FakeTree(_FakeNode("root", [_FakeNode("ERROR"), _FakeNode("child")]))


class _FakeHandler:
    language = SupportedLanguage.PYTHON

    def extract(self, content: bytes, tree: _FakeTree):
        return ([], [], [])

    def compute_complexity(self, content: bytes, tree: _FakeTree):
        return {"unit": ComplexityMetrics(cyclomatic=2)}


@pytest.fixture(autouse=True)
def reset_registry_state() -> None:
    core.LanguageRegistry._handlers = {}
    core.LanguageRegistry._grammars = {}
    core._global_parser = None


class TestCountErrorNodes:
    def test_counts_nested_error_nodes(self) -> None:
        root = _FakeNode("root", [_FakeNode("ERROR"), _FakeNode("branch", [_FakeNode("ERROR")])])

        assert core._count_error_nodes(root) == 2


class TestLanguageRegistry:
    def test_register_get_and_grammar_helpers(self) -> None:
        handler = _FakeHandler()

        core.LanguageRegistry.register(handler)
        core.LanguageRegistry.set_grammar(SupportedLanguage.PYTHON, object())

        assert core.LanguageRegistry.get(SupportedLanguage.PYTHON) is handler
        assert core.LanguageRegistry.get_grammar(SupportedLanguage.PYTHON) is not None
        assert core.LanguageRegistry.supported_languages() == [SupportedLanguage.PYTHON]
        assert core.LanguageRegistry.is_supported(SupportedLanguage.PYTHON) is True
        assert core.LanguageRegistry.is_supported(SupportedLanguage.UNKNOWN) is False


class TestParseSync:
    def test_returns_error_when_language_not_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_common.parsing.tree_sitter.grammars.ensure_language_loaded",
            lambda language: False,
        )

        result = core._parse_sync(Path("test.py"), b"print('x')", SupportedLanguage.PYTHON)

        assert not result.success
        assert result.error == "Failed to load grammar for python"

    def test_returns_error_when_handler_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_common.parsing.tree_sitter.grammars.ensure_language_loaded",
            lambda language: True,
        )

        result = core._parse_sync(Path("test.py"), b"print('x')", SupportedLanguage.PYTHON)

        assert not result.success
        assert result.error == "No handler for python"

    def test_returns_error_when_grammar_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_common.parsing.tree_sitter.grammars.ensure_language_loaded",
            lambda language: True,
        )
        monkeypatch.setattr(core.LanguageRegistry, "get", lambda language: _FakeHandler())
        monkeypatch.setattr(core.LanguageRegistry, "get_grammar", lambda language: None)

        result = core._parse_sync(Path("test.py"), b"print('x')", SupportedLanguage.PYTHON)

        assert not result.success
        assert result.error == "Grammar not loaded for python"

    def test_successful_parse_counts_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_tree_sitter = ModuleType("tree_sitter")
        fake_tree_sitter.Parser = _FakeParser  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "tree_sitter", fake_tree_sitter)
        monkeypatch.setattr(
            "mcp_common.parsing.tree_sitter.grammars.ensure_language_loaded",
            lambda language: True,
        )
        monkeypatch.setattr(core.LanguageRegistry, "get", lambda language: _FakeHandler())
        monkeypatch.setattr(core.LanguageRegistry, "get_grammar", lambda language: object())

        result = core._parse_sync(Path("test.py"), b"print('x')", SupportedLanguage.PYTHON)

        assert result.success is True
        assert result.symbols == ()
        assert result.relationships == ()
        assert result.imports == ()
        assert result.error_node_count == 1
        assert result.parse_time_ms >= 0
        assert result.complexity["unit"].cyclomatic == 2

    def test_parse_exception_returns_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FailingParser(_FakeParser):
            def parse(self, content: bytes) -> _FakeTree:
                raise RuntimeError("parse failed")

        fake_tree_sitter = ModuleType("tree_sitter")
        fake_tree_sitter.Parser = FailingParser  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "tree_sitter", fake_tree_sitter)
        monkeypatch.setattr(
            "mcp_common.parsing.tree_sitter.grammars.ensure_language_loaded",
            lambda language: True,
        )
        monkeypatch.setattr(core.LanguageRegistry, "get", lambda language: _FakeHandler())
        monkeypatch.setattr(core.LanguageRegistry, "get_grammar", lambda language: object())

        result = core._parse_sync(Path("test.py"), b"print('x')", SupportedLanguage.PYTHON)

        assert not result.success
        assert result.error == "parse failed"


class TestTreeSitterParser:
    def test_detect_language_unknown(self) -> None:
        parser = core.TreeSitterParser()
        assert parser.detect_language(Path("README.txt")) == SupportedLanguage.UNKNOWN

    @pytest.mark.asyncio
    async def test_parse_file_rejects_unknown_language(self) -> None:
        parser = core.TreeSitterParser()

        with pytest.raises(LanguageNotSupportedError):
            await parser.parse_file(Path("README.txt"), language=SupportedLanguage.UNKNOWN)

    @pytest.mark.asyncio
    async def test_parse_file_rejects_too_large_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        file_path = tmp_path / "input.py"
        file_path.write_bytes(b"print('hello')")
        parser = core.TreeSitterParser(max_file_size=0)

        with pytest.raises(FileTooLargeError):
            await parser.parse_file(file_path, language=SupportedLanguage.PYTHON)

    @pytest.mark.asyncio
    async def test_parse_file_returns_cached_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        file_path = tmp_path / "input.py"
        file_path.write_bytes(b"print('hello')")
        parser = core.TreeSitterParser()
        cached_result = ParseResult(
            success=True,
            file_path=str(file_path),
            language=SupportedLanguage.PYTHON,
        )
        parser._cache.set(b"print('hello')", cached_result)

        result = await parser.parse_file(file_path, language=SupportedLanguage.PYTHON)

        assert result.from_cache is True
        assert result.success is True
        assert result.file_path == str(file_path)

    def test_parse_bytes_delegates_to_sync_parser(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = MagicMock(
            return_value=ParseResult(
                success=True,
                file_path="virtual.py",
                language=SupportedLanguage.PYTHON,
            )
        )
        monkeypatch.setattr(core, "_parse_sync", called)
        parser = core.TreeSitterParser()

        result = parser.parse_bytes(b"print('x')", SupportedLanguage.PYTHON, "virtual.py")

        assert result.success is True
        called.assert_called_once()

    def test_get_executor_falls_back_to_threads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        parser = core.TreeSitterParser(max_workers=2)
        monkeypatch.setattr(
            core,
            "ProcessPoolExecutor",
            MagicMock(side_effect=OSError("no process pool")),
        )

        executor = parser._get_executor()

        assert type(executor).__name__ == "ThreadPoolExecutor"

    def test_get_executor_creates_process_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        parser = core.TreeSitterParser(max_workers=2)
        executor = MagicMock(name="process_pool")
        mocked_ctor = MagicMock(return_value=executor)
        monkeypatch.setattr(core, "ProcessPoolExecutor", mocked_ctor)

        result = parser._get_executor()

        assert result is executor
        mocked_ctor.assert_called_once_with(max_workers=2)

    def test_get_executor_reuses_existing_executor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        parser = core.TreeSitterParser(max_workers=2)
        executor = MagicMock(name="cached_executor")
        parser._executor = executor
        monkeypatch.setattr(core, "ProcessPoolExecutor", MagicMock())

        result = parser._get_executor()

        assert result is executor
        core.ProcessPoolExecutor.assert_not_called()

    def test_shutdown_clears_executor(self) -> None:
        parser = core.TreeSitterParser()
        executor = MagicMock()
        parser._executor = executor

        parser.shutdown()

        executor.shutdown.assert_called_once_with(wait=True)
        assert parser._executor is None

    def test_get_parser_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        instance = core.TreeSitterParser()
        factory = MagicMock(return_value=instance)
        monkeypatch.setattr(core, "TreeSitterParser", factory)
        monkeypatch.setattr(core, "_global_parser", None)

        first = core.get_parser()
        second = core.get_parser()

        assert first is instance
        assert second is instance
        factory.assert_called_once()
