"""End-to-end test: canonical AgentMetadata / SkillMetadata shapes.

Phase 10 task 5 of the bodai-skill-agent-distribution plan.

Goal
----
Verify that ``AgentMetadata`` and ``SkillMetadata`` exposed by every Bodai
component (``akosha``, ``mahavishnu``, ``session-buddy``, ``crackerjack``)
resolve to the same class object as the canonical schemas in
``mcp_common.canonical_schemas``. The canonical schema is the wire shape
returned by ``mcp__<server>__list_agents`` / ``mcp__<server>__get_agent``
(and the same for skills), so a divergence between components would
break federation clients.

Design intent
-------------
The brief specifies the alias pattern:

    # <component>/<component>/mcp/agent_schema.py
    from mcp_common.canonical_schemas.agent import AgentCanonicalSchema
    AgentMetadata = AgentCanonicalSchema

This pattern means ``AgentMetadata IS AgentCanonicalSchema`` holds at
runtime — Python treats ``AgentMetadata`` as the same class object.
Per-repo additions live in the ``agents_tools`` layer (not the schema
layer) so the canonical class object stays shared.

Constraint: this test runs in mcp-common's venv. Other repos' packages
are NOT installed. The find_spec + AST pattern documented below is the
canonical way to verify cross-repo schema consistency without dragging
every Bodai component into mcp-common's test dependency set.

find_spec + AST pattern
-----------------------
``importlib.util.find_spec(<module_path>)`` returns a ``ModuleSpec``
without importing the module. When the spec's ``origin`` is set, the
module's source file is at that path and we can read + AST-parse it
to verify imports and module-level assignments. This is sufficient to
prove ``AgentMetadata IS AgentCanonicalSchema`` at runtime:

- Source imports ``AgentCanonicalSchema`` from the canonical path, AND
- Source has a module-level ``AgentMetadata = AgentCanonicalSchema``,

then by Python's import semantics, ``from <component>.mcp.agent_schema
import AgentMetadata`` will resolve to the canonical class object.
The ``IS`` check is implicitly satisfied; we don't need to trigger
the import chain.

When ``find_spec`` returns ``None`` (the parent package is not
installed in this venv), we skip with a docstring note. The test
runs fully when executed from a component's own dev venv where the
parent package is editable-installed.

Refs:
- docs/superpowers/plans/2026-09-14-dhara-mcp-decomposition-implementation.md
  Phase 10 task 5
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mcp_common.canonical_schemas import (
    AgentCanonicalSchema,
    SkillCanonicalSchema,
)

if TYPE_CHECKING:
    pass


# Component repos under test. Each entry is the importable top-level
# package name (matches the directory name on disk + the wheel name).
COMPONENTS: tuple[str, ...] = (
    "akosha",
    "mahavishnu",
    "session_buddy",
    "crackerjack",
)

# Canonical schema import paths. These match the layout of
# mcp_common.canonical_schemas.{agent,skill}.
CANONICAL_AGENT_PATH = "mcp_common.canonical_schemas.agent"
CANONICAL_AGENT_NAME = "AgentCanonicalSchema"
CANONICAL_AGENT_ALIAS = "AgentMetadata"

CANONICAL_SKILL_PATH = "mcp_common.canonical_schemas.skill"
CANONICAL_SKILL_NAME = "SkillCanonicalSchema"
CANONICAL_SKILL_ALIAS = "SkillMetadata"


def _resolve_schema_source(component: str, schema_kind: str) -> Path | None:
    """Return the source path for ``<component>.mcp.<schema_kind>_schema``.

    Uses ``importlib.util.find_spec`` so we don't trigger the import
    chain (which would require all the component's runtime deps).
    Returns ``None`` when the parent package is not installed in
    the current venv — callers should ``pytest.skip`` in that case.
    """
    module_name = f"{component}.mcp.{schema_kind}_schema"
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    if spec is None or not spec.origin:
        return None
    return Path(spec.origin)


def _ast_find_module_import_from(tree: ast.Module, module: str, name: str) -> bool:
    """Return True iff the module AST has ``from <module> import <name>``.

    Walks the whole tree (not just body) to handle nested patterns
    where an import lives inside a try/except, but most cross-repo
    shims put the canonical import at module level so tree.body is
    sufficient. Walking is cheap and forgiving.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            if any(alias.name == name for alias in node.names):
                return True
    return False


def _ast_find_module_alias(tree: ast.Module, alias_name: str, target_name: str) -> bool:
    """Return True iff the module AST has top-level ``alias_name = target_name``.

    The brief specifies the alias pattern ``AgentMetadata = AgentCanonicalSchema``
    at module scope — a plain assignment, NOT a class definition. A subclass
    like ``class AgentMetadata(AgentCanonicalSchema): ...`` would fail this
    check, which is the desired behavior (a subclass is a different class
    object, not an alias).
    """
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == alias_name:
                if isinstance(node.value, ast.Name) and node.value.id == target_name:
                    return True
    return False


def _is_alias_via_static_analysis(
    component: str,
    schema_kind: str,
    canonical_module: str,
    canonical_name: str,
    alias_name: str,
) -> bool:
    """Static-analysis proof that ``from <component>.mcp.<schema>_schema import <alias>``
    resolves to ``<canonical_name>`` at runtime.

    Returns ``True`` iff:

    1. ``find_spec(<component>.mcp.<schema>_schema)`` returns a spec with origin.
    2. The source file at spec.origin contains
       ``from <canonical_module> import <canonical_name>``.
    3. The source file has a top-level assignment
       ``<alias_name> = <canonical_name>``.
    """
    source_path = _resolve_schema_source(component, schema_kind)
    if source_path is None:
        return False
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    return (
        _ast_find_module_import_from(tree, canonical_module, canonical_name)
        and _ast_find_module_alias(tree, alias_name, canonical_name)
    )


def _try_dynamic_import_alias(
    component: str,
    schema_kind: str,
    alias_name: str,
) -> object | None:
    """Best-effort dynamic import for components whose parent package
    is installed in this venv.

    Returns the resolved attribute (``AgentMetadata`` or
    ``SkillMetadata``) when importable, else ``None``. Used to add a
    stronger runtime check on top of the static-analysis proof.
    """
    module_name = f"{component}.mcp.{schema_kind}_schema"
    try:
        module = importlib.import_module(module_name)
    except (ImportError, ModuleNotFoundError):
        return None
    return getattr(module, alias_name, None)


# ---------------------------------------------------------------------------
# Canonical-path sanity (always runs; mcp_common IS the host of the canonical)
# ---------------------------------------------------------------------------


def test_canonical_schemas_module_imports() -> None:
    """Sanity: the canonical schemas must be importable from mcp_common itself.

    This is the always-runs baseline. If this fails, the test environment
    is broken (mcp_common is not installed or canonical_schemas is missing);
    nothing else can be evaluated.
    """
    from mcp_common.canonical_schemas import agent as canonical_agent_mod
    from mcp_common.canonical_schemas import skill as canonical_skill_mod

    assert hasattr(canonical_agent_mod, CANONICAL_AGENT_NAME)
    assert hasattr(canonical_skill_mod, CANONICAL_SKILL_NAME)
    assert AgentCanonicalSchema is canonical_agent_mod.AgentCanonicalSchema
    assert SkillCanonicalSchema is canonical_skill_mod.SkillCanonicalSchema


def test_canonical_agent_construction_equal() -> None:
    """Construction via the canonical path yields a usable AgentCanonicalSchema.

    The schema field set is what downstream consumers (Phase 4 federation
    clients, Akosha's knowledge graph, Mahavishnu's tool picker) rely on.
    A drift in field set breaks every consumer.
    """
    agent = AgentCanonicalSchema(
        name="sample-agent",
        version="1.0.0",
        description="Sample agent for canonical shape verification",
        capabilities=["sample"],
        owner="test",
    )

    # Identity fields are required.
    assert agent.name == "sample-agent"
    assert agent.version == "1.0.0"

    # Optional surface carries the documented defaults.
    assert agent.capabilities == ["sample"]
    assert agent.owner == "test"
    assert agent.metadata == {}
    assert agent.tools == []
    assert agent.dependencies == []
    assert agent.tool_refs == []
    assert agent.signature is None
    assert agent.server_pubkey_id is None

    # Round-trip through to_dict preserves the wire shape.
    dumped = agent.to_dict()
    assert dumped["name"] == "sample-agent"
    assert dumped["version"] == "1.0.0"
    assert dumped["description"] == "Sample agent for canonical shape verification"
    assert dumped["capabilities"] == ["sample"]
    assert dumped["owner"] == "test"
    assert dumped["schema_version"] == 1


def test_canonical_skill_construction_equal() -> None:
    """Construction via the canonical path yields a usable SkillCanonicalSchema."""
    skill = SkillCanonicalSchema(
        name="sample-skill",
        version="1.0.0",
        description="Sample skill for canonical shape verification",
        tags=["sample"],
        owner="test",
    )

    assert skill.name == "sample-skill"
    assert skill.version == "1.0.0"
    assert skill.tags == ["sample"]
    assert skill.owner == "test"
    assert skill.metadata == {}
    assert skill.tool_refs == []
    assert skill.dependencies == []
    assert skill.allowed_tools == []
    assert skill.signature is None
    assert skill.server_pubkey_id is None
    assert skill.content_type == "skill"
    assert skill.body_format == "yaml-frontmatter+markdown"

    dumped = skill.to_dict()
    assert dumped["name"] == "sample-skill"
    assert dumped["version"] == "1.0.0"
    assert dumped["description"] == "Sample skill for canonical shape verification"
    assert dumped["tags"] == ["sample"]
    assert dumped["schema_version"] == 1


# ---------------------------------------------------------------------------
# Static-analysis proof per component (works without the component installed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("component", COMPONENTS)
def test_agent_metadata_aliases_canonical_static(component: str) -> None:
    """Static proof that ``<component>.mcp.agent_schema.AgentMetadata`` aliases the canonical.

    Uses find_spec + AST (documented above). Skips when the parent
    package is not installed in this venv — the test still runs in
    every component's own dev venv because each component has itself
    editable-installed.
    """
    source_path = _resolve_schema_source(component, "agent")
    if source_path is None:
        pytest.skip(
            f"{component!r} is not installed in this venv; "
            "run from the component's own dev venv to exercise this check."
        )

    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    assert _ast_find_module_import_from(tree, CANONICAL_AGENT_PATH, CANONICAL_AGENT_NAME), (
        f"{source_path}: must import {CANONICAL_AGENT_NAME} from "
        f"{CANONICAL_AGENT_PATH!r} (the canonical envelope contract)."
    )
    assert _ast_find_module_alias(tree, CANONICAL_AGENT_ALIAS, CANONICAL_AGENT_NAME), (
        f"{source_path}: must have a module-level "
        f"{CANONICAL_AGENT_ALIAS} = {CANONICAL_AGENT_NAME} alias. "
        "A subclass (e.g. class AgentMetadata(AgentCanonicalSchema)) is NOT "
        "an alias and breaks the IS-equals-canonical contract."
    )


@pytest.mark.parametrize("component", COMPONENTS)
def test_skill_metadata_aliases_canonical_static(component: str) -> None:
    """Static proof that ``<component>.mcp.skill_schema.SkillMetadata`` aliases the canonical."""
    source_path = _resolve_schema_source(component, "skill")
    if source_path is None:
        pytest.skip(
            f"{component!r} is not installed in this venv; "
            "run from the component's own dev venv to exercise this check."
        )

    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    assert _ast_find_module_import_from(tree, CANONICAL_SKILL_PATH, CANONICAL_SKILL_NAME), (
        f"{source_path}: must import {CANONICAL_SKILL_NAME} from "
        f"{CANONICAL_SKILL_PATH!r} (the canonical envelope contract)."
    )
    assert _ast_find_module_alias(tree, CANONICAL_SKILL_ALIAS, CANONICAL_SKILL_NAME), (
        f"{source_path}: must have a module-level "
        f"{CANONICAL_SKILL_ALIAS} = {CANONICAL_SKILL_NAME} alias."
    )


# ---------------------------------------------------------------------------
# Dynamic verification (only when the component package is installed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("component", COMPONENTS)
def test_agent_metadata_is_canonical_dynamic(component: str) -> None:
    """Runtime proof: ``from <component>.mcp.agent_schema import AgentMetadata`` resolves
    to the SAME class object as the canonical AgentCanonicalSchema.

    Only runs when the component's parent package is installed in this
    venv. This is a stronger check than the static analysis above: it
    catches runtime import machinery issues (re-exports, conditional
    imports, lazy loaders) that AST can't see.
    """
    alias = _try_dynamic_import_alias(component, "agent", CANONICAL_AGENT_ALIAS)
    if alias is None:
        pytest.skip(
            f"{component!r} is not installed in this venv; "
            "the static-analysis check above provides equivalent coverage."
        )

    assert alias is AgentCanonicalSchema, (
        f"{component}.mcp.agent_schema.{CANONICAL_AGENT_ALIAS} is not the "
        f"same class object as {CANONICAL_AGENT_NAME}. Federation clients "
        "rely on identity (IS) equality, not just shape."
    )


@pytest.mark.parametrize("component", COMPONENTS)
def test_skill_metadata_is_canonical_dynamic(component: str) -> None:
    """Runtime proof for SkillMetadata (mirrors the AgentMetadata check above)."""
    alias = _try_dynamic_import_alias(component, "skill", CANONICAL_SKILL_ALIAS)
    if alias is None:
        pytest.skip(
            f"{component!r} is not installed in this venv; "
            "the static-analysis check above provides equivalent coverage."
        )

    assert alias is SkillCanonicalSchema, (
        f"{component}.mcp.skill_schema.{CANONICAL_SKILL_ALIAS} is not the "
        f"same class object as {CANONICAL_SKILL_NAME}."
    )


# ---------------------------------------------------------------------------
# End-to-end construction parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("component", COMPONENTS)
def test_agent_metadata_construction_via_alias(component: str) -> None:
    """Construct a sample through the canonical class and verify the alias path
    produces an object equal in shape.

    The brief: "Constructs a sample AgentCanonicalSchema via the canonical
    path, then verifies the same construction via each alias yields an
    equal object."

    When the alias is the canonical class (IS-equal), the two objects
    compare equal. When the alias is a subclass, equality falls through
    to Pydantic's model equality (field-by-field) and still holds.
    When the alias is a different class entirely (e.g. mahavishnu's
    legacy local class), this check fails — surfacing the migration gap.
    """
    canonical_agent = AgentCanonicalSchema(
        name="parity-agent",
        version="1.0.0",
        description="Parity check across components",
        capabilities=["parity"],
        owner=component,
    )

    alias_cls = _try_dynamic_import_alias(component, "agent", CANONICAL_AGENT_ALIAS)
    if alias_cls is None:
        pytest.skip(
            f"{component!r} is not installed in this venv; "
            "shape parity via the alias cannot be exercised here."
        )

    # Same construction kwargs through the alias path.
    alias_agent = alias_cls(
        name="parity-agent",
        version="1.0.0",
        description="Parity check across components",
        capabilities=["parity"],
        owner=component,
    )

    assert alias_agent.model_dump() == canonical_agent.model_dump(), (
        f"{component}.mcp.agent_schema.{CANONICAL_AGENT_ALIAS} produces a "
        "different shape than the canonical AgentCanonicalSchema. "
        "Check field set, validators, and defaults."
    )


@pytest.mark.parametrize("component", COMPONENTS)
def test_skill_metadata_construction_via_alias(component: str) -> None:
    """Skill counterpart of the agent parity check above."""
    canonical_skill = SkillCanonicalSchema(
        name="parity-skill",
        version="1.0.0",
        description="Parity check across components",
        tags=["parity"],
        owner=component,
    )

    alias_cls = _try_dynamic_import_alias(component, "skill", CANONICAL_SKILL_ALIAS)
    if alias_cls is None:
        pytest.skip(
            f"{component!r} is not installed in this venv; "
            "shape parity via the alias cannot be exercised here."
        )

    alias_skill = alias_cls(
        name="parity-skill",
        version="1.0.0",
        description="Parity check across components",
        tags=["parity"],
        owner=component,
    )

    assert alias_skill.model_dump() == canonical_skill.model_dump(), (
        f"{component}.mcp.skill_schema.{CANONICAL_SKILL_ALIAS} produces a "
        "different shape than the canonical SkillCanonicalSchema."
    )
