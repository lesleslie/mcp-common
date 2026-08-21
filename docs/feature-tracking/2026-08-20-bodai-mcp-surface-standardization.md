---
feature: bodai-mcp-surface-standardization
plan: docs/plans/2026-08-20-bodai-mcp-surface-standardization.md
date: 2026-08-20
built: true
wired: true
adopted: pending
---

# Bodai MCP Surface Standardization

## Context

Every Bodai core MCP server exposes the same baseline tool surface so
clients performing tool discovery across the ecosystem see a uniform
shape. The 4-tool baseline is::

    - discover_tools
    - get_liveness
    - get_readiness
    - health_check_all

Session-Buddy shipped a different surface (one-off `ping`, `server_info`
banner) so cross-server tooling (bodai-radar, ecosystem-awareness,
Claude Code cross-server introspection) sees drift. The plan
standardizes the baseline, preserves `ping` as a deprecated alias for
one release, and pins the baseline with a regression test in
mcp-common.

## Status

- `built: true` - Phase 1 shipped `register_baseline_tools` and the 4
  canonical baseline tools in `mcp_common/baseline_tools.py`
  (commit `2688dc2`, branch `feat/bodai-mcp-baseline-tools`).
- `wired: true` - Phase 2 wired them into Session-Buddy
  (commit `aa49bc74`, branch `feat/bodai-mcp-baseline`):
  Session-Buddy exposes `discover_tools`, `get_liveness`,
  `get_readiness`, `health_check_all` plus the `ping` deprecated
  alias.
- `adopted: pending` - Phase 3 added the cross-server regression
  test (`mcp_common.testing.assert_baseline_surface`) plus the
  per-repo gate in Session-Buddy. Adoption flips to `true` once
  CI is green across all 5 Bodai core consumers.

## Rollout Plan

1. Phase 1 - Establish baseline helpers in mcp-common (DONE).
2. Phase 2 - Migrate Session-Buddy to baseline + ping alias (DONE).
3. Phase 3 - Cross-server regression test in mcp-common plus
   per-repo gate in Session-Buddy (this commit).
4. Follow-up - Migrate remaining Bodai core consumers (Akosha,
   Dhara, Crackerjack) to use `mcp_common.register_baseline_tools`
   instead of hand-rolled equivalents; remove the `ping` deprecated
   alias after one release.

## Verification

- `pytest mcp-common/tests/test_baseline_surface.py -v` - 5 cases
  parametrized over the Bodai core servers; collects when servers
  are reachable, fails when any server drops a baseline tool.
- `pytest session-buddy/tests/test_mcp_baseline.py -v` - per-repo
  gate runs in Session-Buddy's own CI.
- `git grep -rn assert_baseline_surface -- 'mcp-common/' 'session_buddy/'`
  returns the helper definition + the two test files.

## Reference

- Plan: `docs/plans/2026-08-20-bodai-mcp-surface-standardization.md`
- Phase 1 commit: `mcp-common@2688dc2` on `feat/bodai-mcp-baseline-tools`
- Phase 2 commit: `session-buddy@aa49bc74` on `feat/bodai-mcp-baseline`
