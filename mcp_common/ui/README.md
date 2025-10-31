# UI Layer

## Purpose

The UI layer wraps Rich-based presentation primitives used during server startup and runtime status updates.

## Server Panels

- `ServerPanels.startup_success(...)` renders launch banners with host details.
- `ServerPanels.startup_failure(...)` highlights blocking issues with remediation steps.
- Additional helpers surface rate limit summaries and connectivity hints.

When adding new UI components, ensure they remain console-friendly, accept plain data structures, and are exercised in `tests/test_ui_panels.py` to keep the Rich output stable.
