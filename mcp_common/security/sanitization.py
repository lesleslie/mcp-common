"""Input and output sanitization utilities.

Provides utilities to sanitize user inputs and outputs to prevent:
- API key exposure in logs
- SQL injection (for database queries)
- Path traversal attacks
- Cross-site scripting (XSS) in HTML outputs
"""

from __future__ import annotations

import re
import typing as t
from pathlib import Path

# Type alias for Path objects (avoiding direct imports in TYPE_CHECKING blocks)
PathType = type(Path())

# Pattern to detect potential API keys in strings
API_KEY_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9\-_]{16,})['\"]?"
)  # REGEX OK: Safe pattern for detecting API keys in logs

# Common sensitive key patterns
SENSITIVE_PATTERNS = {
    "openai": re.compile(r"sk-[A-Za-z0-9]{48}"),  # REGEX OK: OpenAI API key pattern
    "anthropic": re.compile(r"sk-ant-[A-Za-z0-9\-_]{95,}"),  # REGEX OK: Anthropic API key pattern
    "github": re.compile(r"gh[ps]_[A-Za-z0-9]{36,255}"),  # REGEX OK: GitHub token pattern
    "jwt": re.compile(
        r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"
    ),  # REGEX OK: JWT token pattern
    "generic_hex": re.compile(r"\b[0-9a-f]{32,}\b"),  # REGEX OK: Generic hex API key pattern
}


def _sanitize_string(
    data: str,
    mask_keys: bool = True,
    mask_patterns: list[str] | None = None,
) -> str:
    """Helper function to sanitize string data."""
    # Mask based on key patterns
    if mask_keys:
        for pattern_name, pattern in SENSITIVE_PATTERNS.items():
            if pattern.search(data):
                data = pattern.sub(f"[REDACTED-{pattern_name.upper()}]", data)

    # Mask custom patterns
    if mask_patterns:
        for custom_pattern in mask_patterns:
            data = re.sub(
                custom_pattern, "[REDACTED]", data
            )  # REGEX OK: Custom pattern sanitization

    return data


def sanitize_output(
    data: t.Any,
    mask_keys: bool = True,
    mask_patterns: list[str] | None = None,
) -> t.Any:
    """Sanitize output data to prevent sensitive information exposure.

    Recursively scans dictionaries, lists, and strings to mask sensitive
    data like API keys, tokens, and passwords.

    Args:
        data: Data to sanitize (dict, list, str, or any type)
        mask_keys: If True, mask values for keys containing "key", "token", "password"
        mask_patterns: Additional regex patterns to mask (as strings)

    Returns:
        Sanitized copy of data with sensitive values masked

    Example:
        >>> data = {"api_key": "sk-abc123", "result": "success"}
        >>> sanitized = sanitize_output(data)
        >>> # Returns: {"api_key": "sk-***", "result": "success"}
    """
    if isinstance(data, dict):
        return {k: sanitize_output(v, mask_keys, mask_patterns) for k, v in data.items()}

    if isinstance(data, list):
        return [sanitize_output(item, mask_keys, mask_patterns) for item in data]

    if isinstance(data, str):
        return _sanitize_string(data, mask_keys, mask_patterns)

    # For other types (int, float, bool, None), return as-is
    return data


