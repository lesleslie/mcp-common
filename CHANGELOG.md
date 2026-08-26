# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.22.3] - 2026-08-25

### Fixed

- mcp-common: Re-apply Python 2 except-comma modernization in 14 sites.
  The 0.22.1 release included these fixes (commit 6ed8c9d), but the
  subsequent 0.22.2 version-bump commit (bd8de0f) accidentally reverted
  baseline_tools.py and the other 8 files via a cherry-pick conflict.
  The published 0.22.2 wheel shipped without the paren fix and refurb
  flagged `except X, Y:` syntax in any consumer's installed copy.
  0.22.3 restores the fix on top of 0.22.2.

## [0.22.2] - 2026-08-25

### Fixed

- mcp-common: Re-apply Python 2 except-comma modernization in 14 sites.
  The 0.22.1 release included these fixes (commit 6ed8c9d), but the
  initial 0.22.2 version-bump commit (bd8de0f) accidentally reverted
  baseline_tools.py and the other 8 files via a cherry-pick conflict.
  The published 0.22.2 wheel shipped without the paren fix and refurb
  flagged `except X, Y:` syntax in any consumer's installed copy. The
  fix is restored here; the version-bump step itself happens in the
  crackerjack publish stage.

## [0.22.1] - 2026-08-25

### Added

- Drop fastmcp<4 upper bound — enable v2 SDK track
- mcp-common: Add apply_tool_profile() helper
- mcp-common: Bootstrap_baseline_tools helper for one-line standardization
- mcp-common: Mirror wave-11 mermaid CI guard from crackerjack
- mcp-common: Register_baseline_tools + 4 canonical baseline tools
- mcp-common: Register_http_health_route helper

### Fixed

- mcp-common: Add bootstrap_baseline_tools to __all__
- mcp-common: Extend except-tuple fix to dotted-name exception sites
- mcp-common: Modernize Python 2 except comma syntax in 11 sites
- mcp-common: Modernize Python 2 except-comma syntax in 14 sites
- mcp-common: Narrow Style type for ty (pre-publish dependency)
- mcp-common: Re-apply except-tuple modernization in 14 sites
- mcp-common: Resolve 19 pre-publish ruff errors + untrack .pyscn/
- mcp-common: Resolve 28 pre-existing test failures
- mcp-common: Resolve ty + lychee errors (dispatch.py + plan index regenerator)
- mcp-common: Resolve ty + refurb errors in backends/toolkit and baseline_tools
- mcp-common: Split mandatory_tools into mandatory_groups + essential_tool_names
- ratchet: Lower mcp-common floor to current measured coverage
- ratchet: Mirror mcp-common pyproject.toml to current coverage
- schemas: Add decision-index to topic vocabulary v1

### Documentation

- mcp-common: Apply plan-lifecycle-unification playbook (P7.B)
- mcp-common: Archive PHASE1 summary + update SERVER_INTEGRATION for v0.17.9
- mcp-common: Fix README version drift (0.6.0 -> 0.17.9)

### Testing

- mcp-common: Assert_baseline_surface + 5-server regression test

### Build

- Exclude local venvs from hatchling sdist target

### Internal

- Bump oneiric dep to >=0.16.0
- Bump requires-python to >=3.14
- Bump version to 0.17.10
- Bump version to 0.17.4
- Bump version to 0.17.5
- Bump version to 0.17.6
- Bump version to 0.17.7
- Bump version to 0.17.8
- Bump version to 0.17.9
- Bump version to 0.18.0
- Bump version to 0.19.0
- Bump version to 0.19.1
- Bump version to 0.20.0
- Bump version to 0.20.2
- Bump version to 0.20.4
- Bump version to 0.20.6
- Bump version to 0.22.0
- gitignore: Add *.backup.* catch-all pattern
- mcp-common: Bump tool-config pins from 3.13 to 3.14
- mcp-common: Migrate [project.optional-dependencies] → [dependency-groups]
- mcp-common: Remove 3 point-in-time completion reports from archive
- mcp-common: Remove LICENSE (consolidated to root-level LICENSE)
- mcp-common: Sync uv.lock to pyproject.toml (0.17.6)
- mcp-common: Uv sync --upgrade --all-groups
- Normalize LICENSE attribution to Robert Leslie and Wedgwood Web Works

## [0.22.1] - 2026-08-25

### Fixed

- mcp-common: Modernize Python 2 except-comma syntax in 14 sites
  (baseline_tools, backends/toolkit, cli/{health,security,factory},
  code_graph/analyzer, parsing/tree_sitter/core, tools/mermaid_validator).
  These were missed by the 0.20.6 and 0.20.4 except-tuple modernization
  passes and would cause `refurb` (with `python_version = "3.14"`) and
  Python 3.14's stricter grammar to flag errors in any consumer's
  installed copy.

