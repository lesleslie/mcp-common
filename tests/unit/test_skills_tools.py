"""Unit tests for the ``build_register_skills_tools`` factory.

Mirrors ``test_agents_tools.py`` for the parallel skills factory. The
schemas differ (``SkillCanonicalSchema`` has no inline ``system_prompt``;
the body is returned separately under ``"body"``) and the B-6 invariant
is enforced differently (the factory computes the content_hash from
the body bytes, not from an inlined field).
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from mcp_common.canonical_schemas.skill import SkillCanonicalSchema
from mcp_common.skills_tools import (
    _build_unsigned_metadata,
    _content_hash,
    _strip_body,
    build_register_skills_tools,
)


# --- Test fixtures ------------------------------------------------


class StubApp:
    """Minimal FastMCP app stub that captures tool registrations."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str):  # noqa: ANN001
        def deco(fn):  # noqa: ANN001
            self.tools[name] = fn
            return fn
        return deco


def _stub_signer() -> object:
    """Return a no-op signer with a stable key_id."""

    class _Signer:
        key_id = "0123456789abcdef"

        def sign(self, canonical: bytes) -> object:
            class _Result:
                signature_b64 = "deadbeef" * 8

            return _Result()

    return _Signer()


def _stub_sign(metadata: SkillCanonicalSchema) -> SkillCanonicalSchema:
    """sign() callback matching the agent factory contract."""
    return metadata.model_copy(
        update={
            "signature": "deadbeef" * 8,
            "server_pubkey_id": _stub_signer().key_id,
        }
    )


def _sample_catalog() -> list[dict[str, object]]:
    return [
        {
            "name": "run-quality-checks",
            "body_filename": "run-quality-checks.md",
            "version": "1.0.0",
            "description": "Run the full Crackerjack quality workflow",
            "tool_refs": ["mcp__crackerjack__crackerjack_run"],
            "allowed_tools": ["mcp__crackerjack__crackerjack_run", "Read"],
            "dependencies": [],
        },
        {
            "name": "smart-error-analysis",
            "body_filename": "smart-error-analysis.md",
            "version": "1.0.0",
            "description": "Surface common fix-failure patterns",
            "tool_refs": ["mcp__crackerjack__smart_error_analysis"],
            "allowed_tools": [
                "mcp__crackerjack__smart_error_analysis",
                "Read",
            ],
            "dependencies": ["run-quality-checks"],
        },
    ]


def _sample_bodies() -> dict[str, str]:
    return {
        "run-quality-checks": "---\nname: run-quality-checks\n---\n# Body 1",
        "smart-error-analysis": "---\nname: smart-error-analysis\n---\n# Body 2",
    }


# --- _strip_body / _content_hash (B-6 helpers) ---------------------


def test_strip_body_removes_leading_and_trailing_whitespace() -> None:
    body = "\n\n  ---\nname: x\n---\n# body\n  \n"
    assert _strip_body(body) == "---\nname: x\n---\n# body"


def test_content_hash_is_lowercase_hex_sha256() -> None:
    body = "hello"
    expected = hashlib.sha256(b"hello").hexdigest()
    assert _content_hash(body) == expected
    assert all(c in "0123456789abcdef" for c in _content_hash(body))


# --- Factory: build-time validation -------------------------------


def test_factory_rejects_server_key_violating_b4() -> None:
    with pytest.raises(ValueError, match="server_key.*B-4 allowlist"):
        build_register_skills_tools(
            server_key="../../etc/passwd",
            catalog=_sample_catalog(),
            body_loader=lambda n: "",
            sign=_stub_sign,
        )


def test_factory_rejects_catalog_entry_missing_name() -> None:
    with pytest.raises(ValueError, match="missing 'name' field"):
        build_register_skills_tools(
            server_key="crackerjack",
            catalog=[{"body_filename": "x.md"}],  # no name
            body_loader=lambda n: "",
            sign=_stub_sign,
        )


def test_factory_rejects_catalog_entry_name_violating_b4() -> None:
    with pytest.raises(ValueError, match="B-4 allowlist"):
        build_register_skills_tools(
            server_key="crackerjack",
            catalog=[{"name": "../../bad", "body_filename": "x.md"}],
            body_loader=lambda n: "",
            sign=_stub_sign,
        )


