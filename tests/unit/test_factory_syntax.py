"""Regression tests for mcp_common.cli.factory ``except`` clause syntax.

Plan 2026-08-25 Task 0.5: ``mcp_common/cli/factory.py`` historically
contained two ``except ValueError, OSError:`` clauses (lines 530 and 745)
that were invalid syntax under Python 3 at the time.  The module would
refuse to parse, which would cascade into ``register_lifecycle_handlers``
silently mounting broken handlers in Phase 4.2.

These tests guard against reintroduction:

1. TestFactoryModuleImports — forces module load (would raise
   ``SyntaxError`` on Python 3 if any invalid ``except`` slips back).
2. TestFactoryExceptSyntax — uses ``ast`` to scan the source for a broken
   ``except`` clause and fails loudly if one is found.  This is stronger
   than just importing because it survives syntax being moved between
   sites.

A note on the comma form.  ``except A, B:`` without parentheses is valid
syntax under Python 3.14 (PEP 758), and it is the form this package uses:
``ruff format`` at ``target-version = py314`` rewrites ``except (A, B):``
back to the comma form, so the parenthesised spelling cannot survive a
formatting run.  The clause that is still broken is the Python 2 *binding*
form ``except A, e:`` — PEP 758 parses that as the tuple ``(A, e)``, so
``e`` is looked up as a class when the handler runs and the error path
dies with ``NameError`` instead of catching anything.
"""

from __future__ import annotations

import ast
import builtins
import importlib.util
import re
from pathlib import Path

import pytest

FACTORY_PATH = (
    Path(__file__).resolve().parents[2] / "mcp_common" / "cli" / "factory.py"
)


class TestFactoryModuleImports:
    """Force the module to import.  A ``SyntaxError`` here means the file
    no longer parses under Python 3."""

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
    """Scan the factory source for broken ``except`` clauses.

    The comma form ``except A, B:`` is legal under Python 3.14 (PEP 758)
    and is what ``ruff format`` emits for this package, so it is not an
    offender.  The Python 2 binding form ``except A, e:`` is: PEP 758
    parses it as the tuple ``(A, e)``, so ``e`` is resolved as a class
    when the handler runs and the error path dies with ``NameError``
    instead of catching anything.
    """

    @pytest.fixture
    def factory_source(self) -> str:
        return FACTORY_PATH.read_text(encoding="utf-8")

    @pytest.fixture
    def factory_tree(self, factory_source: str) -> ast.Module:
        return ast.parse(factory_source)

    @pytest.fixture
    def exception_names(self, factory_tree: ast.Module) -> set[str]:
        """Names that resolve to a class in this module's namespace.

        A PEP 758 handler may only list exception classes.  The builtins
        that subclass ``BaseException`` are known without looking at the
        module; for the rest, any name the module binds (a class it
        defines, or an alias it imports) is accepted, so this check
        reports a *variable* used as an exception type rather than
        second-guessing which classes are exceptions.
        """
        names = {
            name
            for name in dir(builtins)
            if isinstance(getattr(builtins, name, None), type)
            and issubclass(getattr(builtins, name), BaseException)
        }
        for node in ast.walk(factory_tree):
            if isinstance(node, ast.ClassDef):
                names.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add((alias.asname or alias.name).split(".")[0])
        return names

    def test_no_python2_binding_form_except(
        self, factory_tree: ast.Module, exception_names: set[str]
    ) -> None:
        """Every member of a PEP 758 handler tuple must be an exception class.

        ``except ValueError, e:`` binds nothing under PEP 758 — it asks to
        catch ``ValueError`` or ``e``, and ``e`` is a name lookup that
        raises ``NameError`` the moment the handler runs.
        """
        offenders: list[str] = []
        for node in ast.walk(factory_tree):
            if not isinstance(node, ast.ExceptHandler) or node.type is None:
                continue
            if not isinstance(node.type, ast.Tuple):
                continue
            for element in node.type.elts:
                if isinstance(element, ast.Name) and element.id not in exception_names:
                    offenders.append(
                        f"line {node.lineno}: '{element.id}' is not an exception class"
                    )
        if offenders:
            formatted = "\n".join(f"  {offender}" for offender in offenders)
            msg = (
                "Python 2 binding-form 'except' clauses detected:\n"
                f"{formatted}\n"
                "List real exception classes, or bind with 'except A as e:'."
            )
            raise AssertionError(msg)

    def test_no_python2_binding_form_textually(self, factory_source: str) -> None:
        """Textual counterpart of the AST check, for CI log localisation.

        Flags ``except A, e:`` where the second element is lower-case —
        a variable name rather than an exception class.  Upper-case names
        (``except ValueError, OSError:``) are the PEP 758 comma form and
        are left alone.
        """
        pattern = re.compile(r"^\s*except\s+[A-Za-z_][\w.]*\s*,\s*([a-z_]\w*)\s*:")
        offenders: list[tuple[int, str]] = []
        for lineno, line in enumerate(factory_source.splitlines(), start=1):
            if pattern.search(line):
                offenders.append((lineno, line.rstrip()))
        if offenders:
            formatted = "\n".join(f"  line {n}: {text}" for n, text in offenders)
            msg = (
                "Python 2 binding-form 'except' clauses detected:\n"
                f"{formatted}\n"
                "List real exception classes, or bind with 'except A as e:'."
            )
            raise AssertionError(msg)

    def test_every_except_handler_uses_tuple_or_as(
        self, factory_tree: ast.Module
    ) -> None:
        """Walk the AST and ensure each ``except`` is bound correctly.

        Valid shapes:
        - ``except A, B:`` (PEP 758) or ``except (A, B):``, where the type
          node is a ``Tuple`` ast node.
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


# Note: a previous ``test_factory_fix_anchors_530_and_745`` regression guard
# pinned the specific lines modernised by Plan 2026-08-25 Task 0.5.  It has
# been removed because:
#
# 1. The file grew past those line numbers; the pinned locations no longer
#    contain ``except`` clauses at all (line 530 became a comment, line 745
#    became a closing paren).
# 2. New instances of the same bug appeared at lines 587 and 802,
#    completely missing the pinned guard.
# 3. The AST-based ``test_no_python2_binding_form_except`` and
#    ``test_every_except_handler_uses_tuple_or_as`` tests above already
#    cover the actual invariant with stronger guarantees and without
#    line-number brittleness.
