"""Branch-focused tests for mcp_common.code_graph.analyzer."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_common.code_graph.analyzer import (
    ClassNode,
    CodeGraphAnalyzer,
    FileNode,
    FunctionNode,
    ImportNode,
)


def _make_analyzer() -> CodeGraphAnalyzer:
    return CodeGraphAnalyzer(Path("/project"))


class TestSmallHelpers:
    def test_file_patterns_and_skips(self) -> None:
        analyzer = _make_analyzer()

        assert analyzer._get_file_pattern("python") == "*.py"
        assert analyzer._get_file_pattern("javascript") == "*.js"
        assert analyzer._get_file_pattern("typescript") == "*.ts"
        assert analyzer._get_file_pattern("rust") is None

        assert analyzer._should_skip_test_file(Path("tests/test_module.py")) is True
        assert analyzer._should_skip_test_file(Path("pkg/test_module.py")) is True
        assert analyzer._should_skip_test_file(Path("pkg/module_test.py")) is False
        assert analyzer._should_skip_non_source_dir(Path("pkg/.venv/module.py")) is True
        assert analyzer._should_skip_non_source_dir(Path("pkg/src/module.py")) is False

    def test_count_totals_counts_nodes_and_calls(self) -> None:
        analyzer = _make_analyzer()
        analyzer.nodes = {
            "file": FileNode(
                id="file",
                name="file.py",
                file_id="file",
                node_type="file",
                path="/project/file.py",
                language="python",
            ),
            "func": FunctionNode(
                id="func",
                name="func",
                file_id="file",
                node_type="function",
                is_export=True,
                start_line=1,
                end_line=2,
            ),
            "cls": ClassNode(
                id="cls",
                name="Cls",
                file_id="file",
                node_type="class",
                start_line=1,
                end_line=2,
            ),
            "imp": ImportNode(
                id="imp",
                name="os",
                file_id="file",
                node_type="import",
                module="os",
            ),
        }
        analyzer._call_graph = {"func": {"callee1", "callee2"}}
        stats = {
            "files_indexed": 0,
            "functions_indexed": 0,
            "classes_indexed": 0,
            "calls_indexed": 0,
            "imports_indexed": 0,
            "duration_ms": 0,
        }

        analyzer._count_totals(stats)

        assert stats == {
            "files_indexed": 0,
            "functions_indexed": 1,
            "classes_indexed": 1,
            "calls_indexed": 2,
            "imports_indexed": 1,
            "duration_ms": 0,
        }


class TestFileReadingAndParsing:
    @pytest.mark.asyncio
    async def test_process_language_unknown_returns_early(self) -> None:
        analyzer = _make_analyzer()
        stats = {"files_indexed": 0, "functions_indexed": 0, "classes_indexed": 0, "calls_indexed": 0, "imports_indexed": 0, "duration_ms": 0}

        await analyzer._process_language(Path("/project"), "rust", False, stats)

        assert stats["files_indexed"] == 0

    @pytest.mark.asyncio
    async def test_process_language_python_invokes_file_analysis(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "module.py").write_text("def main(): pass")
        analyzer = CodeGraphAnalyzer(tmp_path)
        analyze = AsyncMock()
        analyzer._analyze_python_file = analyze  # type: ignore[method-assign]
        stats = {"files_indexed": 0, "functions_indexed": 0, "classes_indexed": 0, "calls_indexed": 0, "imports_indexed": 0, "duration_ms": 0}

        await analyzer._process_language(tmp_path, "python", False, stats)

        analyze.assert_awaited_once()
        assert stats["files_indexed"] == 1

    @pytest.mark.asyncio
    async def test_process_language_non_python_skips_python_analysis(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "module.js").write_text("export const value = 1;")
        analyzer = CodeGraphAnalyzer(tmp_path)
        analyze = AsyncMock()
        analyzer._analyze_python_file = analyze  # type: ignore[method-assign]
        stats = {"files_indexed": 0, "functions_indexed": 0, "classes_indexed": 0, "calls_indexed": 0, "imports_indexed": 0, "duration_ms": 0}

        await analyzer._process_language(tmp_path, "javascript", False, stats)

        analyze.assert_not_awaited()
        assert stats["files_indexed"] == 1

    @pytest.mark.asyncio
    async def test_analyze_python_file_returns_when_read_fails(self, tmp_path: Path) -> None:
        file_path = tmp_path / "module.py"
        file_path.write_text("def main(): pass")
        analyzer = _make_analyzer()
        analyzer._read_file_content = AsyncMock(return_value=None)  # type: ignore[method-assign]
        parse_ast = AsyncMock()
        analyzer._parse_ast = parse_ast  # type: ignore[method-assign]

        await analyzer._analyze_python_file(file_path)

        parse_ast.assert_not_awaited()
        assert analyzer.nodes == {}

    @pytest.mark.asyncio
    async def test_analyze_python_file_returns_when_parse_fails(self, tmp_path: Path) -> None:
        file_path = tmp_path / "module.py"
        file_path.write_text("def main(): pass")
        analyzer = _make_analyzer()
        analyzer._read_file_content = AsyncMock(return_value="def main(): pass")  # type: ignore[method-assign]
        analyzer._parse_ast = AsyncMock(return_value=None)  # type: ignore[method-assign]

        await analyzer._analyze_python_file(file_path)

        assert analyzer.nodes == {}

    @pytest.mark.asyncio
    async def test_read_file_content_handles_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        file_path = tmp_path / "module.py"
        file_path.write_text("def main(): pass")
        analyzer = _make_analyzer()

        monkeypatch.setattr(Path, "read_text", MagicMock(side_effect=OSError("boom")))

        assert await analyzer._read_file_content(file_path) is None

    def test_parse_ast_handles_syntax_error(self) -> None:
        analyzer = _make_analyzer()
        assert asyncio_run(analyzer._parse_ast("def broken(", Path("broken.py"))) is None


def asyncio_run(awaitable):
    import asyncio

    return asyncio.run(awaitable)


class TestExtractionHelpers:
    def test_extract_imports_and_none(self) -> None:
        analyzer = _make_analyzer()

        import_node = ast.parse("import os as operating_system").body[0]
        from_node = ast.parse("from pkg import thing as alias").body[0]
        other_node = ast.parse("x = 1").body[0]

        result1 = analyzer._extract_import(import_node, "pkg/main.py")
        result2 = analyzer._extract_import(from_node, "pkg/main.py")
        result3 = analyzer._extract_import(other_node, "pkg/main.py")

        assert result1 is not None
        assert result1.module == "os"
        assert result1.alias == "operating_system"
        assert result2 is not None
        assert result2.is_from_import is True
        assert result2.imported_names == ["thing"]
        assert result3 is None

    def test_extract_class_and_function_branches(self) -> None:
        analyzer = _make_analyzer()

        class_node = ast.parse(
            """
