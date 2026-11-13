"""Guard that every MCP tool this package publishes carries a description.

FastMCP derives a tool's ``description`` from the docstring of the
function it registers. A function without a docstring is published with
``description: null``, and MCP clients that require a description treat
the tool as unusable. qwen-code counts exactly this:

    invalidToolCount: serverTools.filter(x => !x.name || !x.description).length

Both factories in this package register their tools through a nested
function inside a ``register(app)`` closure, so a docstring missing on
that nested function is invisible at the call site and invisible in a
code review of the caller. That is how ``<server>_list_agents``,
``<server>_get_agent``, ``<server>_list_skills`` and
``<server>_get_skill`` shipped with ``description: null`` on all five
Bodai servers.

The dynamic tests below publish the tools through a real FastMCP app and
assert the wire shape. The static test scans the package so a future
tool cannot reintroduce the gap without a failing test, and so the
scan cannot silently stop matching.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP

from mcp_common.agents_tools import build_register_agents_tools
from mcp_common.canonical_schemas.agent import AgentCanonicalSchema
from mcp_common.canonical_schemas.skill import SkillCanonicalSchema
from mcp_common.skills_tools import build_register_skills_tools

PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "mcp_common"

TOOL_DECORATOR_ATTR = "tool"


# --- Fixtures ----------------------------------------------------------


def _agent_catalog() -> list[dict[str, Any]]:
    """A one-agent catalog, enough to build the factory."""
    return [
        {
            "name": "alpha-specialist",
            "version": "1.0.0",
            "description": "Use proactively for alpha questions.",
            "model": "sonnet",
            "system_prompt": "# alpha\n\nBody for alpha.",
            "tools": ["mcp__test__tool_a"],
        },
    ]


def _skill_catalog() -> list[dict[str, Any]]:
    """A one-skill catalog, enough to build the factory."""
    return [
        {
            "name": "run-quality-checks",
            "body_filename": "run-quality-checks.md",
            "version": "1.0.0",
            "description": "Run the full quality workflow.",
            "tool_refs": ["mcp__test__tool_a"],
        },
    ]


def _agent_sign(metadata: AgentCanonicalSchema) -> AgentCanonicalSchema:
    """sign() callback that only populates the signing fields."""
    return metadata.model_copy(
        update={"signature": "deadbeef" * 8, "server_pubkey_id": "test-key-id"},
    )


def _skill_sign(metadata: SkillCanonicalSchema) -> SkillCanonicalSchema:
    """sign() callback that only populates the signing fields."""
    return metadata.model_copy(
        update={"signature": "deadbeef" * 8, "server_pubkey_id": "test-key-id"},
    )


def _body_loader(name: str) -> str:
    """body_loader callback returning a fixed body."""
    return f"---\nname: {name}\n---\n# Body for {name}"


async def _published(register: Any) -> dict[str, str | None]:
    """Publish ``register``'s tools on a real FastMCP app.

    Returns a mapping of published tool name to description.
    """
    app = FastMCP("mcp-common-description-guard")
    register(app)
    tools = await app.list_tools()
    return {tool.name: tool.description for tool in tools}


# --- Dynamic guards ---------------------------------------------------


async def test_agent_tools_publish_a_description() -> None:
    """The agent tools must be published with a non-empty description."""
    register = build_register_agents_tools(
        server_key="mahavishnu",
        catalog=_agent_catalog(),
        body_loader=_body_loader,
        sign=_agent_sign,
        tool_name_prefix="mahavishnu_",
    )
    published = await _published(register)

    assert set(published) == {"mahavishnu_list_agents", "mahavishnu_get_agent"}
    missing = sorted(name for name, desc in published.items() if not (desc or "").strip())
    assert not missing, (
        f"tools published without a description: {missing}. FastMCP derives "
        "the description from the function docstring, so the registered "
        "function needs one."
    )


async def test_skill_tools_publish_a_description() -> None:
    """The skill tools must be published with a non-empty description."""
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_skill_catalog(),
        body_loader=_body_loader,
        sign=_skill_sign,
        tool_name_prefix="crackerjack_",
    )
    published = await _published(register)

    assert set(published) == {"crackerjack_list_skills", "crackerjack_get_skill"}
    missing = sorted(name for name, desc in published.items() if not (desc or "").strip())
    assert not missing, (
        f"tools published without a description: {missing}. FastMCP derives "
        "the description from the function docstring, so the registered "
        "function needs one."
    )


async def test_bare_names_still_publish_a_description() -> None:
    """The default (unprefixed) naming must publish descriptions too."""
    register = build_register_agents_tools(
        server_key="akosha",
        catalog=_agent_catalog(),
        body_loader=_body_loader,
        sign=_agent_sign,
    )
    published = await _published(register)

    assert set(published) == {"list_agents", "get_agent"}
    missing = sorted(name for name, desc in published.items() if not (desc or "").strip())
    assert not missing, f"tools published without a description: {missing}"


# --- Static guard -----------------------------------------------------


def _tool_decorated_functions() -> list[tuple[str, int, str]]:
    """Every function in the package carrying a ``.tool(...)`` decorator.

    Returns ``(relative_path, lineno, function_name)`` triples.
    """
    found: list[tuple[str, int, str]] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == TOOL_DECORATOR_ATTR
                ):
                    found.append(
                        (str(path.relative_to(PACKAGE_ROOT.parent)), node.lineno, node.name)
                    )
    return found


def test_every_tool_function_has_a_docstring() -> None:
    """A tool function without a docstring publishes ``description: null``."""
    without_docstring: list[str] = []
    for relative_path, lineno, func_name in _tool_decorated_functions():
        path = PACKAGE_ROOT.parent / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == func_name
                and node.lineno == lineno
            ):
                docstring = ast.get_docstring(node)
                if not (docstring or "").strip():
                    without_docstring.append(f"{relative_path}:{lineno} {func_name}")
                break

    assert not without_docstring, (
        "tool functions registered without a docstring, so FastMCP publishes "
        "them with description: null and MCP clients count them as invalid: "
        f"{sorted(without_docstring)}"
    )


def test_the_static_scan_matches_the_tool_registrations() -> None:
    """Guard against the scan silently matching nothing."""
    found = _tool_decorated_functions()
    assert len(found) >= 4, (
        "expected at least the four tool functions registered by "
        f"build_register_agents_tools and build_register_skills_tools, "
        f"found {len(found)}: {found}"
    )