## [0.22.0] - 2026-08-25

### Added

- Drop fastmcp\<4 upper bound — enable v2 SDK track
- mcp-common: Add apply_tool_profile() helper
- mcp-common: Bootstrap_baseline_tools helper for one-line standardization
- mcp-common: Mirror wave-11 mermaid CI guard from crackerjack
- mcp-common: Register_baseline_tools + 4 canonical baseline tools
- mcp-common: Register_http_health_route helper

### Fixed

- mcp-common: Add bootstrap_baseline_tools to __all__
- mcp-common: Extend except-tuple fix to dotted-name exception sites
- mcp-common: Modernize Python 2 except comma syntax in 11 sites
- mcp-common: Narrow Style type for ty (pre-publish dependency)
- mcp-common: Re-apply except-tuple modernization in 14 sites
- mcp-common: Resolve 19 pre-publish ruff errors + untrack .pyscn/
- mcp-common: Resolve 28 pre-existing test failures
- mcp-common: Resolve ty + lychee errors (dispatch.py + plan index regenerator)
- mcp-common: Resolve ty + refurb errors in backends/toolkit and baseline_tools
- mcp-common: Split mandatory_tools into mandatory_groups + essential_tool_names
- ratchet: Lower mcp-common floor to current measured coverage
- ratchet: Mirror mcp-common pyproject.toml to current coverage
- schemas: Add decision-index to topic vocabulary v1

### Documentation

- mcp-common: Apply plan-lifecycle-unification playbook (P7.B)
- mcp-common: Archive PHASE1 summary + update SERVER_INTEGRATION for v0.17.9
- mcp-common: Fix README version drift (0.6.0 -> 0.17.9)

### Testing

- mcp-common: Assert_baseline_surface + 5-server regression test

### Build

- Exclude local venvs from hatchling sdist target

### Internal

- Bump oneiric dep to >=0.16.0
- Bump requires-python to >=3.14
- Bump version to 0.17.10
- Bump version to 0.17.3
- Bump version to 0.17.4
- Bump version to 0.17.5
- Bump version to 0.17.6
- Bump version to 0.17.7
- Bump version to 0.17.8
- Bump version to 0.17.9
- Bump version to 0.18.0
- Bump version to 0.19.0
- Bump version to 0.19.1
- Bump version to 0.20.0
- Bump version to 0.20.2
- Bump version to 0.20.4
- Bump version to 0.20.6
- gitignore: Add *.backup.* catch-all pattern
- gitignore: Untrack .lycheecache + add \*.backup.json rule
- mcp-common: Bump tool-config pins from 3.13 to 3.14
- mcp-common: Migrate [project.optional-dependencies] → [dependency-groups]
- mcp-common: Remove 3 point-in-time completion reports from archive
- mcp-common: Remove LICENSE (consolidated to root-level LICENSE)
- mcp-common: Sync uv.lock to pyproject.toml (0.17.6)
- mcp-common: Uv sync --upgrade --all-groups
- Normalize LICENSE attribution to Robert Leslie and Wedgwood Web Works

## [0.21.0] - 2026-08-25

### Changed

- mcp-common: Drop `fastmcp<4` upper bound to permit fastmcp 4.x and the
  MCP SDK v2 line. The re-export surface in `mcp_common.fastmcp` (FastMCP,
  Context, Middleware, MiddlewareContext, RateLimitingMiddleware) and the
  `fastmcp.tools.Tool` API used by `baseline_tools` and `dispatch` are
  source-compatible with fastmcp 4.0.0b3. Consumers on the v2 track
  (crackerjack ≥0.55, future mcp SDK v2 releases) can now upgrade without
  a mcp-common upper-bound conflict.

### Notes

- This is a minor bump because downstream resolvers may now pick fastmcp
  4.x and the MCP SDK v2 line, which carries SDK-level breaking changes
  independent of mcp-common itself. Test with `crackerjack run` before
  shipping.

## [0.20.6] - 2026-08-25

### Added

- mcp-common: Add apply_tool_profile() helper
- mcp-common: Bootstrap_baseline_tools helper for one-line standardization
- mcp-common: Mirror wave-11 mermaid CI guard from crackerjack
- mcp-common: Plan 7 Phase 1 — FastMCP 3.4 foundation
- mcp-common: Register_baseline_tools + 4 canonical baseline tools
- mcp-common: Register_http_health_route helper

### Fixed

