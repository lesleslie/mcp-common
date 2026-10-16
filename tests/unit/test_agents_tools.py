"""Tests for mcp_common.agents_tools.build_register_agents_tools.

The factory owns the wire shape, B-4 allowlist, body normalization,
content-hash (B-6), and the success/error envelope. These tests
exercise the mechanism end-to-end against a mock FastMCP app so a
regression in any of those surfaces fails loudly. Signing itself is
opaque to the factory (the per-server ``sign`` callable does the
canonicalize-then-sign work); these tests stub ``sign`` to assert
the factory calls it correctly and round-trips the result.
"""
from __future__ import annotations

import hashlib
import inspect
from typing import Any

import pytest

from mcp_common.agents_tools import build_register_agents_tools
from mcp_common.canonical_schemas.agent import AgentCanonicalSchema
from mcp_common.signing import SkillsSigner


# --- Mock FastMCP app --------------------------------------------------


class MockApp:
    """Minimal FastMCP stand-in.

    Real ``@app.tool(name=...)`` returns a decorator that registers
    the function under the given name. This mock captures the
    registered tool functions for direct inspection.
    """

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, *, name: str | None = None) -> Any:
        def decorator(fn: Any) -> Any:
            self.tools[name or fn.__name__] = fn
            return fn

        return decorator


# --- Test fixtures -----------------------------------------------------


def _real_signer() -> SkillsSigner:
    """Return a fresh SkillsSigner with a real ed25519 keypair."""
    return SkillsSigner.generate()


def _test_sign(server_key: str = "test") -> Any:
    """Build a sign() callable that uses a real SkillsSigner.

    The signing policy here is the simplest one that matches the
    spec: hash the system_prompt's bytes, sign the canonicalized
    metadata dict, attach the signature + key_id. The per-server
    implementations layer their own canonical_payload_for_signing
    on top, but the wire shape and field names match.
    """
    signer = _real_signer()

    def sign(metadata: AgentCanonicalSchema) -> AgentCanonicalSchema:
        # Use the schema's own to_dict() (which already does
        # model_dump(mode="json")) as the canonicalization
        # surface. Real per-server signers strip the signature
        # fields first; the factory treats that as opaque.
        canonical = metadata.to_dict()
        sig_b64 = signer.sign(canonical)
        return metadata.model_copy(
            update={
                "signature": sig_b64,
                "server_pubkey_id": "test-key-id",
            }
        )

    return sign


def _disk_body_loader(bodies: dict[str, str]) -> Any:
    """Build a body_loader that mimics the file-on-disk pattern."""
    def body_loader(name: str) -> str:
        if name not in bodies:
            raise FileNotFoundError(f"Agent body {name!r} missing from catalog")
        return bodies[name]

    return body_loader


def _inline_catalog() -> list[dict[str, Any]]:
    """Two-agent catalog with inline system_prompt for body_loader-free testing."""
    return [
        {
            "name": "alpha-specialist",
            "version": "1.0.0",
            "description": "Use proactively for alpha questions.",
            "model": "sonnet",
            "system_prompt": "# alpha\n\nBody for alpha.",
            "tools": ["mcp__test__tool_a"],
            "title": "Alpha Specialist",
            "category": "test",
            "owner": "test",
        },
        {
            "name": "beta-specialist",
            "version": "1.0.0",
            "description": "Use proactively for beta questions.",
            "model": "opus",
            "system_prompt": "# beta\n\nBody for beta.  ",
            "tools": ["mcp__test__tool_b"],
        },
    ]


def _disk_catalog() -> list[dict[str, Any]]:
    """Two-agent catalog that exercises the body_loader path."""
    return [
        {
            "name": "gamma-specialist",
            "version": "1.0.0",
            "description": "Use proactively for gamma questions.",
            "model": "sonnet",
        },
        {
            "name": "delta-specialist",
            "version": "1.0.0",
            "description": "Use proactively for delta questions.",
            "model": "opus",
        },
    ]


# --- Factory-shape tests ----------------------------------------------


