---
status: active
role: canonical
date: 2026-07-16
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
topic: mcp-design
---

# iTerm2 AppleScript Protocol Specification

**Date:** 2026-05-23
**Status:** Canonical  <!-- legacy status — see YAML frontmatter -->
**Purpose:** Define the canonical protocol for iTerm2 AppleScript integration across the Bodai ecosystem (mdinject/Swift, Mahavishnu/Python).

______________________________________________________________________

## 1. Overview

This document defines the canonical protocol for iTerm2 AppleScript integration, enabling cross-repository session identity schema compatibility, consistent string escaping, and shared AppleScript pattern templates.

### Session ID Format

Canonical session identifier format: `"session_{iTerm2IntId}"`

Examples:

- `session_123` — session with iTerm2 integer ID 123
- `session_456` — session with iTerm2 integer ID 456

______________________________________________________________________

## 2. Canonical Session Schema

```yaml
ITerm2Session:
  id: string            # "session_{iTerm2IntId}" — canonical across repos
  window_id: string     # iTerm2 unique window id
  tab_id: string | null # null if window-level session
  name: string | null
  current_directory: string | null
  window_index: int    # display/human reference only
  tab_index: int        # display/human reference only
```

### Python Representation

```python
from dataclasses import dataclass

@dataclass
class ITerm2Session:
    id: str              # "session_{iTerm2IntId}"
    window_id: str       # iTerm2 unique window id
    tab_id: str | None   # null if window-level session
    name: str | None
    current_directory: str | None
    window_index: int    # display/human reference only
    tab_index: int       # display/human reference only
```

### Swift Representation

```swift
struct ITerm2Session: Identifiable, Hashable {
    let id: String           // "session_{int}"
    let windowId: String     // iTerm2 unique id (string)
    let tabId: String?       // nil if window-level (no tab)
    let name: String?
    let currentDirectory: String?
    let windowIndex: Int    // for display/human reference only
    let tabIndex: Int
}
```

______________________________________________________________________

## 3. Escaping Rules (Canonical)

Strings sent to AppleScript must be escaped according to the following algorithm. This applies to both single-line and multi-line strings.

### Escaping Algorithm

```python
def escape_for_applescript(value: str) -> str:
    """Escape a string for AppleScript, handling multi-line correctly."""
    # 1. Backslash first (before everything else)
    escaped = value.replace("\\", "\\\\")
    # 2. Double-quote
    escaped = escaped.replace('"', '\\"')
    # 3. Single-quote (AppleScript standard)
    escaped = escaped.replace("'", "\\'")
    # 4. Tab
    escaped = escaped.replace("\t", "\\t")
    # 5. Carriage return (remove, not valid in AppleScript strings)
    escaped = escaped.replace("\r", "")
    # 6. Newline: handled at call site (multi-line with & return &)
    return escaped

def build_applescript_string(value: str) -> str:
    """Build an AppleScript string literal, handling multi-line."""
    lines = value.split("\n")
    if len(lines) == 1:
        return f'"{escape_for_applescript(value)}"'
    # Multi-line: "line1" & return & "line2" & return & "line3"
    escaped_lines = [f'"{escape_for_applescript(line)}"' for line in lines]
    return " & return & ".join(escaped_lines)
```

### Escaping Rules Summary

| Character | Escaped As | Notes |
|-----------|------------|-------|
| `\` (backslash) | `\\` | Escape first, always |
| `"` (double-quote) | `\"` | |
| `'` (single-quote) | `\'` | AppleScript standard |
| `\t` (tab) | `\t` | |
| `\r` (carriage return) | (removed) | Not valid in AppleScript strings |
| `\n` (newline) | `& return &` | Multi-line handling at call site |

### Multi-Line String Handling

When a string contains multiple lines, AppleScript requires joining with `& return &`:

```applescript
"line1" & return & "line2" & return & "line3"
```

______________________________________________________________________

## 4. AppleScript Pattern Templates

### 4.1 Enumerate Sessions

Returns a list of session information for all iTerm2 windows, tabs, and sessions.

```applescript
-- Canonical template
tell application "iTerm2"
    if it is running then
        set output to {}
        repeat with w in windows
            set wIndex to index of w
            repeat with t in tabs of w
                set tIndex to index of t
                repeat with s in sessions of t
                    set sId to id of s
                    set sName to name of s
                    set sCwd to ""
                    try
                        set sCwd to current directory of s
                    end try
                    set end of output to {wIndex, tIndex, sId, sName, sCwd}
                end repeat
            end repeat
        end repeat
        return output
    else
        return {}
    end if
end tell
```

### 4.2 Send Text to Session

Send text to a specific session by session ID.

```applescript
tell application "iTerm2"
    tell session id {session_id}
        write text {escaped_text}
    end tell
end tell
```

### 4.3 Create Window with Profile

Create a new window with a specific iTerm2 profile and optionally run a command.

```applescript
tell application "iTerm2"
    activate
    set newWindow to (create window with profile {profile_name})
    set windowID to unique id of newWindow
    tell newWindow
        tell current session
            write text {escaped_command}
        end tell
    end tell
    return windowID
end tell
```

### 4.4 Close Session

Close a specific session by ID.

```applescript
tell application "iTerm2"
    tell session id {session_id}
        close
    end tell
end tell
```

### 4.5 Get Window Bounds

Get the current bounds (position and size) of a window.

```applescript
tell application "iTerm2"
    tell window {window_index}
        get bounds
    end tell
end tell
```

### 4.6 Set Window Bounds

Set the bounds (position and size) of a window.

```applescript
tell application "iTerm2"
    tell window {window_index}
        set bounds {x, y, width, height}
    end tell
end tell
```

______________________________________________________________________

## 5. Conformance Requirements

Implementations must satisfy the following conformance requirements:

### 5.1 Session Identity

- Session IDs MUST be strings in the format `"session_{iTerm2IntId}"`
- The `id` field of `ITerm2Session` MUST use this format
- Window and tab IDs remain as-is from iTerm2's native string representation

### 5.2 String Escaping

- All six escaping rules MUST be implemented in order
- Multi-line strings MUST use the `& return &` concatenation pattern
- Carriage returns MUST be removed, not escaped
- Backslash MUST be escaped first, before other characters

### 5.3 AppleScript Patterns

- All six pattern templates (enumerate, send, create, close, get bounds, set bounds) MUST be implemented
- Session IDs in `tell session id` MUST use the integer ID (not the "session_N" string format)
- Profile names MUST be passed as raw strings (not escaped)

### 5.4 Conformance Testing

Each repository implementing this protocol SHOULD provide conformance tests that:

1. Verify session ID format matches `"session_{int}"`
1. Verify escaping handles all six character types correctly
1. Verify multi-line string building with `& return &`
1. Verify each AppleScript pattern produces valid AppleScript

______________________________________________________________________

## 6. References

- iTerm2 AppleScript Documentation: https://iterm2.com/documentation-scripting.html
- Swift Implementation: mdinject (AppleScriptBridge)
- Python Implementation: Mahavishnu (`mahavishnu/terminal/adapters/iterm2.py`)
- Design Document: `docs/superpowers/specs/2026-05-23-unified-iterm2-applescript-design.md`
