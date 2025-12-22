## Oneiric MCP CLI Factory Plan

Purpose: define the shared CLI lifecycle commands, health/status semantics, and
runtime cache conventions for MCP servers migrating to Oneiric.

### Standard CLI Flags

- Short lifecycle flags: `--start`, `--stop`, `--restart`, `--status`
- Long aliases: `--start-mcp-server`, `--stop-mcp-server`, `--restart-mcp-server`,
  `--server-status`
- Health inspection: `--health` with optional `--probe` modifier

### Status vs Health vs Probe

- `--status`: lightweight process status. Reads PID file and checks runtime
  snapshot freshness (updated_at within TTL).
- `--health`: lifecycle health summary from Oneiric runtime snapshot.
- `--health --probe`: executes live health probes using Oneiric lifecycle
  health checks, then reports updated snapshot results.

### Runtime Cache Conventions

- Cache root: `.oneiric_cache/` within each project workspace.
- PID file: `.oneiric_cache/mcp_server.pid` (default).
- Runtime health snapshot: `.oneiric_cache/runtime_health.json`
- Runtime telemetry snapshot: `.oneiric_cache/runtime_telemetry.json`

Rationale: project-local caches avoid global state collisions and keep per-repo
health/telemetry artifacts alongside the server code.

### Snapshot Expectations (Oneiric)

The CLI reads Oneiric runtime snapshots for health/status details:

- `oneiric.runtime.health.RuntimeHealthSnapshot` fields (PID, watchers, remote,
  lifecycle_state, activity_state, last sync/error details).
- `oneiric.runtime.telemetry.RuntimeObservabilitySnapshot` for last event/workflow
  telemetry (used by dashboards and ops tooling).

### Implementation Steps

1. Remove ACB dependencies and references from `mcp-common`.
1. Add Oneiric-native settings wrapper and cache path helpers.
1. Implement the CLI factory with standard flags and snapshot-based status/health.
1. Update docs and examples to reflect Oneiric-only usage.
1. Roll out the CLI factory to MCP servers (session-buddy first, then
   raindropio-mcp and mailgun-mcp, then the remaining active projects).

### Notes

- The CLI factory should accept optional overrides for PID path, cache root,
  and health TTL.
- Server implementations should write a runtime health snapshot at startup
  and update it on shutdown; optional periodic updates are recommended.