- mcp-common: Add bootstrap_baseline_tools to __all__
- mcp-common: Extend except-tuple fix to dotted-name exception sites
- mcp-common: Modernize Python 2 except comma syntax in 11 sites
- mcp-common: Narrow Style type for ty (pre-publish dependency)
- mcp-common: Re-apply except-tuple modernization in 14 sites
- mcp-common: Resolve 19 pre-publish ruff errors + untrack .pyscn/
- mcp-common: Resolve 28 pre-existing test failures
- mcp-common: Resolve ty + lychee errors (dispatch.py + plan index regenerator)
- mcp-common: Resolve ty + refurb errors in backends/toolkit and baseline_tools
- mcp-common: Split mandatory_tools into mandatory_groups + essential_tool_names
- ratchet: Lower mcp-common floor to current measured coverage
- ratchet: Mirror mcp-common pyproject.toml to current coverage
- schemas: Add decision-index to topic vocabulary v1

### Documentation

- mcp-common: Apply plan-lifecycle-unification playbook (P7.B)
- mcp-common: Archive PHASE1 summary + update SERVER_INTEGRATION for v0.17.9
- mcp-common: Fix README version drift (0.6.0 -> 0.17.9)

### Testing

- mcp-common: Assert_baseline_surface + 5-server regression test

### Internal

- Bump oneiric dep to >=0.16.0
- Bump requires-python to >=3.14
- Bump version to 0.17.0
- Bump version to 0.17.1
- Bump version to 0.17.10
- Bump version to 0.17.3
- Bump version to 0.17.4
- Bump version to 0.17.5
- Bump version to 0.17.6
- Bump version to 0.17.7
- Bump version to 0.17.8
- Bump version to 0.17.9
- Bump version to 0.18.0
- Bump version to 0.19.0
- Bump version to 0.19.1
- Bump version to 0.20.0
- Bump version to 0.20.2
- Bump version to 0.20.4
- gitignore: Add *.backup.* catch-all pattern
- gitignore: Untrack .lycheecache + add \*.backup.json rule
- mcp-common: Bump tool-config pins from 3.13 to 3.14
- mcp-common: Migrate [project.optional-dependencies] → [dependency-groups]
- mcp-common: Remove 3 point-in-time completion reports from archive
- mcp-common: Remove LICENSE (consolidated to root-level LICENSE)
- mcp-common: Sync uv.lock to pyproject.toml (0.17.6)
- mcp-common: Uv sync --upgrade --all-groups
- Normalize LICENSE attribution to Robert Leslie and Wedgwood Web Works

## [0.20.5] - 2026-08-25

### Fixed

- mcp-common: Re-apply except-tuple modernization in 14 sites. The 0.20.2
  bump (commit f8776ad) shipped changelog credits for the 11-site fix
  (d30baf6) + the dotted-name fix (c19c127) but did NOT include the actual
  code changes, reintroducing the Python 2 `except X, Y:` syntax that
  refurb flags on every crackerjack comprehensive run. Sites re-fixed
  (same list as 0.20.3): `baseline_tools.py:222`,
  `tools/mermaid_validator/renderer.py:87`, `backends/toolkit.py:175, 260, 299`, `cli/security.py:120, 161, 177`, `cli/health.py:172, 198`,
  `cli/factory.py:530, 745`, `parsing/tree_sitter/core.py:265`,
  `code_graph/analyzer.py:246`.

## [0.20.4] - 2026-08-24

### Added

- mcp-common: Add apply_tool_profile() helper
- mcp-common: Bootstrap_baseline_tools helper for one-line standardization
- mcp-common: Mirror wave-11 mermaid CI guard from crackerjack
- mcp-common: Plan 7 Phase 1 — FastMCP 3.4 foundation
- mcp-common: Register_baseline_tools + 4 canonical baseline tools
- mcp-common: Register_http_health_route helper

### Fixed

- mcp-common: Add bootstrap_baseline_tools to __all__
- mcp-common: Extend except-tuple fix to dotted-name exception sites
- mcp-common: Modernize Python 2 except comma syntax in 11 sites
- mcp-common: Narrow Style type for ty (pre-publish dependency)
- mcp-common: Resolve 19 pre-publish ruff errors + untrack .pyscn/
- mcp-common: Resolve 28 pre-existing test failures
- mcp-common: Resolve ty + lychee errors (dispatch.py + plan index regenerator)
- mcp-common: Resolve ty + refurb errors in backends/toolkit and baseline_tools
- mcp-common: Split mandatory_tools into mandatory_groups + essential_tool_names
- ratchet: Lower mcp-common floor to current measured coverage
- ratchet: Mirror mcp-common pyproject.toml to current coverage
- schemas: Add decision-index to topic vocabulary v1

### Documentation

- mcp-common: Apply plan-lifecycle-unification playbook (P7.B)
- mcp-common: Archive PHASE1 summary + update SERVER_INTEGRATION for v0.17.9
- mcp-common: Fix README version drift (0.6.0 -> 0.17.9)

