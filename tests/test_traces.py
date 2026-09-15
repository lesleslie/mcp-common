"""Tests for mcp_common.traces.endpoint_resolver (Phase 5 / spec §5)."""
from __future__ import annotations

import os
from pathlib import Path

from mcp_common.traces import EndpointResolver


def test_resolve_default_path(tmp_path):
    resolver = EndpointResolver(base_dir=tmp_path)
    ep = resolver.resolve("mahavishnu")
    assert ep.component == "mahavishnu"
    assert ep.path == tmp_path / "mahavishnu" / "traces.duckdb"
    assert ep.exists is False


def test_resolve_env_override(tmp_path):
    override = tmp_path / "custom" / "traces.duckdb"
    override.parent.mkdir(parents=True)
    override.touch()
    os.environ["MAHAVISHNU_TRACES_PATH"] = str(override)
    try:
        resolver = EndpointResolver(base_dir=tmp_path)
        ep = resolver.resolve("mahavishnu")
        assert ep.path == override
        assert ep.exists is True
    finally:
        del os.environ["MAHAVISHNU_TRACES_PATH"]


def test_resolve_all_returns_five_components():
    resolver = EndpointResolver(base_dir=Path("/tmp"))
    eps = resolver.resolve_all()
    components = {ep.component for ep in eps}
    assert components == {"mahavishnu", "akosha", "crackerjack", "session_buddy", "dhara"}


def test_unknown_component_falls_through_to_base():
    resolver = EndpointResolver(base_dir=Path("/tmp/foo"))
    ep = resolver.resolve("unknown-component")
    assert ep.path == Path("/tmp/foo/unknown-component/traces.duckdb")