def test_factory_returns_callable() -> None:
    """build_register_agents_tools returns a register(app) closure."""
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({"_": "unused"}),
        sign=_test_sign(),
    )
    assert callable(register)


def test_factory_rejects_bad_server_key() -> None:
    """B-4 enforcement at factory construction."""
    with pytest.raises(ValueError, match="server_key 'BadKey' violates B-4 allowlist"):
        build_register_agents_tools(
            server_key="BadKey",
            catalog=[],
            body_loader=_disk_body_loader({}),
            sign=_test_sign(),
        )


def test_factory_rejects_missing_name() -> None:
    """Catalog entries without a name fail at construction."""
    with pytest.raises(ValueError, match="missing 'name' field"):
        build_register_agents_tools(
            server_key="test",
            catalog=[{"description": "no name here"}],
            body_loader=_disk_body_loader({}),
            sign=_test_sign(),
        )


def test_factory_rejects_bad_name() -> None:
    """Catalog entry names must match the B-4 allowlist."""
    with pytest.raises(ValueError, match="name 'BadName' violates B-4 allowlist"):
        build_register_agents_tools(
            server_key="test",
            catalog=[{"name": "BadName", "description": "x"}],
            body_loader=_disk_body_loader({}),
            sign=_test_sign(),
        )


def test_factory_rejects_duplicate_names() -> None:
    """No two catalog entries may share a name."""
    catalog = [
        {"name": "dup", "description": "first"},
        {"name": "dup", "description": "second"},
    ]
    with pytest.raises(ValueError, match="duplicate catalog entry name: 'dup'"):
        build_register_agents_tools(
            server_key="test",
            catalog=catalog,
            body_loader=_disk_body_loader({}),
            sign=_test_sign(),
        )


# --- Tool-name prefix tests -------------------------------------------


def test_default_tool_name_prefix_is_empty() -> None:
    """Default registers tools as ``list_agents`` and ``get_agent`` (akosha convention)."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    assert "list_agents" in app.tools
    assert "get_agent" in app.tools


def test_custom_tool_name_prefix() -> None:
    """Non-empty prefix is prepended to the tool names."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
        tool_name_prefix="mahavishnu_",
    )
    register(app)
    assert "mahavishnu_list_agents" in app.tools
    assert "mahavishnu_get_agent" in app.tools
    # Default names are NOT registered when a prefix is set.
    assert "list_agents" not in app.tools
    assert "get_agent" not in app.tools


# --- list_agents tests ------------------------------------------------


async def test_list_agents_returns_metadata_list() -> None:
    """list_agents returns one dict per catalog entry with metadata populated."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["list_agents"]()
    assert isinstance(result, list)
    assert len(result) == 2
    names = {r["name"] for r in result}
    assert names == {"alpha-specialist", "beta-specialist"}


async def test_list_agents_metadata_fields() -> None:
    """Each entry carries the canonical schema fields."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["list_agents"]()
    alpha = next(r for r in result if r["name"] == "alpha-specialist")
    # Required fields are populated.
    assert alpha["id"] == "test:alpha-specialist:1.0.0"
    assert alpha["server_key"] == "test"
    assert alpha["description"] == "Use proactively for alpha questions."
    assert alpha["model"] == "sonnet"
    assert alpha["system_prompt"] == "# alpha\n\nBody for alpha."  # not stripped at list time
    assert alpha["tools"] == ["mcp__test__tool_a"]
    # B-6 invariant: content_hash matches the (stripped) body bytes.
    expected_hash = hashlib.sha256("# alpha\n\nBody for alpha.".encode("utf-8")).hexdigest()
    assert alpha["content_hash"] == expected_hash
    # List does NOT sign; both signing fields are None.
    assert alpha["signature"] is None
    assert alpha["server_pubkey_id"] is None


