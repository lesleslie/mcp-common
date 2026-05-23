"""Async AppleScript bridge for macOS subprocess execution."""

import asyncio
import shutil

from .exceptions import AppleScriptError, ScriptTimeoutError

OSASCRIPT_AVAILABLE = shutil.which("osascript") is not None


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