class Child(Base, pkg.Parent):
    \"\"\"Docstring.\"\"\"
    pass
"""
        ).body[0]
        assert isinstance(class_node, ast.ClassDef)
        class_node.end_lineno = None

        func_node = ast.parse(
            """
def complex_func(x):
    \"\"\"Docstring.\"\"\"
    if x:
        for _ in range(1):
            while x:
                try:
                    helper()
                    obj.method()
                finally:
                    pass
    return x
"""
        ).body[0]
        assert isinstance(func_node, ast.FunctionDef)
        func_node.end_lineno = None

        class_result = analyzer._extract_class(class_node, "pkg/main.py", Path("pkg/main.py"))
        func_result = analyzer._extract_function(func_node, "pkg/main.py", Path("pkg/main.py"))

        assert class_result is not None
        assert class_result.base_classes == ["Base", "pkg.Parent"]
        assert class_result.docstring == "Docstring."
        assert class_result.end_line == class_result.start_line

        assert func_result is not None
        assert func_result.is_export is True
        assert func_result.complexity > 1
        assert "helper" in func_result.calls
        assert "obj.method" in func_result.calls
        assert func_result.end_line == func_result.start_line

        anon_call = ast.Call(func=ast.Constant(value=1), args=[], keywords=[])
        assert analyzer._extract_call_name(anon_call) is None

    def test_method_detection(self) -> None:
        analyzer = _make_analyzer()
        tree = ast.parse(
            """
class C:
    def method(self):
        return 1

def top_level():
    return 2
"""
        )
        method_node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "method")
        top_level_node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "top_level")

        assert analyzer._is_method(method_node, tree) is True
        assert analyzer._is_method(top_level_node, tree) is False

    def test_extract_and_add_helpers_skip_none_results(self) -> None:
        analyzer = _make_analyzer()
        tree = ast.parse(
            """
import os

class Example:
    pass

def top_level():
    return 1
