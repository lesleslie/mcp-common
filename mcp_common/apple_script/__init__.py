"""AppleScript bridge shared across mcp-common and mahavishnu."""

from .bridge import OSASCRIPT_AVAILABLE, run, escape_for_applescript, build_applescript_string
from .exceptions import AppleScriptError, ScriptTimeoutError

__all__ = ["run", "OSASCRIPT_AVAILABLE", "AppleScriptError", "ScriptTimeoutError", "escape_for_applescript", "build_applescript_string"]