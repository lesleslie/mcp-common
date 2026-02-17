# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
