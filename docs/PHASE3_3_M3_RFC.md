# Phase 3.3 M3: Replace sys.exit() with Custom Exceptions

**RFC Date**: 2025-01-27
**Status**: 📝 Draft
**Priority**: Moderate (M3)
**Estimated Effort**: 45 minutes

---

## Problem Statement

Multiple MCP servers use `sys.exit()` in library/module code for error handling. This creates several issues:

1. **No Graceful Degradation**: Calling code cannot catch and handle errors
2. **Poor Testability**: Difficult to test error conditions without exiting test runner
3. **Coupling**: Forces immediate termination instead of allowing error handling strategies
4. **Anti-Pattern**: Using `sys.exit()` in library code is considered non-Pythonic

### Current sys.exit() Usage Patterns

Found **18 files** with `sys.exit()` calls across MCP servers:

**Configuration Validation** (should be replaced):
- `/Users/les/Projects/unifi-mcp/unifi_mcp/config.py` (lines 90, 152, 157)
- `/Users/les/Projects/excalidraw-mcp/excalidraw_mcp/config.py`
- Other config modules

**Dependency Checks** (should be replaced):
- `/Users/les/Projects/session-mgmt-mcp/session_mgmt_mcp/server.py` (line 119 - FastMCP missing)

**CLI Entry Points** (keep as-is):
- `/Users/les/Projects/raindropio-mcp/raindropio_mcp/main.py` (line 70 - `--version` flag)
- `/Users/les/Projects/opera-cloud-mcp/opera_cloud_mcp/main.py`
- Other main.py entry points

---

## Proposed Solution

### 1. Create Custom Exception Hierarchy

Create a new module: `/Users/les/Projects/mcp-common/mcp_common/exceptions.py`

```python
"""Custom exceptions for MCP server lifecycle and configuration."""

from __future__ import annotations


class MCPServerError(Exception):
    """Base exception for all MCP server errors."""

    pass


class ServerConfigurationError(MCPServerError):
    """Raised when server configuration is invalid or incomplete."""

    def __init__(
        self, message: str, field: str | None = None, value: str | None = None
    ) -> None:
        self.field = field
        self.value = value
        super().__init__(message)


class ServerInitializationError(MCPServerError):
    """Raised when server fails to initialize due to environment issues."""

    def __init__(
        self, message: str, component: str | None = None, details: str | None = None
    ) -> None:
        self.component = component
        self.details = details
        super().__init__(message)


class DependencyMissingError(MCPServerError):
    """Raised when a required dependency is not available."""

    def __init__(
        self,
        message: str,
        dependency: str | None = None,
        install_command: str | None = None,
    ) -> None:
        self.dependency = dependency
        self.install_command = install_command
        super().__init__(message)


class CredentialValidationError(ServerConfigurationError):
    """Raised when credentials fail validation."""

    pass
```

### 2. Migration Pattern

**BEFORE (Anti-pattern)**:
```python
def validate_credentials_at_startup(self) -> None:
    if not self.username or not self.username.strip():
        print("❌ Username Validation Failed", file=sys.stderr)
        print("   Username is not set", file=sys.stderr)
        sys.exit(1)
```

**AFTER (Custom Exception)**:
```python
from mcp_common.exceptions import CredentialValidationError

def validate_credentials_at_startup(self) -> None:
    if not self.username or not self.username.strip():
        raise CredentialValidationError(
            message="Username is not set in configuration",
            field="username",
        )
```

**Entry Point Handling**:
```python
def main() -> None:
    try:
        settings = Settings()
        settings.validate_credentials_at_startup()
        server = create_server(settings)
        server.run()
    except MCPServerError as e:
        print(f"❌ Server Error: {e}", file=sys.stderr)
        sys.exit(1)  # Only exit at entry point
    except KeyboardInterrupt:
        print("\nServer interrupted by user", file=sys.stderr)
        sys.exit(0)
```

### 3. Benefits

1. **Graceful Error Handling**: Calling code can catch exceptions and implement retry logic
2. **Better Testing**: Can test error conditions without exiting test runner
3. **Rich Error Context**: Exceptions carry structured information (field, component, details)
4. **Separation of Concerns**: Entry points decide exit strategy, not library code
5. **Stack Traces**: Exceptions provide full context for debugging

---

## Implementation Plan

### Phase 1: Create Exception Module (5 minutes)
1. Create `/Users/les/Projects/mcp-common/mcp_common/exceptions.py`
2. Define exception hierarchy with docstrings
3. Export exceptions in `__init__.py`

### Phase 2: Migrate Configuration Validation (20 minutes)
Files to migrate:
- `unifi-mcp/unifi_mcp/config.py` (3 instances)
- `excalidraw-mcp/excalidraw_mcp/config.py`
- `session-mgmt-mcp` (configuration-related sys.exit calls)
- `opera-cloud-mcp` (configuration-related sys.exit calls)

Pattern:
1. Replace `sys.exit(1)` with appropriate exception
2. Update entry points to catch and handle exceptions
3. Preserve error messages (now in exception message)

