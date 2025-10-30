# Exception Suppression Cleanup Action Plan

**Issue**: Overly broad `suppress(Exception)` patterns found across 223 files
**Priority**: HIGH (Phase 3.2 H3)
**Impact**: Hides bugs, makes debugging difficult
**Estimated Effort**: 3-4 hours for MCP servers, 8-10 hours total

______________________________________________________________________

## Problem Analysis

### Current Anti-Pattern

```python
from contextlib import suppress

with suppress(Exception):  # ❌ Catches EVERYTHING - masks bugs
    risky_operation()
```

**Why this is bad**:

- Silently swallows `KeyboardInterrupt`, `SystemExit`
- Hides `NameError`, `AttributeError`, `TypeError` (programming errors)
- Makes debugging nearly impossible
- Violates Python's "errors should never pass silently" principle

______________________________________________________________________

## Replacement Patterns

### Pattern 1: Optional Feature Initialization

**Use case**: Startup features that should fail gracefully

```python
# ❌ Current (too broad)
with suppress(Exception):
    validate_llm_api_keys_at_startup()

# ✅ Better (specific + logged)
try:
    validate_llm_api_keys_at_startup()
except (ImportError, ValueError) as e:
    logger.warning(f"LLM validation skipped: {e}")
except Exception as e:
    logger.error(f"Unexpected LLM validation error: {e}", exc_info=True)
    # Server continues but logs unexpected errors
```

### Pattern 2: Dependency Injection Checks

**Use case**: Check if dependency exists, use default if not

```python
# ❌ Current (too broad)
with suppress(Exception):
    existing = depends.get_sync(SessionLogger)
    if isinstance(existing, SessionLogger):
        return

# ✅ Better (specific)
try:
    existing = depends.get_sync(SessionLogger)
    if isinstance(existing, SessionLogger):
        return
except (KeyError, AttributeError):
    pass  # Dependency not registered, continue to create it
```

### Pattern 3: Progress Reporting (Non-Critical)

**Use case**: Console output that shouldn't crash the server

```python
# ❌ Current (too broad)
with suppress(Exception):
    console.print(Panel("Progress update"))

# ✅ Better (specific + minimal logging)
try:
    console.print(Panel("Progress update"))
except (ValueError, RuntimeError) as e:
    # Console rendering failed, continue silently
    # (Don't log - this is non-critical UI)
    pass
```

### Pattern 4: Resource Cleanup

**Use case**: Cleanup operations that shouldn't fail the main flow

```python
# ❌ Current (too broad)
with suppress(Exception):
    cleanup_temp_files()

# ✅ Better (specific + logged)
try:
    cleanup_temp_files()
except (OSError, PermissionError) as e:
    logger.warning(f"Cleanup failed (non-critical): {e}")
```

______________________________________________________________________

## Priority Classification

### 🔴 **CRITICAL** (Fix immediately - MCP server startup/core paths)

- `server.py`, `main.py`, `server_core.py` in all MCP servers
- Startup validation logic
- Security-related operations

### 🟡 **HIGH** (Fix within 1 week - Core functionality)

- DI registration in `di/__init__.py`
- Progress reporting in MCP tools
- Client initialization

### 🟢 **MEDIUM** (Fix within 1 month - Non-critical features)

- UI/console rendering
- Optional integrations
- Logging operations

______________________________________________________________________

## Affected Files by Project

### **session-mgmt-mcp** (10 instances found)

| File | Lines | Priority | Pattern Type |
|------|-------|----------|--------------|
| `server.py` | 434, 439 | 🔴 CRITICAL | Optional feature init |
| `di/__init__.py` | 50, 59, 70, 82, 94 | 🟡 HIGH | DI checks |
| `server_core.py` | 415, 741 | 🟡 HIGH | Core functionality |
| `natural_scheduler.py` | 178 | 🟢 MEDIUM | Optional feature |

### **crackerjack/mcp** (5+ instances found)

| File | Lines | Priority | Pattern Type |
|------|-------|----------|--------------|
| `context.py` | 104 | 🟡 HIGH | Context management |
| `progress_components.py` | 49, 155, 325, 367 | 🟢 MEDIUM | UI rendering |

### **acb/mcp** (TBD - needs analysis)

### **opera-cloud-mcp** (Already fixed 1 instance in H2)

### **excalidraw-mcp** (TBD - needs analysis)

### **raindropio-mcp** (TBD - needs analysis)

### **Other projects** (TBD - total 223 files)

______________________________________________________________________

## Implementation Checklist

### Phase 1: MCP Server Core Files (Estimated: 1-2 hours)

- [ ] session-mgmt-mcp: `server.py` lines 434, 439
- [ ] crackerjack: `context.py` line 104
- [ ] excalidraw-mcp: Analyze and fix server core
- [ ] raindropio-mcp: Analyze and fix server core
- [ ] Other MCP servers: Analyze and fix server cores

### Phase 2: Dependency Injection (Estimated: 1 hour)

- [ ] session-mgmt-mcp: `di/__init__.py` (5 instances)
- [ ] Document DI-specific exception handling pattern
- [ ] Create reusable `safe_get()` helper

### Phase 3: Progress/UI Components (Estimated: 30 min)

- [ ] crackerjack: `progress_components.py` (4 instances)
- [ ] Evaluate if suppress is acceptable for UI (non-critical)

### Phase 4: Remaining Files (Estimated: 4-6 hours)

- [ ] Complete file inventory (213 remaining files)
- [ ] Categorize by priority
- [ ] Fix systematically by priority

______________________________________________________________________

## Testing Strategy

After each fix:

1. **Run unit tests**: `pytest tests/unit/`
1. **Run integration tests**: `pytest tests/integration/`
1. **Manual smoke test**: Start server, verify no crashes
1. **Check logs**: Verify expected warnings appear

______________________________________________________________________

## Success Criteria

- ✅ Zero `suppress(Exception)` in MCP server core files
- ✅ All suppression uses specific exception types
- ✅ Unexpected errors are logged (not silently suppressed)
- ✅ All tests pass
- ✅ Servers start successfully

______________________________________________________________________

## Notes

- **Keep `suppress()` for truly expected exceptions** (e.g., `KeyError` when checking dict)
- **Always log unexpected exceptions** even if you don't re-raise
- **Consider creating helpers** for common patterns (e.g., `safe_di_get()`)
- **Document decisions** when `Exception` is truly necessary (very rare)

______________________________________________________________________

## Quick Reference: Common Specific Exceptions

| Operation | Expected Exceptions |
|-----------|-------------------|
| File I/O | `OSError`, `PermissionError`, `FileNotFoundError` |
| Import | `ImportError`, `ModuleNotFoundError` |
| Dict/Attribute | `KeyError`, `AttributeError` |
| Validation | `ValueError`, `TypeError` |
| Network | `ConnectionError`, `TimeoutError`, `HTTPError` |
| Parsing | `JSONDecodeError`, `ParseError` |

______________________________________________________________________

**Document Created**: 2025-01-27
**Last Updated**: 2025-01-27
**Status**: Ready for implementation