"""
        )
        file_node = FileNode(
            id="pkg/main.py",
            name="main.py",
            file_id="pkg/main.py",
            node_type="file",
            path="/project/pkg/main.py",
            language="python",
        )

        analyzer._extract_import = MagicMock(return_value=None)  # type: ignore[method-assign]
        analyzer._extract_class = MagicMock(return_value=None)  # type: ignore[method-assign]
        analyzer._extract_function = MagicMock(return_value=None)  # type: ignore[method-assign]

        analyzer._extract_and_add_imports(tree, file_node, "pkg/main.py")
        analyzer._extract_and_add_definitions(tree, file_node, "pkg/main.py")

        assert file_node.imports == []
        assert file_node.classes == []
        assert file_node.functions == []

    def test_function_node_lookups_ignore_non_function_nodes(self) -> None:
        analyzer = _make_analyzer()
        analyzer.nodes = {
            "bad": SimpleNamespace(node_type="function", name="maybe", file_id="x")
        }

        assert analyzer._find_function_node("maybe") is None
        assert analyzer._find_function_by_name("maybe") is None


class TestFunctionContextAndRelations:
    def _build_graph(self) -> CodeGraphAnalyzer:
        analyzer = _make_analyzer()
        analyzer.nodes = {
            "pkg/main.py": FileNode(
                id="pkg/main.py",
                name="main.py",
                file_id="pkg/main.py",
                node_type="file",
                path="/project/pkg/main.py",
                language="python",
            ),
            "pkg/utils.py": FileNode(
                id="pkg/utils.py",
                name="utils.py",
                file_id="pkg/utils.py",
                node_type="file",
                path="/project/pkg/utils.py",
                language="python",
            ),
            "pkg/helpers.py": FileNode(
                id="pkg/helpers.py",
                name="helpers.py",
                file_id="pkg/helpers.py",
                node_type="file",
                path="/project/pkg/helpers.py",
                language="python",
            ),
            "pkg/main.py:function:caller": FunctionNode(
                id="pkg/main.py:function:caller",
                name="caller",
                file_id="pkg/main.py",
                node_type="function",
                is_export=True,
                start_line=1,
                end_line=4,
                calls=["helper", "missing"],
            ),
            "pkg/main.py:function:helper": FunctionNode(
                id="pkg/main.py:function:helper",
                name="helper",
                file_id="pkg/main.py",
                node_type="function",
                is_export=True,
                start_line=6,
                end_line=8,
            ),
            "pkg/other.py:function:external": FunctionNode(
                id="pkg/other.py:function:external",
                name="external",
                file_id="pkg/other.py",
                node_type="function",
                is_export=True,
                start_line=1,
                end_line=3,
                calls=["caller", "pkg/main.py:function:caller"],
            ),
            "pkg/main.py:import:pkg.utils": ImportNode(
                id="pkg/main.py:import:pkg.utils",
                name="utils.py",
                file_id="pkg/main.py",
                node_type="import",
                module="utils.py",
                is_from_import=False,
            ),
            "pkg/main.py:from:pkg.helpers:helper": ImportNode(
                id="pkg/main.py:from:pkg.helpers:helper",
                name="helper",
                file_id="pkg/main.py",
                node_type="import",
                module="helpers.py",
                is_from_import=True,
                imported_names=["helper"],
            ),
            "pkg/other.py:import:pkg.main": ImportNode(
                id="pkg/other.py:import:pkg.main",
                name="main.py",
                file_id="pkg/other.py",
                node_type="import",
                module="main.py",
                is_from_import=False,
                imported_names=["main.py"],
            ),
            "pkg/other.py:import:random": ImportNode(
                id="pkg/other.py:import:random",
                name="random",
                file_id="pkg/other.py",
                node_type="import",
                module="random",
                is_from_import=False,
                imported_names=["unrelated"],
            ),
            "ghost": FunctionNode(
                id="ghost",
                name="ghost",
                file_id="pkg/ghost.py",
                node_type="function",
                is_export=True,
                start_line=1,
                end_line=2,
                calls=["caller"],
            ),
        }
        analyzer._call_graph = {
            "pkg/main.py:function:caller": {"helper", "missing"},
            "pkg/other.py:function:external": {"caller", "pkg/main.py:function:caller"},
            "ghost": {"pkg/main.py:function:caller"},
        }
        return analyzer

    @pytest.mark.asyncio
    async def test_get_function_context_with_flags(self) -> None:
        analyzer = self._build_graph()

        context = await analyzer.get_function_context("caller")
        assert context["function"]["name"] == "caller"
        assert any(item["name"] == "external" for item in context["callers"])
        assert any(item["name"] == "helper" for item in context["callees"])

        slim_context = await analyzer.get_function_context(
            "caller",
            include_callers=False,
            include_callees=False,
        )
        assert slim_context["callers"] == []
        assert slim_context["callees"] == []

    @pytest.mark.asyncio
    async def test_find_related_files_and_aggregation(self) -> None:
        analyzer = self._build_graph()

        related = await analyzer.find_related_files("pkg/main.py", relationship_type="all", limit=10)

        paths = {item["file_path"] for item in related}
        assert "pkg/other.py" in paths
        assert "pkg/utils.py" in paths
        assert "pkg/helpers.py" in paths

        other = next(item for item in related if item["file_path"] == "pkg/other.py")
        assert set(other["relationship"]) >= {"imported_by", "called_by"}
        assert other["strength"] == 2

    @pytest.mark.asyncio
    async def test_find_related_files_imports_only(self) -> None:
        analyzer = self._build_graph()

        related = await analyzer.find_related_files("pkg/main.py", relationship_type="imports", limit=10)

        assert related

    @pytest.mark.asyncio
    async def test_find_related_files_calls_only(self) -> None:
        analyzer = self._build_graph()

        related = await analyzer.find_related_files("pkg/main.py", relationship_type="calls", limit=10)

        assert related

    @pytest.mark.asyncio
    async def test_find_related_files_called_by_only(self) -> None:
        analyzer = self._build_graph()

        related = await analyzer.find_related_files("pkg/main.py", relationship_type="called_by", limit=10)

        assert related

    def test_relationship_helpers_ignore_non_dataclass_nodes(self) -> None:
        analyzer = _make_analyzer()
        analyzer.nodes = {
            "pkg/main.py": SimpleNamespace(file_id="pkg/main.py", node_type="file", id="pkg/main.py"),
            "pkg/main.py:import:pkg.utils": SimpleNamespace(
                file_id="pkg/main.py",
                node_type="import",
                id="pkg/main.py:import:pkg.utils",
                module="utils.py",
                is_from_import=True,
                imported_names=["helper"],
            ),
            "pkg/other.py:import:pkg.main": SimpleNamespace(
                file_id="pkg/other.py",
                node_type="import",
                id="pkg/other.py:import:pkg.main",
                module="main.py",
                is_from_import=False,
                imported_names=["main.py"],
            ),
            "pkg/main.py:function:caller": SimpleNamespace(
                file_id="pkg/main.py",
                node_type="function",
                id="pkg/main.py:function:caller",
                name="caller",
                calls=[],
            ),
        }
        analyzer._call_graph = {
            "pkg/main.py:function:caller": {"helper"},
            "pkg/other.py:function:external": {"caller"},
        }

        imports, imports_from = analyzer._get_file_imports("pkg/main.py")
        imported_by = analyzer._find_imported_by_relationships("pkg/main.py")
        calls = analyzer._find_calls_relationships(["pkg/main.py:function:caller"], "pkg/main.py")
        called_by = analyzer._find_called_by_relationships(["pkg/main.py:function:caller"])
        callers = analyzer._get_callers("caller")

        assert imports == set()
        assert imports_from == set()
        assert imported_by == []
        assert calls == []
        assert called_by == []
        assert callers == []

    def test_call_relationship_helpers_skip_missing_nodes(self) -> None:
        analyzer = _make_analyzer()
        analyzer.nodes = {
            "pkg/main.py": FileNode(
                id="pkg/main.py",
                name="main.py",
                file_id="pkg/main.py",
                node_type="file",
                path="/project/pkg/main.py",
                language="python",
            ),
            "pkg/main.py:function:caller": FunctionNode(
                id="pkg/main.py:function:caller",
                name="caller",
                file_id="pkg/main.py",
                node_type="function",
                is_export=True,
                start_line=1,
                end_line=2,
            ),
        }
        analyzer._call_graph = {
            "pkg/main.py:function:caller": {"other"},
            "pkg/missing.py:function:ghost": {"caller"},
        }

        callers = analyzer._get_callers("target")
        callees = analyzer._get_callees(analyzer.nodes["pkg/main.py:function:caller"])
        called_by = analyzer._find_called_by_relationships(["pkg/main.py:function:caller"])
        no_match_called_by = analyzer._find_called_by_relationships(["pkg/other.py:function:ghost"])

        assert callers == []
        assert callees == []
        assert called_by == []
        assert no_match_called_by == []

    def test_function_node_lookups_return_none_when_missing(self) -> None:
        analyzer = self._build_graph()

        assert analyzer._find_function_node("missing") is None
        assert analyzer._find_function_by_name("missing") is None
