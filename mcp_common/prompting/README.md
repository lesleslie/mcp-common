# Prompting and Notification Adapter

Unified cross-platform user interaction for MCP servers with automatic backend detection.

## Features

- ✅ **Native macOS dialogs** (PyObjC backend)

  - NSAlert for dialog boxes
  - NSUserNotification for system notifications
  - NSOpenPanel/NSSavePanel for file selection
  - NSTextField for text/password input

- ✅ **Terminal UI prompts** (prompt-toolkit backend)

  - Cross-platform (Linux, macOS, Windows)
  - Rich formatting and syntax highlighting
  - Async/await support
  - Full-screen application support

- ✅ **Automatic backend detection**

  - Platform-aware selection
  - Graceful fallback
  - Optional dependencies (no bloat)

## Installation

```bash
# Base installation (no prompting support)
pip install mcp-common

# macOS native prompts
pip install 'mcp-common[macos-prompts]'

# Terminal UI prompts (cross-platform)
pip install 'mcp-common[terminal-prompts]'

# Everything
pip install 'mcp-common[all-prompts]'
```

## Quick Start

### Method 1: Factory Function (Recommended)

```python
from mcp_common.prompting import create_prompt_adapter

# Auto-detect best backend (macOS native on macOS, TUI elsewhere)
adapter = create_prompt_adapter()

# Initialize the adapter (loads resources, validates configuration)
await adapter.initialize()

try:
    # Send notification
    await adapter.notify("Build complete!", "All tests passed")

    # Confirm action
    if await adapter.confirm("Deploy to production?"):
        print("Deploying...")

    # Prompt for text input
    name = await adapter.prompt_text("Enter your name:", placeholder="John Doe")

    # Select from choices
    choice = await adapter.prompt_choice(
        "Select environment",
        choices=["staging", "production"],
        default="staging",
    )

    # Select file
    files = await adapter.select_file("Choose config file", allowed_types=["yaml", "json"])
finally:
    # Cleanup resources
    await adapter.shutdown()
```

### Method 2: PromptAdapter Class (Direct Instantiation)

```python
from mcp_common.prompting import PromptAdapter

# Direct instantiation
adapter = PromptAdapter()

# Or with specific backend
adapter = PromptAdapter(backend="pyobjc")

# Or with custom settings
from mcp_common.prompting import PromptAdapterSettings
settings = PromptAdapterSettings(backend="prompt-toolkit", timeout=30)
adapter = PromptAdapter(settings=settings)

# Use the adapter
await adapter.initialize()
try:
    await adapter.notify("Hello!", "This is a notification")
finally:
    await adapter.shutdown()
```

### Method 3: Context Manager (Automatic Cleanup)

```python
from mcp_common.prompting import create_prompt_adapter

# Context manager handles initialization and cleanup automatically
async with create_prompt_adapter() as adapter:
    await adapter.notify("Build complete!", "All tests passed")
    result = await adapter.confirm("Continue?")
    # Resources automatically cleaned up on exit
```

## Backend Selection

### Auto Mode (Recommended)

```python
adapter = create_prompt_adapter(backend="auto")
```

**Platform detection:**

- macOS → PyObjC backend (native dialogs)
- Linux/Windows → prompt-toolkit backend (terminal UI)
- Fallback → If preferred backend unavailable

### Manual Backend Selection

```python
# Force macOS native (even on Linux/Windows, will error)
macos_adapter = create_prompt_adapter(backend="pyobjc")

# Force terminal UI (cross-platform)
tui_adapter = create_prompt_adapter(backend="prompt-toolkit")
```

## API Reference

### create_prompt_adapter()

```python
def create_prompt_adapter(
    backend: Literal["auto", "pyobjc", "prompt-toolkit"] = "auto",
    config: PromptAdapterSettings | None = None,
) -> PromptBackend
```

Create a prompt adapter with automatic backend detection.

**Parameters:**

- `backend`: Backend preference (default: "auto")
  - `"auto"`: Automatically detect best available backend
  - `"pyobjc"`: Force PyObjC backend (macOS only)
  - `"prompt-toolkit"`: Force prompt-toolkit backend (cross-platform)
- `config`: Optional configuration (if None, loads from Oneiric settings or environment variables)

**Returns:**