async def test_list_agents_calls_on_call_for_b7() -> None:
    """B-7: every list_agents call invokes the on_call hook."""
    app = MockApp()
    counter = {"calls": 0}

    def on_call() -> None:
        counter["calls"] += 1

    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
        on_call=on_call,
    )
    register(app)
    await app.tools["list_agents"]()
    await app.tools["list_agents"]()
    assert counter["calls"] == 2


async def test_list_agents_with_disk_body_loader() -> None:
    """When the catalog has no inline body, the factory calls body_loader."""
    app = MockApp()
    bodies = {
        "gamma-specialist": "# gamma\n\nDisk-loaded body.\n",
        "delta-specialist": "# delta\n\nAnother body.\n",
    }
    register = build_register_agents_tools(
        server_key="test",
        catalog=_disk_catalog(),
        body_loader=_disk_body_loader(bodies),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["list_agents"]()
    gamma = next(r for r in result if r["name"] == "gamma-specialist")
    # The body is the stripped version of the disk file.
    assert gamma["system_prompt"] == "# gamma\n\nDisk-loaded body."
    expected_hash = hashlib.sha256("# gamma\n\nDisk-loaded body.".encode("utf-8")).hexdigest()
    assert gamma["content_hash"] == expected_hash


# --- get_agent tests --------------------------------------------------


async def test_get_agent_success_path() -> None:
    """get_agent returns success envelope with signed metadata + body."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["get_agent"]("alpha-specialist")
    assert result["success"] is True
    assert "metadata" in result
    assert "body" in result
    assert result["body"] == "# alpha\n\nBody for alpha."
    # The factory called sign() and the result has the signing fields populated.
    assert result["metadata"]["signature"] is not None
    assert result["metadata"]["server_pubkey_id"] == "test-key-id"


async def test_get_agent_signature_fields_are_well_formed() -> None:
    """The factory's contract: signature is a non-empty base64 string.

    The cryptographic round-trip is the per-server signer's job, not
    the factory's — real per-server signers canonicalize (stripping
    the signing fields themselves before signing) and the
    corresponding verify path knows to do the same. This test
    asserts the surface contract: the factory hands the server's
    ``sign()`` an unsigned metadata and returns the signed version
    with both ``signature`` and ``server_pubkey_id`` populated.
    """
    app = MockApp()
    captured: dict[str, AgentCanonicalSchema] = {}
    signer = _real_signer()

    def sign(metadata: AgentCanonicalSchema) -> AgentCanonicalSchema:
        # Per-server signers strip the signing fields before
        # canonicalization; mirror that here so the test exercises
        # the same shape the per-server codepath would.
        canonical = {
            k: v
            for k, v in metadata.to_dict().items()
            if k not in ("signature", "server_pubkey_id")
        }
        sig_b64 = signer.sign(canonical)
        captured["unsigned"] = metadata
        return metadata.model_copy(
            update={"signature": sig_b64, "server_pubkey_id": "real-key-id"}
        )

    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=sign,
    )
    register(app)
    result = await app.tools["get_agent"]("alpha-specialist")
    # Factory contract: signature is a non-empty base64 string and
    # the key_id is populated.
    assert isinstance(result["metadata"]["signature"], str)
    assert len(result["metadata"]["signature"]) > 0
    assert result["metadata"]["server_pubkey_id"] == "real-key-id"
    # The factory called sign() with the unsigned metadata (which is
    # what the canonical-signer pattern relies on).
    assert captured["unsigned"].signature is None
    assert captured["unsigned"].server_pubkey_id is None


async def test_get_agent_rejects_invalid_name() -> None:
    """B-4 at the API boundary: a path-traversal name returns the error envelope."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["get_agent"]("../etc/passwd")
    assert result["success"] is False
    assert "B-4" in result["error"]


async def test_get_agent_rejects_uppercase_name() -> None:
    """B-4 forbids uppercase characters in the name."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["get_agent"]("BadName")
    assert result["success"] is False
    assert "B-4" in result["error"]


async def test_get_agent_not_found() -> None:
    """A name that passes the allowlist but isn't in the catalog returns 'not found'."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["get_agent"]("nonexistent-agent")
    assert result["success"] is False
    assert "not found on this server" in result["error"]
    assert "nonexistent-agent" in result["error"]