### Phase 3: Migrate Dependency Checks (10 minutes)
Files to migrate:
- `session-mgmt-mcp/session_mgmt_mcp/server.py:119` (FastMCP missing)
- Other dependency checks

Pattern:
1. Replace `sys.exit(1)` with `DependencyMissingError`
2. Include install command in exception for better UX

### Phase 4: Update Entry Points (10 minutes)
Files to update:
- All `main.py` and `server.py` files with `run_server()` functions
- Add try/except blocks to catch custom exceptions
- Keep `sys.exit()` at entry point level (appropriate usage)

### Phase 5: Testing & Verification (10 minutes)
1. Test all servers start correctly
2. Test validation errors raise exceptions (not exit)
3. Test entry points catch exceptions and exit gracefully
4. Run existing test suites to ensure no regressions

---

## Files to Modify

### 1. Create New Module
- `/Users/les/Projects/mcp-common/mcp_common/exceptions.py` (new)
- `/Users/les/Projects/mcp-common/mcp_common/__init__.py` (export exceptions)

### 2. Configuration Files (Replace sys.exit)
- `/Users/les/Projects/unifi-mcp/unifi_mcp/config.py`
- `/Users/les/Projects/excalidraw-mcp/excalidraw_mcp/config.py`
- `/Users/les/Projects/session-mgmt-mcp/session_mgmt_mcp/llm_providers.py` (if validation-related)

### 3. Server Initialization Files (Replace sys.exit)
- `/Users/les/Projects/session-mgmt-mcp/session_mgmt_mcp/server.py:119`

### 4. Entry Points (Add exception handling)
- `/Users/les/Projects/unifi-mcp/unifi_mcp/server.py` (run_server function)
- `/Users/les/Projects/raindropio-mcp/raindropio_mcp/main.py` (main function)
- `/Users/les/Projects/opera-cloud-mcp/opera_cloud_mcp/main.py` (main function)
- `/Users/les/Projects/excalidraw-mcp/excalidraw_mcp/server.py` (main function)
- Other entry points as needed

### 5. DO NOT Modify (Appropriate sys.exit Usage)
- `--version` flag handlers (CLI convention)
- `--help` flag handlers (CLI convention)
- Final exit at entry point level (after catching exceptions)

---

## Testing Strategy

### Unit Tests
```python
def test_invalid_username_raises_exception():
    """Test that invalid username raises CredentialValidationError."""
    with pytest.raises(CredentialValidationError) as exc_info:
        settings = Settings(username="")
        settings.validate_credentials_at_startup()

    assert exc_info.value.field == "username"
    assert "not set" in str(exc_info.value).lower()
```

### Integration Tests
```python
def test_server_catches_config_error(capsys):
    """Test that server entry point catches and logs config errors."""
    # Simulate missing config
    with pytest.raises(SystemExit) as exc_info:
        main()  # Entry point should catch exception and call sys.exit(1)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Server Error" in captured.err
```

---

## Decision Points

### Q1: Should we keep sys.exit() at entry point level?
**Decision**: YES - Entry points (main.py, CLI commands) should use sys.exit() to return proper exit codes. This is Pythonic and expected for CLI tools.

### Q2: Should we replace ALL sys.exit() calls?
**Decision**: NO - Only replace sys.exit() in:
- Configuration validation methods
- Dependency checks in library code
- Server initialization code
- Any code that might be imported and called programmatically

Keep sys.exit() in:
- CLI flag handlers (--version, --help)
- Entry point error handling (after catching exceptions)

### Q3: Should exceptions include structured data?
**Decision**: YES - Exceptions should include:
- `field` for configuration errors (which field failed)
- `component` for initialization errors (which component failed)
- `dependency` + `install_command` for missing dependencies
This enables better error messages and programmatic handling.

---

## Risks & Mitigations

### Risk 1: Breaking existing error handling
**Mitigation**: Add exception handling at entry points before removing sys.exit() calls

### Risk 2: Test failures due to expected exits
**Mitigation**: Update tests to expect exceptions instead of SystemExit

### Risk 3: Missing some sys.exit() calls
**Mitigation**: Use comprehensive grep to find all instances, document which to keep

---

## Success Criteria

1. ✅ Custom exception module created in mcp-common
2. ✅ All configuration validation uses custom exceptions
3. ✅ All dependency checks use custom exceptions
4. ✅ Entry points catch exceptions and handle gracefully
5. ✅ All servers start correctly
6. ✅ Error messages are preserved (better UX)
7. ✅ Test suites pass without regressions
8. ✅ Documentation updated (migration guide)

---

## References

- **PEP 8**: Avoid using sys.exit() in library code
- **Python Best Practices**: Raise exceptions, don't exit
- **Phase 3 Review**: `/Users/les/Projects/mcp-common/docs/PHASE3_CONSOLIDATED_REVIEW.md`

---

**Created**: 2025-01-27
**Status**: 📝 Draft - Ready for Implementation
**Next Step**: Create exception module and begin Phase 1