def test_factory_rejects_duplicate_catalog_names() -> None:
    catalog = [
        {"name": "x", "body_filename": "x.md"},
        {"name": "x", "body_filename": "x.md"},
    ]
    with pytest.raises(ValueError, match="duplicate catalog entry name"):
        build_register_skills_tools(
            server_key="crackerjack",
            catalog=catalog,
            body_loader=lambda n: "",
            sign=_stub_sign,
        )


def test_factory_rejects_catalog_entry_missing_body_filename() -> None:
    with pytest.raises(ValueError, match="missing required 'body_filename'"):
        build_register_skills_tools(
            server_key="crackerjack",
            catalog=[{"name": "x"}],  # no body_filename
            body_loader=lambda n: "",
            sign=_stub_sign,
        )


# --- Tool registration: tool name prefix --------------------------


def test_factory_default_tool_names_match_akosha_wire() -> None:
    app = StubApp()
    register = build_register_skills_tools(
        server_key="akosha",
        catalog=_sample_catalog(),
        body_loader=lambda n: "",
        sign=_stub_sign,
        # tool_name_prefix default "" => "list_skills", "get_skill"
    )
    register(app)
    assert "list_skills" in app.tools
    assert "get_skill" in app.tools


def test_factory_prefixed_tool_names_match_crackerjack_wire() -> None:
    app = StubApp()
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=lambda n: "",
        sign=_stub_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    assert "crackerjack_list_skills" in app.tools
    assert "crackerjack_get_skill" in app.tools


# --- list_skills wire shape ----------------------------------------


def test_list_skills_returns_unsigned_metadata_with_content_hash() -> None:
    app = StubApp()
    bodies = _sample_bodies()
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=bodies.__getitem__,
        sign=_stub_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    result = asyncio.run(app.tools["crackerjack_list_skills"]())  # type: ignore[arg-type]
    assert len(result) == 2
    for entry in result:
        assert "content_hash" in entry
        assert entry["content_hash"] == hashlib.sha256(
            bodies[entry["name"]].strip().encode("utf-8")
        ).hexdigest()
        # Per Phase 1 §11 B-6: signature fields are None in list
        # response (populated by get_skill).
        assert entry["signature"] is None
        assert entry["server_pubkey_id"] is None
        # Body is NOT inlined; clients call get_skill for it.
        assert "body" not in entry


# --- get_skill wire shape -----------------------------------------


def test_get_skill_returns_signed_metadata_plus_body() -> None:
    app = StubApp()
    bodies = _sample_bodies()
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=bodies.__getitem__,
        sign=_stub_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="run-quality-checks"))  # type: ignore[arg-type]
    assert r["success"] is True
    assert r["body"] == bodies["run-quality-checks"].strip()
    assert r["metadata"]["signature"] == "deadbeef" * 8
    assert r["metadata"]["server_pubkey_id"] == _stub_signer().key_id
    assert r["metadata"]["content_hash"] == hashlib.sha256(
        bodies["run-quality-checks"].strip().encode("utf-8")
    ).hexdigest()


# --- get_skill error envelopes -----------------------------------


def test_get_skill_rejects_path_traversal_with_b4_envelope() -> None:
    app = StubApp()
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=lambda n: "",
        sign=_stub_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="../../etc/passwd"))  # type: ignore[arg-type]
    assert r["success"] is False
    assert "allowlist" in r["error"]


def test_get_skill_rejects_dotdot_substring() -> None:
    app = StubApp()
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=lambda n: "",
        sign=_stub_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="foo..bar"))  # type: ignore[arg-type]
    assert r["success"] is False
    assert "allowlist" in r["error"]


def test_get_skill_returns_not_found_envelope() -> None:
    app = StubApp()
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=lambda n: "",
        sign=_stub_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="nope"))  # type: ignore[arg-type]
    assert r["success"] is False
    assert "not found" in r["error"]


def test_get_skill_returns_missing_body_envelope() -> None:
    app = StubApp()

    def missing(name: str) -> str:
        msg = f"Skill body for {name!r} missing"
        raise FileNotFoundError(msg)

    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=missing,
        sign=_stub_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="run-quality-checks"))  # type: ignore[arg-type]
    assert r["success"] is False
    assert "missing" in r["error"]