async def test_get_agent_body_loader_error() -> None:
    """A missing body file surfaces as the error envelope, not an exception."""
    app = MockApp()
    # Catalog has no inline body; the loader will raise FileNotFoundError.
    catalog = [{"name": "missing-body", "description": "x", "model": "sonnet"}]
    register = build_register_agents_tools(
        server_key="test",
        catalog=catalog,
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["get_agent"]("missing-body")
    assert result["success"] is False
    assert "missing from catalog" in result["error"]


async def test_get_agent_sign_error() -> None:
    """When sign() raises, the error envelope carries the reason — no exception escape."""
    app = MockApp()

    def broken_sign(metadata: AgentCanonicalSchema) -> AgentCanonicalSchema:
        raise RuntimeError("signer not initialized")

    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=broken_sign,
    )
    register(app)
    result = await app.tools["get_agent"]("alpha-specialist")
    assert result["success"] is False
    assert "signing failed" in result["error"]
    assert "signer not initialized" in result["error"]


async def test_get_agent_sign_returns_wrong_type() -> None:
    """A buggy sign() that returns a non-AgentCanonicalSchema gets a clear error."""
    app = MockApp()

    def bad_sign(metadata: AgentCanonicalSchema) -> dict:
        return {"not": "a schema"}

    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=bad_sign,
    )
    register(app)
    result = await app.tools["get_agent"]("alpha-specialist")
    assert result["success"] is False
    assert "AgentCanonicalSchema" in result["error"]


async def test_get_agent_calls_on_call_for_b7() -> None:
    """B-7: every get_agent call invokes the on_call hook (even on the error path)."""
    app = MockApp()
    counter = {"calls": 0}

    def on_call() -> None:
        counter["calls"] += 1

    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
        on_call=on_call,
    )
    register(app)
    await app.tools["get_agent"]("alpha-specialist")
    await app.tools["get_agent"]("nonexistent")
    # B-7 counts every call regardless of outcome.
    assert counter["calls"] == 2


# --- Dynamic body synthesis (oneiric path B) --------------------------


async def test_dynamic_body_synthesis_for_oneiric_path_b() -> None:
    """The factory accepts a body_loader that synthesizes bodies on the fly.

    This is the test for the "oneiric path B" design: the catalog
    is generated at server startup from the adapter registry,
    each entry's body is computed (not read from disk) by a
    closure over the domain, and the factory handles it the same
    way as the disk-file case.
    """
    # Simulate: two domains, each with a synthesized body.
    catalog = [
        {
            "name": "llm-specialist",
            "version": "1.0.0",
            "description": "Use proactively for LLM adapter questions.",
            "model": "sonnet",
        },
        {
            "name": "vector-specialist",
            "version": "1.0.0",
            "description": "Use proactively for vector database questions.",
            "model": "sonnet",
        },
    ]

    def synthesize_body(name: str) -> str:
        # In production this would walk the adapter_registry for
        # the matching domain and emit a pointed body. The factory
        # only cares that body_loader(name) returns a string.
        domain = name.replace("-specialist", "")
        return (
            f"# {domain}-specialist\n\n"
            f"Use mcp__oneiric__oneiric_list_adapters(domain='{domain}') "
            f"to enumerate providers. Validate before deployment with "
            f"mcp__oneiric__oneiric_validate_adapter.\n"
        )

    register = build_register_agents_tools(
        server_key="oneiric",
        catalog=catalog,
        body_loader=synthesize_body,
        sign=_test_sign(),
        tool_name_prefix="oneiric_",
    )
    app = MockApp()
    register(app)
    # list path
    listing = await app.tools["oneiric_list_agents"]()
    llm = next(r for r in listing if r["name"] == "llm-specialist")
    assert "domain='llm'" in llm["system_prompt"]
    # get path
    result = await app.tools["oneiric_get_agent"]("vector-specialist")
    assert result["success"] is True
    # The synthesized body uses the name's "domain" portion, which
    # is the name minus the "-specialist" suffix. Match exactly
    # what synthesize_body() emits so the B-6 hash assertion is on
    # the actual bytes, not a near-match.
    expected_body = (
        "# vector-specialist\n\n"
        "Use mcp__oneiric__oneiric_list_adapters(domain='vector') "
        "to enumerate providers. Validate before deployment with "
        "mcp__oneiric__oneiric_validate_adapter.\n"
    ).strip()
    assert result["body"] == expected_body
    assert "domain='vector'" in result["body"]
    # B-6 invariant: the content_hash matches the synthesized body.
    expected_hash = hashlib.sha256(expected_body.encode("utf-8")).hexdigest()
    assert result["metadata"]["content_hash"] == expected_hash