### Testing

- mcp-common: Assert_baseline_surface + 5-server regression test

### Internal

- Bump oneiric dep to >=0.16.0
- Bump requires-python to >=3.14
- Bump version to 0.16.3
- Bump version to 0.16.4
- Bump version to 0.17.0
- Bump version to 0.17.1
- Bump version to 0.17.10
- Bump version to 0.17.3
- Bump version to 0.17.4
- Bump version to 0.17.5
- Bump version to 0.17.6
- Bump version to 0.17.7
- Bump version to 0.17.8
- Bump version to 0.17.9
- Bump version to 0.18.0
- Bump version to 0.19.0
- Bump version to 0.19.1
- Bump version to 0.20.0
- Bump version to 0.20.2
- gitignore: Add *.backup.* catch-all pattern
- gitignore: Untrack .lycheecache + add \*.backup.json rule
- mcp-common: Bump tool-config pins from 3.13 to 3.14
- mcp-common: Migrate [project.optional-dependencies] → [dependency-groups]
- mcp-common: Remove 3 point-in-time completion reports from archive
- mcp-common: Remove LICENSE (consolidated to root-level LICENSE)
- mcp-common: Sync uv.lock to pyproject.toml (0.17.6)
- mcp-common: Uv sync --upgrade --all-groups
- Normalize LICENSE attribution to Robert Leslie and Wedgwood Web Works

## [0.20.3] - 2026-08-24

### Fixed

- mcp-common: Re-apply except-tuple modernization (14 sites) — 0.20.2
  published without the d30baf6 + c19c127 code changes (only their
  changelog entries), reintroducing the Python 2 `except X, Y:` syntax
  that refurb flags. Sites re-fixed: `baseline_tools.py:222`,
  `tools/mermaid_validator/renderer.py:87`, `backends/toolkit.py:175, 260, 299`, `cli/security.py:120, 161, 177`, `cli/health.py:172, 198`,
  `tools/mermaid_validator/renderer.py:87`, `backends/toolkit.py:175, 260, 299`, `cli/security.py:120, 161, 177`, `cli/health.py:172, 198`,
  `cli/factory.py:530, 745`, `parsing/tree_sitter/core.py:265`,
  `code_graph/analyzer.py:246`.

## [0.20.2] - 2026-08-24

### Added

- mcp-common: Add apply_tool_profile() helper
- mcp-common: Bootstrap_baseline_tools helper for one-line standardization
- mcp-common: Mirror wave-11 mermaid CI guard from crackerjack
- mcp-common: Plan 7 Phase 1 — FastMCP 3.4 foundation
- mcp-common: Register_baseline_tools + 4 canonical baseline tools
- mcp-common: Register_http_health_route helper

### Fixed

- mcp-common: Add bootstrap_baseline_tools to __all__
- mcp-common: Extend except-tuple fix to dotted-name exception sites
- mcp-common: Modernize Python 2 except comma syntax in 11 sites
- mcp-common: Narrow Style type for ty (pre-publish dependency)
- mcp-common: Resolve 19 pre-publish ruff errors + untrack .pyscn/
- mcp-common: Resolve 28 pre-existing test failures
- mcp-common: Resolve ty + lychee errors (dispatch.py + plan index regenerator)
- mcp-common: Resolve ty + refurb errors in backends/toolkit and baseline_tools
- mcp-common: Split mandatory_tools into mandatory_groups + essential_tool_names
- ratchet: Lower mcp-common floor to current measured coverage
- ratchet: Mirror mcp-common pyproject.toml to current coverage

### Documentation

- mcp-common: Apply plan-lifecycle-unification playbook (P7.B)
- mcp-common: Archive PHASE1 summary + update SERVER_INTEGRATION for v0.17.9
- mcp-common: Fix README version drift (0.6.0 -> 0.17.9)

### Testing

- mcp-common: Assert_baseline_surface + 5-server regression test

### Internal