def test_get_skill_returns_signing_failed_envelope_when_signer_raises() -> None:
    app = StubApp()
    bodies = _sample_bodies()

    def broken_sign(meta: SkillCanonicalSchema) -> SkillCanonicalSchema:
        msg = "signer not initialized"
        raise RuntimeError(msg)

    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=bodies.__getitem__,
        sign=broken_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="run-quality-checks"))  # type: ignore[arg-type]
    assert r["success"] is False
    assert "signing failed" in r["error"]
    assert "signer not initialized" in r["error"]


def test_get_skill_rejects_wrong_sign_return_type() -> None:
    app = StubApp()
    bodies = _sample_bodies()

    def bad_return(meta: SkillCanonicalSchema) -> dict[str, object]:
        return {"wrong": "type"}

    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=bodies.__getitem__,
        sign=bad_return,  # type: ignore[arg-type]
        tool_name_prefix="crackerjack_",
    )
    register(app)
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="run-quality-checks"))  # type: ignore[arg-type]
    assert r["success"] is False
    assert "SkillCanonicalSchema" in r["error"]


# --- B-7 cycle bumps ---------------------------------------------


def test_on_call_is_invoked_on_every_call() -> None:
    app = StubApp()
    bodies = _sample_bodies()
    calls: list[int] = []

    def on_call() -> None:
        calls.append(1)

    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=bodies.__getitem__,
        sign=_stub_sign,
        on_call=on_call,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    asyncio.run(app.tools["crackerjack_list_skills"]())  # type: ignore[arg-type]
    asyncio.run(app.tools["crackerjack_get_skill"](name="run-quality-checks"))  # type: ignore[arg-type]
    asyncio.run(app.tools["crackerjack_get_skill"](name="nope"))  # type: ignore[arg-type]
    # 1 for list + 1 for each get_skill, even when the latter errors
    # (the B-7 contract is per-call, not per-success).
    assert len(calls) == 3


def test_on_call_none_omits_cycle_bump() -> None:
    """When on_call=None, the factory still works (no cycles bumped)."""
    app = StubApp()
    bodies = _sample_bodies()
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=_sample_catalog(),
        body_loader=bodies.__getitem__,
        sign=_stub_sign,
        on_call=None,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    # No exception means None was accepted.
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="run-quality-checks"))  # type: ignore[arg-type]
    assert r["success"] is True


# --- B-6 content_hash invariance ---------------------------------


def test_content_hash_matches_stripped_body() -> None:
    app = StubApp()
    bodies = {
        "run-quality-checks": "\n\n  ---\nname: x\n---\n# body\n  \n",
    }
    catalog = [
        {
            "name": "run-quality-checks",
            "body_filename": "run-quality-checks.md",
            "version": "1.0.0",
            "description": "test",
        },
    ]
    register = build_register_skills_tools(
        server_key="crackerjack",
        catalog=catalog,
        body_loader=bodies.__getitem__,
        sign=_stub_sign,
        tool_name_prefix="crackerjack_",
    )
    register(app)
    r = asyncio.run(app.tools["crackerjack_get_skill"](name="run-quality-checks"))  # type: ignore[arg-type]
    expected = hashlib.sha256(b"---\nname: x\n---\n# body").hexdigest()
    assert r["metadata"]["content_hash"] == expected


# --- Build-metadata helpers (white box) --------------------------


def test_build_unsigned_metadata_includes_all_known_fields() -> None:
    entry = {
        "name": "alpha",
        "body_filename": "alpha.md",
        "version": "2.0.0",
        "description": "alpha description",
        "tool_refs": ["a", "b"],
        "allowed_tools": ["c"],
        "dependencies": ["d"],
        "owner": "tester",
        "tags": ["t1", "t2"],
    }
    body = "alpha body"
    meta = _build_unsigned_metadata(entry, server_key="crackerjack", body=body)
    assert isinstance(meta, SkillCanonicalSchema)
    assert meta.name == "alpha"
    assert meta.version == "2.0.0"
    assert meta.server == "crackerjack"
    assert meta.id == "crackerjack:alpha:2.0.0"
    assert meta.description == "alpha description"
    assert meta.tool_refs == ["a", "b"]
    assert meta.allowed_tools == ["c"]
    assert meta.dependencies == ["d"]
    assert meta.owner == "tester"
    assert meta.tags == ["t1", "t2"]
    assert meta.content_type == "skill"
    assert meta.body_size == len(body.encode("utf-8"))
    assert meta.body_format == "yaml-frontmatter+markdown"
    assert meta.content_hash == hashlib.sha256(body.encode("utf-8")).hexdigest()
