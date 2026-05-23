"""Async AppleScript bridge for macOS subprocess execution."""

import asyncio
import shutil

from .exceptions import AppleScriptError, ScriptTimeoutError

OSASCRIPT_AVAILABLE = shutil.which("osascript") is not None


def escape_for_applescript(value: str) -> str:
    """Escape a string for AppleScript following the canonical spec.

    Rules (per iterm2-applescript-protocol.md):
    1. Backslash \\ → \\\\  (escape first)
    2. Double-quote " → \\"
    3. Single-quote ' → \\'
    4. Tab \\t → \\t
    5. Carriage return \\r → removed
    """
    escaped = value.replace("\\", "\\\\")  # backslash first
    escaped = escaped.replace('"', '\\"')   # double-quote
    escaped = escaped.replace("'", "\\'")   # single-quote
    escaped = escaped.replace("\t", "\\t")  # tab
    escaped = escaped.replace("\r", "")     # carriage return removed
    return escaped


def build_applescript_string(value: str) -> str:
    """Build an AppleScript string literal, handling multi-line via & return &.

    Single-line strings are returned as "..." literals.
    Multi-line strings use the "line1" & return & "line2" & return & "line3" syntax.
    """
    lines = value.split("\n")
    if len(lines) == 1:
        return f'"{escape_for_applescript(value)}"'
    escaped_lines = [f'"{escape_for_applescript(line)}"' for line in lines]
    return " & return & ".join(escaped_lines)


async def run(script: str, timeout: float = 30.0) -> str:
    """Run an AppleScript and return output.

    Args:
        script: AppleScript source to execute.
        timeout: Seconds before killing subprocess (default 30).

    Returns:
        stdout as decoded string.

    Raises:
        AppleScriptError: osascript not available (non-macOS) or non-zero exit.
        ScriptTimeoutError: Subprocess exceeded timeout.
    """
    if not OSASCRIPT_AVAILABLE:
        raise AppleScriptError("osascript not available (macOS only)")

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript",
            "-e",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            err = stderr.decode().strip() if stderr else "Unknown AppleScript error"
            raise AppleScriptError(stderr=err)
        return stdout.decode().strip()
    except asyncio.TimeoutError:
        proc.kill()
        raise ScriptTimeoutError(f"AppleScript timed out after {timeout}s")
    except Exception as e:
        raise AppleScriptError(f"Failed to run AppleScript: {e}") from e