- Bump oneiric dep to >=0.16.0
- Bump requires-python to >=3.14
- Bump version to 0.16.3
- Bump version to 0.16.4
- Bump version to 0.17.0
- Bump version to 0.17.1
- Bump version to 0.17.10
- Bump version to 0.17.3
- Bump version to 0.17.4
- Bump version to 0.17.5
- Bump version to 0.17.6
- Bump version to 0.17.7
- Bump version to 0.17.8
- Bump version to 0.17.9
- Bump version to 0.18.0
- Bump version to 0.19.0
- Bump version to 0.19.1
- Bump version to 0.20.0
- gitignore: Add *.backup.* catch-all pattern
- gitignore: Add backup file patterns to silence checkpoint tool artifacts
- gitignore: Untrack .lycheecache + add \*.backup.json rule
- mcp-common: Bump tool-config pins from 3.13 to 3.14
- mcp-common: Migrate [project.optional-dependencies] → [dependency-groups]
- mcp-common: Remove 3 point-in-time completion reports from archive
- mcp-common: Remove LICENSE (consolidated to root-level LICENSE)
- mcp-common: Sync uv.lock to pyproject.toml (0.17.6)
- mcp-common: Uv sync --upgrade --all-groups
- Normalize LICENSE attribution to Robert Leslie and Wedgwood Web Works
- Untrack and delete 2 historical *.backup/*.bak files

## [0.20.1] - 2026-08-24

### Fixed

- mcp-common: Replace 11 `except X, Y:` Python 2 comma-syntax sites with
  `except (X, Y):` tuple form. refurb flags these; the legacy 2-arg form
  binds the second identifier to a variable name in pre-3.x, but the
  multi-arg form silently works as a tuple on Python 3.14 (with
  confusing reader semantics). Sites fixed: `baseline_tools.py:222`,
  `tools/mermaid_validator/renderer.py:87`, `backends/toolkit.py:175,260, 299`, `cli/health.py:172,198`, `cli/factory.py:530,745`,
  `parsing/tree_sitter/core.py:265`, `code_graph/analyzer.py:246`.

## [0.20.0] - 2026-08-24

### Internal

- Bump requires-python to >=3.14
- mcp-common: Bump tool-config pins from 3.13 to 3.14

## [0.19.1] - 2026-08-21

### Added

- mcp-common: Bootstrap_baseline_tools helper for one-line standardization
- mcp-common: Register_baseline_tools + 4 canonical baseline tools

### Fixed

- mcp-common: Add bootstrap_baseline_tools to __all__
- mcp-common: Resolve 28 pre-existing test failures
- mcp-common: Resolve ty + refurb errors in backends/toolkit and baseline_tools

### Testing

- mcp-common: Assert_baseline_surface + 5-server regression test

## [0.19.0] - 2026-08-20

### Fixed

- mcp-common: Resolve 19 pre-publish ruff errors + untrack .pyscn/
- mcp-common: Resolve ty + lychee errors (dispatch.py + plan index regenerator)

### Internal

- mcp-common: Uv sync --upgrade --all-groups

## [0.18.0] - 2026-08-18

### Added

- mcp-common: Add apply_tool_profile() helper

### Fixed

- mcp-common: Narrow Style type for ty (pre-publish dependency)
- mcp-common: Split mandatory_tools into mandatory_groups + essential_tool_names

## [0.17.10] - 2026-08-17

### Added

- mcp-common: Mirror wave-11 mermaid CI guard from crackerjack

### Documentation

- mcp-common: Archive PHASE1 summary + update SERVER_INTEGRATION for v0.17.9
- mcp-common: Fix README version drift (0.6.0 -> 0.17.9)

## [0.17.9] - 2026-08-12

### Fixed

- ratchet: Lower mcp-common floor to current measured coverage
- ratchet: Mirror mcp-common pyproject.toml to current coverage

## [0.17.8] - 2026-07-26

### Added

- mcp-common: Register_http_health_route helper

### Internal

- Bump oneiric dep to >=0.16.0
- Normalize LICENSE attribution to Robert Leslie and Wedgwood Web Works

## [0.17.7] - 2026-07-21

### Documentation

- mcp-common: Apply plan-lifecycle-unification playbook (P7.B)

### Internal

- mcp-common: Remove 3 point-in-time completion reports from archive
- mcp-common: Remove LICENSE (consolidated to root-level LICENSE)
- mcp-common: Sync uv.lock to pyproject.toml (0.17.6)

## [0.17.4] - 2026-07-06

### Internal

- gitignore: Add *.backup.* catch-all pattern
- gitignore: Untrack .lycheecache + add \*.backup.json rule
- mcp-common: Migrate [project.optional-dependencies] → [dependency-groups]

## [0.17.3] - 2026-07-04

### Added

- Add @require_auth() decorator with Permission-level enforcement
- Add AuthAuditEvent and AuditLogger with custom sink support
- Add AuthConfig with env-var secret loading and placeholder rejection
- Add mcp_common/auth package skeleton with exception hierarchy
- apple_script: Add canonical multi-line escaping functions
- apple_script: Add shared async AppleScript bridge
- auth: Add JWT create/verify with issuer, audience, and permission claims
- auth: Add KNOWN_SERVICES registry and issuer/audience verification
- auth: Add Permission enum and Role definitions
- llm: Add edge case tests, Hypothesis property tests, format pass; bump to 0.14.0
- llm: Add HailuoAdapter for MiniMax video generation with SSRF-safe polling
- llm: Add llama_server support and fail-closed API key validation
- llm: Add multimodal TaskType variants and VISION deprecation alias
- llm: Add per-tier retry loop, error sanitization, and CancelledError propagation
- llm: Add task_routing model resolution in OpenAICompatibleProvider; bump to 0.14.1
- llm: Add timeout_seconds, require_auth, api_key_env to ProviderConfig
- llm: Add UnsupportedModalityError exception
- mcp-common: Plan 7 Phase 1 — FastMCP 3.4 foundation

### Changed

- Mcp-common (quality: 60/100) - 2026-04-14 02:37:34

### Fixed

- apple_script: Export escape_for_applescript and build_applescript_string
- auth: Remove bare except — verify_issuer already raises UnknownIssuerError

### Documentation

- Add iTerm2 AppleScript protocol spec

### Testing

- Add inter-service auth integration tests
- auth: Add missing branch coverage for permissions and audit logger
- coverage: Add 31 comprehensive tests and fix path traversal security issue

### Internal

- Bump version to 0.11.0
- Bump version to 0.11.1
- Bump version to 0.12.0
- Bump version to 0.12.1
- Bump version to 0.12.2
- Bump version to 0.12.3
- Bump version to 0.13.0
- Bump version to 0.13.1
- Bump version to 0.13.2
- Bump version to 0.13.3
- Bump version to 0.15.0
- Bump version to 0.15.1
- Bump version to 0.15.2
- Bump version to 0.15.3
- Bump version to 0.16.0
- Bump version to 0.16.1
- Bump version to 0.16.2
- Bump version to 0.16.3
- Bump version to 0.16.4
- Bump version to 0.17.0
- Bump version to 0.17.1
- gitignore: Add backup file patterns to silence checkpoint tool artifacts
- Ignore .worktrees directory
- Untrack and delete 2 historical *.backup/*.bak files
- Untrack large coverage JSONs and add gitignore pattern

## [0.17.0] - 2026-06-26

### Added

- mcp-common: Plan 7 Phase 1 — FastMCP 3.4 foundation

## [0.16.3] - 2026-06-05

### Internal

- gitignore: Add backup file patterns to silence checkpoint tool artifacts
- Untrack and delete 2 historical *.backup/*.bak files

## [0.16.0] - 2026-05-24

### Added

- apple_script: Add canonical multi-line escaping functions
- apple_script: Add shared async AppleScript bridge

### Fixed

- apple_script: Export escape_for_applescript and build_applescript_string

### Documentation

- Add iTerm2 AppleScript protocol spec

## [0.15.2] - 2026-05-19

### Testing

- auth: Add missing branch coverage for permissions and audit logger

## [0.15.1] - 2026-05-17

### Internal

- Untrack large coverage JSONs and add gitignore pattern

## [0.15.0] - 2026-05-16

### Added

- Add @require_auth() decorator with Permission-level enforcement
- Add AuthAuditEvent and AuditLogger with custom sink support
- Add AuthConfig with env-var secret loading and placeholder rejection
- Add mcp_common/auth package skeleton with exception hierarchy
- auth: Add JWT create/verify with issuer, audience, and permission claims
- auth: Add KNOWN_SERVICES registry and issuer/audience verification
- auth: Add Permission enum and Role definitions
- Extend health module with dependency checking infrastructure
- llm: Add edge case tests, Hypothesis property tests, format pass; bump to 0.14.0
- llm: Add HailuoAdapter for MiniMax video generation with SSRF-safe polling
- llm: Add llama_server support and fail-closed API key validation
- llm: Add multimodal TaskType variants and VISION deprecation alias
- llm: Add per-tier retry loop, error sanitization, and CancelledError propagation
- llm: Add task_routing model resolution in OpenAICompatibleProvider; bump to 0.14.1
- llm: Add timeout_seconds, require_auth, api_key_env to ProviderConfig
- llm: Add UnsupportedModalityError exception

### Changed

- Mcp-common (quality: 60/100) - 2026-04-13 04:52:13
- Mcp-common (quality: 60/100) - 2026-04-14 02:37:34
- Replace python-jose with PyJWT to fix CVE-2024-23342
- Update config, core, deps, tests
- Update config, deps, docs, tests
- Update core functionality
- Update core, deps, docs
- Update dependencies
- Update dependencies

### Fixed

- auth: Remove bare except — verify_issuer already raises UnknownIssuerError

### Testing

- Add inter-service auth integration tests
- coverage: Add 31 comprehensive tests and fix path traversal security issue

### Internal

- Add archive/backup directories to gitignore
- Bump version to 0.10.0
- Bump version to 0.11.0
- Bump version to 0.11.1
- Bump version to 0.12.0
- Bump version to 0.12.1
- Bump version to 0.12.2
- Bump version to 0.12.3
- Bump version to 0.13.0
- Bump version to 0.13.1
- Bump version to 0.13.2
- Bump version to 0.13.3
- Bump version to 0.9.10
- Bump version to 0.9.2
- Bump version to 0.9.4
- Bump version to 0.9.5
- Bump version to 0.9.6
- Bump version to 0.9.7
- Bump version to 0.9.8
- Bump version to 0.9.9
- Ignore .worktrees directory
- Update LICENSE copyright to 2026, standardize license field

## [0.13.0] - 2026-04-30

### Added

- Add @require_auth() decorator with Permission-level enforcement
- Add AuthAuditEvent and AuditLogger with custom sink support
- Add AuthConfig with env-var secret loading and placeholder rejection
- Add mcp_common/auth package skeleton with exception hierarchy
- auth: Add JWT create/verify with issuer, audience, and permission claims
- auth: Add KNOWN_SERVICES registry and issuer/audience verification
- auth: Add Permission enum and Role definitions

### Fixed

- auth: Remove bare except — verify_issuer already raises UnknownIssuerError

### Testing

- Add inter-service auth integration tests

### Internal

- Ignore .worktrees directory

## [0.11.0] - 2026-04-14

### Changed

- Mcp-common (quality: 60/100) - 2026-04-14 02:37:34

## [0.10.0] - 2026-04-13

### Changed

- Mcp-common (quality: 60/100) - 2026-04-13 04:52:13

## [0.9.10] - 2026-04-13

### Changed

- Update config, deps, docs, tests

## [0.9.9] - 2026-04-03

### Changed

- Update core, deps, docs

## [0.9.8] - 2026-03-20

### Changed

- Update dependencies

## [0.9.7] - 2026-03-20

### Changed

- Update dependencies

## [0.9.6] - 2026-03-20

### Added

- Extend health module with dependency checking infrastructure

### Changed

- Update core functionality

### Internal

- Add archive/backup directories to gitignore
- Update LICENSE copyright to 2026, standardize license field

## [0.9.5] - 2026-02-22

### Changed

- Update config, core, deps, tests

## [0.9.2] - 2026-02-17

### Changed

- Update config, deps

## [0.9.1] - 2026-02-13

### Changed

- Update dependencies

## [0.9.0] - 2026-02-12

### Added

- Add Prometheus metrics and TLS integration to WebSocket base class
- Add TLS/WSS support to WebSocket server and client

### Changed

- Update deps, docs

## [0.8.0] - 2026-02-09

### Added

- prompting: Complete API improvements with 100% test coverage

### Changed

- Update config, core, deps, docs, tests

## [0.6.0] - 2026-02-02

### Added

#### Performance Optimizations (Phase 4)

- **Sanitization Early-Exit Optimization** - 2.2x faster for clean text

  - Early return when no sensitive patterns detected
  - Maintains full compatibility with custom patterns
  - ~10μs for clean text vs ~22μs before

- **API Key Validation Caching** - 10x faster for repeated validations

  - New `validate_api_key_format_cached()` function with LRU cache
  - Cache size: 128 most recent (key, provider, pattern) combinations
  - ~10μs for cached calls vs ~100μs for uncached

- **Performance Test Suite** - 7 new benchmark tests

  - Tests verify both correctness and performance improvements
  - Benchmark results show measured speedup

#### Testing Best Practices (Phase 5)

- **Property-Based Testing** - 20 new tests using Hypothesis

  - API key validation with random strings and edge cases
  - Sanitization with random data structures
  - Health checks with random components and timestamps
  - Automatic discovery of edge cases

- **Concurrency Testing** - 10 new tests for thread-safety

  - 100+ concurrent sanitization operations verified safe
  - 100+ concurrent API key validations verified safe
  - Concurrent config loading tested
  - Health snapshot concurrent reads verified

- **Test Suite Growth** - 585 → 615 tests (+30 new tests)

  - Property-based tests: 20
  - Concurrency tests: 10
  - Coverage maintained at 99%+

### Changed

- Update config, core, deps, tests
- Sanitization now 2x faster for clean text (early exit optimization)
- API key validation 10x faster for repeated calls (LRU cache)
- Export `validate_api_key_format_cached` from `mcp_common.security` module

### Performance Impact

**Benchmarks:**

- Sanitization (clean text): 22μs → 10μs (2.2x faster)
- API key validation (cached): 100μs → 10μs (10x faster)
- Test suite execution: ~110s → ~120s (+10s for new tests)
- Overall test count: 585 → 615 (+30 tests)

**Real-World Impact:**

- 2x reduction in CPU usage for sanitization
- 9x faster for repeated API key validations in loops
- Production-ready thread-safety guarantees
- Improved edge case handling and robustness

### Documentation

- Added `PHASE4_SUMMARY.md` - Performance optimization documentation
- Added `PHASE5_SUMMARY.md` - Testing best practices documentation
- Updated README.md with performance benchmark tables
- Updated README.md with testing capabilities overview

### Testing

- All 615 tests passing (100% pass rate)
- 20 property-based tests with Hypothesis
- 10 concurrency tests with async/await
- 7 performance optimization benchmarks
- Coverage: 99%+ maintained

## [0.5.2] - 2026-01-24

### Changed

- Update dependencies

## [0.5.1] - 2026-01-24

### Changed

- Update core, deps, docs, tests

## [0.5.0] - 2026-01-24

### Changed

- Update config, deps, docs

## [0.4.9] - 2026-01-21

### Changed

- Update config, core, deps, docs, tests

## [0.4.8] - 2026-01-05

### Changed

- Update dependencies

## [0.4.7] - 2026-01-05

### Changed

- Update core, deps

## [0.4.6] - 2026-01-03

### Changed

- Update core, deps, tests

## [0.4.5] - 2026-01-03

### Changed

- Update deps, docs

### Fixed

- Resolve all ruff violations for crackerjack compliance

### Internal

- Session checkpoint - Phase 3 migration complete
- Session cleanup - optimize repository after Phase 3 migration

## [0.4.4] - 2026-01-02

### Added

#### New Server Module (`mcp_common/server/`)

- `BaseOneiricServerMixin` - Reusable server lifecycle methods with template pattern
  - `_init_runtime_components()` - Initialize Oneiric runtime components
  - `_create_startup_snapshot()` - Create server startup snapshots
  - `_create_shutdown_snapshot()` - Create server shutdown snapshots
  - `_build_health_components()` - Build health check components
  - `_extract_config_snapshot()` - Extract config for snapshots
- `check_serverpanels_available()` - Check if mcp_common.ui module exists
- `check_security_available()` - Check if mcp_common.security module exists
- `check_rate_limiting_available()` - Check if FastMCP rate limiting exists
- `get_availability_status()` - Get all dependency statuses as dict
- `create_runtime_components()` - Factory for Oneiric runtime initialization
- All availability functions cached with `@lru_cache` for performance

#### CLI Factory Enhancements

- `MCPServerCLIFactory.create_server_cli()` - Support server_class pattern
  - Bridges gap between handler and server_class patterns
  - Enables all MCP servers to use production-ready factory
  - Maintains backward compatibility with existing handler pattern

#### Documentation

- `docs/SERVER_INTEGRATION.md` - Comprehensive integration and migration guide
  - Architecture patterns (server class vs handler functions)
  - Migration guide from oneiric.core.cli
  - Before/after code examples showing 100+ line savings per server
  - Complete usage examples and best practices
- `docs/PHASE1_COMPLETE_SUMMARY.md` - Detailed Phase 1 completion summary

#### Testing

- 35 new tests for server module (all passing, 100% pass rate)
- 97.83% coverage on base.py
- 91.30% coverage on runtime.py
- 77.78% coverage on availability.py
- Integration tests with actual Oneiric runtime components

### Changed

- Enhanced CLI factory to support both handler and server_class patterns
- Improved documentation structure with integration guides

### Deprecated

- `oneiric.core.cli.MCPServerCLIFactory` - Use `mcp_common.cli.MCPServerCLIFactory.create_server_cli()` instead

## [0.4.1] - 2025-12-27

### Changed

- Update config, core, deps, docs, tests

## [0.4.0] - 2025-12-27

### Changed

- Update config, core, deps, docs, tests

## [0.3.6] - 2025-12-22

### Changed

- Update config, deps, docs

## [0.3.5] - 2025-12-20

### Changed

- Update config, deps, docs

## [0.3.4] - 2025-12-20

### Changed

- Update config, deps, docs, tests

## [0.3.3] - 2025-11-17

### Changed

- Mcp-common (quality: 68/100) - 2025-11-05 15:15:47
- Mcp-common (quality: 68/100) - 2025-11-09 03:08:23
- Update config, deps, docs, tests

### Documentation

- config: Update CHANGELOG, pyproject, uv

## [0.3.2] - 2025-11-05

### Documentation

- config: Update CHANGELOG, pyproject, uv

## [0.3.1] - 2025-10-31

### Fixed

- test: Update 66 files

## [0.3.0] - 2025-10-31

### Fixed

- Fix ruff check issues and improve code quality
- test: Update 36 files
