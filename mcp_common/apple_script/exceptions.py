class AppleScriptError(Exception):
    """Raised when AppleScript execution fails."""

    def __init__(self, message: str | None = None, stderr: str | None = None):
        self.stderr = stderr
        msg = message or stderr or "AppleScript execution failed"
        super().__init__(msg)


class ScriptTimeoutError(AppleScriptError):
    """Raised when AppleScript times out."""

    def __init__(self, message: str):
        super().__init__(message)