- Configured prompt backend instance (must call `await adapter.initialize()` before use)

**Example:**

```python
adapter = create_prompt_adapter(backend="auto")
await adapter.initialize()
# Use adapter...
await adapter.shutdown()
```

### PromptAdapter (Class)

```python
class PromptAdapter:
    def __init__(
        self,
        backend: str = "auto",
        settings: PromptAdapterSettings | None = None,
    )
```

Convenient wrapper class for direct instantiation.

**Parameters:**

- `backend`: Backend preference (default: "auto")
- `settings`: Optional settings object

**Example:**

```python
# Direct instantiation
adapter = PromptAdapter()

# With custom settings
from mcp_common.prompting import PromptAdapterSettings
settings = PromptAdapterSettings(backend="pyobjc", timeout=60)
adapter = PromptAdapter(settings=settings)
```

### PromptAdapterSettings

```python
class PromptAdapterSettings(BaseSettings):
    backend: str = "auto"
    timeout: int = 30
    tui_theme: str = "default"
    # ... other settings
```

Configuration for prompt adapters following Oneiric patterns.

**Environment Variables:**
Set via environment variables with `MCP_COMMON_PROMPT_` prefix:

```bash
export MCP_COMMON_PROMPT_BACKEND=pyobjc
export MCP_COMMON_PROMPT_TIMEOUT=60
export MCP_COMMON_PROMPT_TUI_THEME=dark
```

**Loading from Oneiric:**

```python
from mcp_common.prompting import PromptAdapterSettings

# Load from Oneiric settings with environment overrides
settings = PromptAdapterSettings.from_settings()
```

**Backward Compatibility:**

```python
from mcp_common.prompting import PromptConfig  # Alias for PromptAdapterSettings

# Old code still works
config = PromptConfig(backend="pyobjc")
```

### Lifecycle Methods

#### initialize()

```python
async def initialize(self) -> None
```

Initialize backend resources. Must be called before using the adapter.

**PyObjC Backend**: Validates platform and PyObjC availability
**prompt-toolkit Backend**: No-op (no resources to initialize)

#### shutdown()

```python
async def shutdown(self) -> None
```

Cleanup backend resources. Should be called when done with the adapter.

**PyObjC Backend**: Shuts down ThreadPoolExecutor used for GUI operations
**prompt-toolkit Backend**: No-op

#### Context Manager Support

```python
async def __aenter__(self) -> "PromptBackend"
async def __aexit__(self, *args) -> None
```

Automatic resource management with `async with`:

```python
async with create_prompt_adapter() as adapter:
    await adapter.notify("Hello!")
# Resources automatically cleaned up
```

### PromptBackend Methods

#### alert()

```python
async def alert(
    title: str,
    message: str,
    detail: str | None = None,
    buttons: list[str] | None = None,
    default_button: str | None = None,
    style: str = "info",
) -> DialogResult
```

Display an alert dialog with optional buttons.

**Returns:** DialogResult with clicked button

#### confirm()

```python
async def confirm(
    title: str,
    message: str,
    default: bool = False,
    yes_label: str = "Yes",
    no_label: str = "No",
) -> bool
```

Display a confirmation dialog (Yes/No).

**Returns:** True if user clicked Yes, False if No

#### prompt_text()

```python
async def prompt_text(
    title: str,
    message: str,
    default: str = "",
    placeholder: str = "",
    secure: bool = False,
) -> str | None
```

Prompt user for text input.

**Returns:** User input text, or None if cancelled

#### prompt_choice()

```python
async def prompt_choice(
    title: str,
    message: str,
    choices: list[str],
    default: str | None = None,
) -> str | None
```

Prompt user to select from a list of choices.

**Returns:** Selected choice, or None if cancelled

#### notify()

```python
async def notify(
    title: str,
    message: str,
    level: NotificationLevel = NotificationLevel.INFO,
    sound: bool = True,
) -> bool
```

Send a system notification.

**Returns:** True if notification was delivered successfully

#### select_file()

```python
async def select_file(
    title: str,
    allowed_types: list[str] | None = None,
    multiple: bool = False,
) -> list[Path] | None
```

Display file selection dialog.

**Returns:** List of selected file paths, or None if cancelled

#### select_directory()

```python
async def select_directory(
    title: str,
) -> Path | None
```