# --- Body normalization ------------------------------------------------


def test_body_normalization_strips_surrounding_whitespace() -> None:
    """A body with leading/trailing whitespace is normalized for B-6 hashing.

    Mirrors the strip in the akosha/mahavishnu/crackerjack
    ``_normalize_body`` helper — a Write-tool-emitted body often
    has a trailing newline. ``str.strip()`` only removes whitespace,
    so the frontmatter-prefix case is intentionally not tested
    here (that would be a different transformation).
    """
    bodies = {
        "trailing-newline": "Body text.\n",
        "leading-newline": "\n\nBody text.",
        "mixed": "  \n  Body text.  \n  ",
    }
    register = build_register_agents_tools(
        server_key="test",
        catalog=[
            {
                "name": "trailing-newline",
                "version": "1.0.0",
                "description": "x",
            },
            {
                "name": "leading-newline",
                "version": "1.0.0",
                "description": "x",
            },
            {
                "name": "mixed",
                "version": "1.0.0",
                "description": "x",
            },
        ],
        body_loader=_disk_body_loader(bodies),
        sign=_test_sign(),
    )
    app = MockApp()
    register(app)
    expected_hash = hashlib.sha256("Body text.".encode("utf-8")).hexdigest()

    async def collect() -> list[dict[str, Any]]:
        listing = await app.tools["list_agents"]()
        for entry in listing:
            assert entry["system_prompt"] == "Body text."
            assert entry["content_hash"] == expected_hash
        return listing

    import asyncio

    asyncio.run(collect())


# --- Wire shape: signature is None at list_agents, populated at get_agent --


async def test_list_agents_signing_fields_are_none() -> None:
    """Per B-6 + Phase 3 contract: list returns UNSIGNED metadata."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    listing = await app.tools["list_agents"]()
    for entry in listing:
        assert entry["signature"] is None
        assert entry["server_pubkey_id"] is None


async def test_get_agent_signing_fields_are_populated() -> None:
    """get_agent is the only call that returns a signed payload."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    result = await app.tools["get_agent"]("alpha-specialist")
    assert result["metadata"]["signature"] is not None
    assert result["metadata"]["server_pubkey_id"] == "test-key-id"


# --- Id field format --------------------------------------------------


async def test_id_format_is_server_name_version() -> None:
    """The canonical id is ``server_key:name:version`` (3 colon-separated parts)."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="akosha",
        catalog=[
            {
                "name": "alpha",
                "version": "2.1.3",
                "description": "x",
                "system_prompt": "alpha body",
            }
        ],
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    listing = await app.tools["list_agents"]()
    assert listing[0]["id"] == "akosha:alpha:2.1.3"


# --- Sanity: factory functions are coroutines --------------------------


def test_registered_tools_are_async_callables() -> None:
    """Both tools must be coroutine functions (FastMCP convention)."""
    app = MockApp()
    register = build_register_agents_tools(
        server_key="test",
        catalog=_inline_catalog(),
        body_loader=_disk_body_loader({}),
        sign=_test_sign(),
    )
    register(app)
    assert inspect.iscoroutinefunction(app.tools["list_agents"])
    assert inspect.iscoroutinefunction(app.tools["get_agent"])
