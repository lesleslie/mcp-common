# Test Coverage Quick Start Guide

## Overview

Comprehensive test coverage has been added to mcp-common with **6 new test files** containing **~330 test methods**.

## File Locations

All test files are in: `/Users/les/Projects/mcp-common/tests/unit/`

### New Test Files

1. `test_validation_mixin.py` - Validation mixin tests
2. `test_ui_panels.py` - UI panel tests
3. `test_validation.py` - Validation utility tests
4. `test_schemas.py` - Schema tests
5. `test_interfaces.py` - Interface tests
6. `test_exceptions.py` - Exception tests

## Running Tests

### Run All New Tests

```bash
cd /Users/les/Projects/mcp-common
pytest tests/unit/test_validation_mixin.py -v
pytest tests/unit/test_ui_panels.py -v
pytest tests/unit/test_validation.py -v
pytest tests/unit/test_schemas.py -v
pytest tests/unit/test_interfaces.py -v
pytest tests/unit/test_exceptions.py -v
```

### Run All Unit Tests

```bash
pytest tests/unit/ -v
```

### Run with Coverage

```bash
pytest --cov=mcp_common --cov-report=html
open htmlcov/index.html
```

### Run Specific Test Classes

```bash
# Validation Mixin
pytest tests/unit/test_validation_mixin.py::TestValidationMixinRequiredField -v
pytest tests/unit/test_validation_mixin.py::TestValidationMixinCredentials -v

# UI Panels
pytest tests/unit/test_ui_panels.py::TestServerPanelsStartupSuccess -v
pytest tests/unit/test_ui_panels.py::TestServerPanelsStatusTable -v

# Validation
pytest tests/unit/test_validation.py::TestValidateOutput -v
pytest tests/unit/test_validation.py::TestValidateInput -v

# Schemas
pytest tests/unit/test_schemas.py::TestToolResponse -v
pytest tests/unit/test_schemas.py::TestToolInput -v

# Interfaces
pytest tests/unit/test_interfaces.py::TestDualUseToolProtocol -v
pytest tests/unit/test_interfaces.py::TestEnsureDualUseDecorator -v

# Exceptions
pytest tests/unit/test_exceptions.py::TestAPIKeyMissingError -v
pytest tests/unit/test_exceptions.py::TestAPIKeyFormatError -v
```

## Test Coverage Summary

| Module | Coverage Target | Test File |
|--------|----------------|-----------|
| Validation Mixin | 85%+ | `test_validation_mixin.py` |
| UI Panels | 85%+ | `test_ui_panels.py` |
| Validation Utils | 85%+ | `test_validation.py` |
| Schemas | 85%+ | `test_schemas.py` |
| Interfaces | 85%+ | `test_interfaces.py` |
| Exceptions | 85%+ | `test_exceptions.py` |

## Expected Results

After running tests, you should see:
- ✅ All tests pass
- ✅ Overall coverage: 60%+
- ✅ All core modules: 85%+

## Documentation

For detailed information, see:
- `TEST_COVERAGE_EXPANSION.md` - Detailed expansion plan
- `TEST_COVERAGE_COMPLETION_REPORT.md` - Completion report

## Quick Stats

- **Test Files**: 6 new files
- **Test Classes**: 41 classes
- **Test Methods**: ~330 methods
- **Lines of Code**: ~3,900 lines
- **Coverage Target**: 60%+ overall, 85%+ per module

## Status: READY ✅

All tests are created and ready to run. Execute the commands above to verify coverage.
