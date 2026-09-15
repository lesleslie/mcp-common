"""Tests for mcp_common.canonical_schemas (Phase 4 / spec §4.11)."""
from __future__ import annotations

from mcp_common.canonical_schemas import AgentCanonicalSchema, SkillCanonicalSchema


def test_agent_canonical_schema_round_trip():
    schema = AgentCanonicalSchema(
        name="mahavishnu-orchestrator",
        version="1.0.0",
        description="Routes tasks to pools",
        capabilities=["routing", "workflow"],
        owner="mahavishnu",
        metadata={"tier": "core"},
    )
    out = schema.to_dict()
    assert out["name"] == "mahavishnu-orchestrator"
    assert out["version"] == "1.0.0"
    assert "routing" in out["capabilities"]
    assert out["metadata"]["tier"] == "core"


def test_skill_canonical_schema_round_trip():
    schema = SkillCanonicalSchema(
        name="crackerjack-fast-hooks",
        version="0.5.0",
        description="Run fast hooks",
        tags=["fast", "hooks"],
        owner="crackerjack",
        signature="not-a-real-sig",
    )
    out = schema.to_dict()
    assert out["name"] == "crackerjack-fast-hooks"
    assert out["signature"] == "not-a-real-sig"
    assert "fast" in out["tags"]