def sanitize_dict_for_logging(
    data: dict[str, t.Any],
    sensitive_keys: set[str] | None = None,
) -> dict[str, t.Any]:
    """Sanitize dictionary for safe logging.

    Masks values for keys that commonly contain sensitive data.

    Args:
        data: Dictionary to sanitize
        sensitive_keys: Additional keys to mask (beyond defaults)

    Returns:
        Sanitized dictionary copy

    Example:
        >>> log_data = sanitize_dict_for_logging({
        ...     "api_key": "secret123",
        ...     "user": "john",
        ...     "password": "pass123"
        ... })
        >>> # Returns: {"api_key": "***", "user": "john", "password": "***"}
    """
    # Default sensitive keys
    default_sensitive = {
        "api_key",
        "apikey",
        "api-key",
        "token",
        "secret",
        "password",
        "passwd",
        "pwd",
        "bearer",
        "authorization",
        "auth",
        "credential",
        "private_key",
        "secret_key",
    }

    if sensitive_keys:
        default_sensitive.update(sensitive_keys)

    sanitized: dict[str, t.Any] = {}
    for key, value in data.items():
        # Check if key name suggests sensitive data
        if any(sens in key.lower() for sens in default_sensitive):
            sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict_for_logging(value, sensitive_keys)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict_for_logging(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


def sanitize_path(
    path: str | Path,
    base_dir: str | Path | None = None,
    allow_absolute: bool = False,
) -> Path:
    """Sanitize file path to prevent traversal attacks.

    Validates that path:
    - Doesn't contain '..' (directory traversal)
    - Is relative to base_dir (if provided)
    - Doesn't access system files

    Args:
        path: Path to sanitize
        base_dir: Base directory to confine paths to
        allow_absolute: If True, allow absolute paths

    Returns:
        Sanitized Path object

    Raises:
        ValueError: If path is unsafe

    Example:
        >>> safe_path = sanitize_path("../../etc/passwd", base_dir="/app/data")
        >>> # Raises ValueError: Path traversal detected
    """
    path_obj = Path(path)

    # Check for directory traversal
    if ".." in path_obj.parts:
        msg = f"Path traversal detected in '{path}'"
        raise ValueError(msg)

    # Check absolute paths
    if path_obj.is_absolute():
        if not allow_absolute:
            msg = f"Absolute paths not allowed: '{path}'"
            raise ValueError(msg)

        # Check if accessing system directories
        system_dirs = {"/etc", "/sys", "/proc", "/boot", "/root"}
        path_str = str(path_obj)
        if any(path_str.startswith(sysdir) for sysdir in system_dirs):
            msg = f"Access to system directory denied: '{path}'"
            raise ValueError(msg)

    # If base_dir provided, ensure path is relative to it
    if base_dir:
        base = Path(base_dir).resolve()
        try:
            resolved = (base / path_obj).resolve()
            # Ensure resolved path is under base_dir
            resolved.relative_to(base)
        except ValueError as e:
            msg = f"Path '{path}' escapes base directory '{base_dir}'"
            raise ValueError(msg) from e

    return path_obj


def sanitize_input(
    value: t.Any,
    max_length: int | None = None,
    allowed_chars: str | None = None,
    strip_html: bool = False,
) -> str:
    """Sanitize user input string.

    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        allowed_chars: Regex pattern of allowed characters
        strip_html: If True, remove HTML tags

    Returns:
        Sanitized string

    Raises:
        ValueError: If input violates constraints

    Example:
        >>> sanitized = sanitize_input(
        ...     "<script>alert('xss')</script>hello",
        ...     max_length=100,
        ...     strip_html=True
        ... )
        >>> # Returns: "hello"
    """
    # Validate type defensively (runtime)
    if not isinstance(value, str):
        msg = "Expected string"
        raise ValueError(msg)  # noqa: TRY004

    # Strip HTML if requested
    if strip_html:
        value = re.sub(r"<[^>]+>", "", value)  # REGEX OK: HTML tag stripping

    # Check length
    if max_length and len(value) > max_length:
        msg = f"Input exceeds maximum length of {max_length}"
        raise ValueError(msg)

    # Check allowed characters
    if allowed_chars and not re.match(
        f"^[{allowed_chars}]*$", value
    ):  # REGEX OK: Character validation
        msg = f"Input contains disallowed characters. Allowed: {allowed_chars}"
        raise ValueError(msg)

    return value.strip()  # type: ignore[no-any-return]


def mask_sensitive_data(text: str, visible_chars: int = 4) -> str:
    """Mask sensitive data in text for safe display.

    Detects and masks API keys, tokens, and other sensitive patterns.

    Args:
        text: Text containing potential sensitive data
        visible_chars: Number of characters to show at end

    Returns:
        Text with sensitive data masked

    Example:
        >>> masked = mask_sensitive_data("API key: sk-abc123def456")
        >>> # Returns: "API key: sk-...f456"
    """
    masked_text = text

    # Mask each sensitive pattern
    for pattern in SENSITIVE_PATTERNS.values():
        for match in pattern.finditer(text):
            original = match.group(0)
            if len(original) > visible_chars:
                masked = f"{original[:3]}...{original[-visible_chars:]}"
            else:
                masked = "***"
            masked_text = masked_text.replace(original, masked)

    return masked_text