Display directory selection dialog.

**Returns:** Selected directory path, or None if cancelled

## Backend Comparison

| Feature | PyObjC (macOS) | prompt-toolkit (TUI) |
|---------|-----------------|---------------------|
| **Dialogs** | ✅ Native NSAlert | ✅ Terminal prompts |
| **Notifications** | ✅ NSUserNotification (system) | ✅ Terminal print |
| **File Selection** | ✅ NSOpenPanel (native browser) | ⚠️ Manual path input |
| **Text Input** | ✅ NSTextField | ✅ prompt() |
| **Password** | ✅ NSSecureTextField | ✅ Secure prompt() |
| **Rich Formatting** | ✅ NSAttributedString | ✅ HTML/Style |
| **Async Support** | ⚠️ Requires main thread | ✅ Full async support |
| **Cross-platform** | ❌ macOS only | ✅ All platforms |
| **Dependencies** | Heavy (~50MB) | Medium |

## Examples

### Example 1: Deployment Confirmation

```python
from mcp_common.prompting import create_prompt_adapter

adapter = create_prompt_adapter()

if await adapter.confirm(
    "Deploy to production",
    message="This will affect all users",
    default=False,
):
    # Deploy to production
    await adapter.notify("Deployed successfully", level="success")
else:
    await adapter.notify("Deployment cancelled", level="warning")
```

### Example 2: Configuration Wizard

```python
from mcp_common.prompting import create_prompt_adapter

adapter = create_prompt_adapter()

# Step 1: Get deployment target
env = await adapter.prompt_choice(
    "Select deployment environment",
    choices=["staging", "production"],
    default="staging",
)

# Step 2: Get config file
config_file = await adapter.select_file(
    "Select configuration file",
    allowed_types=["yaml", "json"],
)

# Step 3: Confirm
if await adapter.confirm(
    "Deploy configuration",
    message=f"Deploy {config_file[0].name} to {env}",
):
    # Deploy
    pass
```

### Example 3: Progress Updates

```python
from mcp_common.prompting import create_prompt_adapter

adapter = create_prompt_adapter()

# Notify progress
await adapter.notify("Starting build...", level="info")

# ... build ...

await adapter.notify("Build complete!", level="success")

# On failure
await adapter.notify("Build failed", level="error", sound=True)
```

## Error Handling

```python
from mcp_common.prompting import create_prompt_adapter
from mcp_common.prompting.exceptions import (
    BackendUnavailableError,
    UserCancelledError,
)

try:
    adapter = create_prompt_adapter(backend="pyobjc")
except BackendUnavailableError as e:
    print(f"Backend not available: {e.install_hint}")
    print("Falling back to prompt-toolkit...")
    adapter = create_prompt_adapter(backend="prompt-toolkit")

result = await adapter.confirm("Continue?")
if result is None:
    print("User cancelled the prompt")
```

## Testing

```python
# Test backend availability
from mcp_common.prompting.factory import list_available_backends

available = list_available_backends()
print(f"Available backends: {', '.join(available)}")

# Test auto-detection
from mcp_common.prompting import create_prompt_adapter

adapter = create_prompt_adapter()
print(f"Selected backend: {adapter.backend_name}")
```

## Platform-Specific Notes

### macOS (PyObjC Backend)

- Requires macOS 10.8+ for NSUserNotification
- Requires PyObjC 10.0+ for Python 3.13 compatibility
- All GUI operations run on main thread (handled automatically)
- System notifications require app to be in Notification Center preferences

### Terminal UI (prompt-toolkit Backend)

- Works on all platforms with a terminal
- Supports mouse interaction in compatible terminals
- Rich formatting with ANSI colors
- Full-screen applications possible

## Contributing

When adding new backends:

1. Create a new file in `mcp_common/backends/`
1. Implement the `PromptBackend` protocol
1. Add static `is_available_static()` method
1. Update `factory.py` to include the new backend
1. Add optional dependencies to `pyproject.toml`

Example new backend:

```python
# mcp_common/backends/linux.py
class LibNotifyBackend(PromptBackend):
    """Linux libnotify backend."""

    @staticmethod
    def is_available_static() -> bool:
        import sys
        return sys.platform.startswith("linux")

    # ... implement methods
```
