"""Regression tests for mcp_common.cli.factory Python 2 except syntax.

Plan 2026-08-25 Task 0.5: ``mcp_common/cli/factory.py`` historically
contained two ``except ValueError, OSError:`` clauses (lines 530 and 745)
that are invalid syntax under Python 3.  The module would refuse to parse,
which would cascade into ``register_lifecycle_handlers`` silently
mounting broken handlers in Phase 4.2.

These tests guard against reintroduction:

1. TestFactoryModuleImports — forces module load (would raise
   ``SyntaxError`` on Python 3 if any comma-form ``except`` slips back).
2. TestFactoryExceptSyntax — uses ``ast`` to scan the source for any
   legacy comma-syntax ``except`` clause and fails loudly if one is
   found.  This is stronger than just importing because it survives
   syntax being moved between sites.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

FACTORY_PATH = (
    Path(__file__).resolve().parents[2] / "mcp_common" / "cli" / "factory.py"
)


class TestFactoryModuleImports:
    """Force the module to import.  Any Python 2 ``except`` syntax
    reintroduction would raise ``SyntaxError`` here."""

    def test_module_path_exists(self) -> None:
        assert FACTORY_PATH.is_file(), f"factory.py not found at {FACTORY_PATH}"

    def test_factory_module_importable(self) -> None:
        spec = importlib.util.find_spec("mcp_common.cli.factory")
        if spec is None:
            msg = "mcp_common.cli.factory must exist for CLI lifecycle support"
            raise AssertionError(msg)

    def test_factory_module_loads_without_syntax_error(self) -> None:
        import mcp_common.cli.factory  # noqa: F401  pylint: disable=import-outside-toplevel


class TestFactoryExceptSyntax:
    """Scan the factory source for any legacy comma-form ``except``
    clause.  Python 3 rejects ``except A, B:`` (treats B as the bound
    name).  Only ``except (A, B):`` and ``except A as e:`` are valid."""

    @pytest.fixture
    def factory_source(self) -> str:
        return FACTORY_PATH.read_text(encoding="utf-8")

    @pytest.fixture
    def factory_tree(self, factory_source: str) -> ast.Module:
        return ast.parse(factory_source)

    def _iter_except_handlers(
        self, tree: ast.Module
    ) -> list[tuple[ast.ExceptHandler, ast.AST]]:
        """Yield ``(handler, type_node)`` for each non-empty ``except``."""
        handlers: list[tuple[ast.ExceptHandler, ast.AST]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None:
                continue
            handlers.append((node, node.type))
        return handlers

    def test_no_python2_comma_form_except(self, factory_source: str) -> None:
        """Reject the literal text ``except A, B:`` anywhere in the file.

        The ast-based test below is the source of truth, but a textual
        grep makes failures easier to localise in CI logs."""
        import re

        pattern = re.compile(r"^\s*except\s+[A-Za-z_][\w.]*\s*,\s*[A-Za-z_]")
        offenders: list[tuple[int, str]] = []
        for lineno, line in enumerate(factory_source.splitlines(), start=1):
            if pattern.search(line):
                offenders.append((lineno, line.rstrip()))
        if offenders:
            formatted = "\n".join(f"  line {n}: {text}" for n, text in offenders)
            msg = (
                "Python 2 comma-form 'except' clauses detected:\n"
                f"{formatted}\n"
                "Modernise to 'except (A, B):' before merging."
            )
            raise AssertionError(msg)

    def test_every_except_handler_uses_tuple_or_as(
        self, factory_tree: ast.Module
    ) -> None:
        """Walk the AST and ensure each ``except`` is bound correctly.

        Valid shapes:
        - ``except Tuple:`` where the type node is a ``Tuple`` ast node.
        - ``except SomeClass as name:`` where the type node is a Name.
        """
        offenders: list[str] = []
        for node in ast.walk(factory_tree):
            if not isinstance(node, ast.ExceptHandler) or node.type is None:
                continue
            type_node = node.type
            if isinstance(type_node, ast.Tuple):
                continue
            if isinstance(type_node, ast.Name):
                continue
            if isinstance(type_node, ast.Attribute):
                continue
            offenders.append(
                f"line {node.lineno}: unsupported except type node: "
                f"{ast.dump(type_node)}"
            )
        if offenders:
            msg = (
                "Found 'except' handlers that are neither tuples nor "
                "single Name/Attribute:\n" + "\n".join(offenders)
            )
            raise AssertionError(msg)

    def test_factory_parses_cleanly(self, factory_source: str) -> None:
        """``ast.parse`` would raise ``SyntaxError`` on legacy syntax.

        This is the strictest check — if any line in the file is invalid
        Python 3, the test fails with the exact line number."""
        try:
            ast.parse(factory_source)
        except SyntaxError as exc:  # pragma: no cover - defensive
            msg = (
                f"mcp_common/cli/factory.py failed to parse at line "
                f"{exc.lineno}: {exc.msg}"
            )
            raise AssertionError(msg) from exc


def test_factory_fix_anchors_530_and_745() -> None:
    """Pin the specific lines that Task 0.5 modernised so future refactors
    can't silently re-break the same logic elsewhere without an explicit
    test update."""
    factory_text = FACTORY_PATH.read_text(encoding="utf-8")
    lines = factory_text.splitlines()

    target_lines = {530, 745}
    hits: dict[int, str] = {}
    for lineno in target_lines:
        if lineno > len(lines):
            msg = (
                f"factory.py has only {len(lines)} lines; expected a "
                f"handler near line {lineno}"
            )
            raise AssertionError(msg)
        stripped = lines[lineno - 1].strip()
        if "except" not in stripped or "OSError" not in stripped:
            msg = f"line {lineno} no longer catches OSError: {stripped!r}"
            raise AssertionError(msg)
        if "ValueError, OSError:" in stripped:
            msg = (
                f"line {lineno} reverted to Python 2 syntax: {stripped!r}"
            )
            raise AssertionError(msg)
        if "(ValueError, OSError)" not in stripped:
            msg = (
                f"line {lineno} expected parenthesized tuple form, "
                f"got: {stripped!r}"
            )
            raise AssertionError(msg)
        hits[lineno] = stripped

    assert hits.keys() == target_lines
