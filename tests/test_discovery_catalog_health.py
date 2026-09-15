"""Tests for mcp_common.discovery, mcp_common.catalog, mcp_common.health_tools.

All three modules currently expose stubs (Phase 4 wiring deferred). Tests
pin the stub contracts so consumers know what to expect before Phase 4
wires the real backends.
"""
from __future__ import annotations

from mcp_common import catalog, discovery, health_tools


def test_discovery_agents_returns_empty_list():
    assert discovery.discover_agents() == []
    assert discovery.discover_agents(source="crackerjack") == []


def test_discovery_skills_returns_empty_list():
    assert discovery.discover_skills() == []
    assert discovery.discover_skills(source="oneiric") == []


def test_catalog_returns_empty_list():
    assert catalog.catalog("any query") == []
    assert catalog.catalog("any query", component="akosha", limit=5) == []


def test_catalog_list_capabilities_returns_empty_list():
    assert catalog.list_capabilities() == []


def test_health_register_feed_stub_returns_none():
    assert health_tools.register_feed(server=None, feed_name="test_feed") is None


def test_health_aggregate_health_returns_unknown():
    out = health_tools.aggregate_health(server=None)
    assert out["status"] == "UNKNOWN"
    assert out["feeds"] == {}
