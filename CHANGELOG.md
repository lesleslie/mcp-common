# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
