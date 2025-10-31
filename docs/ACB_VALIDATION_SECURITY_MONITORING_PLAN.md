# ACB Validation, Security, and Monitoring Consolidation Plan

Status: Approved
Owner: ACB Core / MCP Common
Scope: ACB + mcp-common (no transitional wrappers)

## Goals

- Create first‑class, framework‑agnostic modules in ACB for validation, security, and monitoring.
- Remove overlapping code from mcp-common and update imports in internal projects.
- Keep actions pure, adapters provider‑specific, and services reserved for orchestration (not used now).

## Deliverables

- `acb.validation` (new): Pydantic/Settings integration (mixins + validator factories).
- `acb.config.Settings` (augment): Generic helpers (e.g., `get_data_dir`).
- `acb.monitoring` (new package): Health primitives + HTTP connectivity checks.
- `acb.security.sanitization` (new): Input/path sanitizers, masking, logging helpers.
- `acb.actions.validate` (trim): Pure validators only (no sanitizers, no wrappers).
- `mcp-common`: Remove overlapping health/http code; update docs and imports to ACB modules.

## Architecture Boundaries

- Actions: stateless/pure utilities (adapter‑agnostic).
- Adapters: provider implementations (e.g., `acb.adapters.monitoring.*`).
- Monitoring: primitives in `acb.monitoring` (not providers).
- Services: reserved for orchestration (not in scope now).

## Work Items and Progress

### 1) ACB – Validation

- [ ] Add `acb/validation.py`
  - [ ] Port `ValidationMixin` (from mcp-common, remove MCP‑specifics)
  - [ ] Add validator factories: `create_pattern_validator`, `create_length_validator`
  - [ ] Unit tests (models using `@field_validator`) and usage docs

### 2) ACB – Config

- [ ] Extend `acb/config.py`
  - [ ] Add `Settings.get_data_dir(field_name: str) -> Path`
  - [ ] Tests: type mismatch -> ValueError; creation/expansion works
  - [ ] Docs: example usage

### 3) ACB – Monitoring

- [ ] Add `acb/monitoring/health.py`

  - [ ] `HealthStatus` (ordered enum), `ComponentHealth`, `HealthCheckResponse`
  - [ ] Tests: aggregator, ordering, to_dict

- [ ] Add `acb/monitoring/http.py`

  - [ ] Adapter‑agnostic HTTP checks using `acb.adapters.requests`:
    - `check_http_connectivity(url, expected_status=200, timeout_ms=5000)`
    - `check_http_client_health(test_url: str | None = None, timeout_ms=5000)`
  - [ ] Exception aliasing (httpx/niquests/requests) without client types
  - [ ] Tests: dummy adapter via `import_adapter/depends` patch; success/latency/timeout paths

### 4) ACB – Security / Sanitization

- [x] Add `acb/security/sanitization.py`
  - [x] `sanitize_input`, `sanitize_path`, `mask_sensitive_data`
  - [x] `sanitize_output`, `sanitize_dict_for_logging`
  - [x] `sanitize_html`, `sanitize_sql`
  - [ ] Unit tests in ACB repo + docs page

### 5) ACB – Actions (Validate)

- [x] Trim `acb/actions/validate/__init__.py`
  - [x] Remove sanitizers completely (no wrappers)
  - [ ] Keep pure validators: email/url/phone/length/pattern/sql_injection/xss/path_traversal
  - [ ] Update actions README to reference `acb.security.sanitization`

### 6) mcp-common Cleanup

- [ ] Remove overlapping modules

  - [ ] Delete `mcp_common/health.py`
  - [x] Delete `mcp_common/http_health.py`

- [x] Update imports and tests to ACB modules

  - [ ] Health primitives → `acb.monitoring.health`
  - [ ] HTTP checks → `acb.monitoring.http`
  - [ ] Validation helpers (if used) → `acb.validation`
  - [ ] Sanitizers → `acb.security.sanitization`

- [ ] Docs & Examples

  - [ ] Update README/examples to use ACB modules
  - [ ] Remove deprecated references

## Internal Projects – Migration Checklist

- [ ] Validation

  - `from acb.validation import ValidationMixin, create_*_validator`

- [ ] Settings helper

  - Use `Settings.get_data_dir("field_name")`

- [ ] Sanitization

  - `from acb.security.sanitization import sanitize_input, sanitize_path, mask_sensitive_data, sanitize_html, sanitize_sql`

- [ ] Monitoring

  - `from acb.monitoring.health import HealthStatus, ComponentHealth, HealthCheckResponse`
  - `from acb.monitoring.http import check_http_connectivity, check_http_client_health`

## Notes / Constraints

- No transitional wrappers or re‑exports; update all call sites directly.
- Keep `acb.config` as a single module; only extend `Settings`.
- Monitoring scope: only HTTP primitives now. No `acb.services.monitoring` (defer).

## Acceptance Criteria

- ACB builds with new modules; docs and tests added.
- mcp-common builds with overlapping modules removed; imports updated.
- Internal servers updated and green (lint, type, tests, coverage).
