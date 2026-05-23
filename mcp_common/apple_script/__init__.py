"""AppleScript bridge shared across mcp-common and mahavishnu."""

from .bridge import OSASCRIPT_AVAILABLE, run
from .exceptions import AppleScriptError, ScriptTimeoutError

__all__ = ["run", "OSASCRIPT_AVAILABLE", "AppleScriptError", "ScriptTimeoutError"]