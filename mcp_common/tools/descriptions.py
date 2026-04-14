"""Description trimming for MCP tool registration.

Reduces tool docstrings to terse action statements that consume fewer tokens
in Claude's system prompt. Full documentation stays in source code docstrings
for developers but is NOT sent to Claude at runtime.

FastMCP extracts parameter schemas from type hints and Annotated[] types,
NOT from docstrings. Trimming docstrings is safe — it only affects the
top-level description shown to Claude.

Budget:
    Core tools:    200 chars (what it does + key params)
    Standard tools: 150 chars (what it does)
    Utility tools:  100 chars (one-liner)
"""

from __future__ import annotations

MAX_DESCRIPTION_LENGTH = 200

# Sections to strip from tool descriptions
_STRIP_SECTIONS = ("Args:", "Returns:", "Raises:", "Example:", "Examples:", "Note:", "Notes:")


def trim_description(docstring: str | None, max_length: int = MAX_DESCRIPTION_LENGTH) -> str:
    """Extract first paragraph from docstring, trimmed to max_length.

    Strips Examples, Args, Returns, Raises, Note sections.
    Keeps only the first non-empty paragraph.

    Args:
        docstring: The function's docstring to trim.
        max_length: Maximum character length for the result.

    Returns:
        Trimmed description string, or empty string if input is empty.
    """
    if not docstring:
        return ""

    lines: list[str] = []
    for line in docstring.split("\n"):
        stripped = line.strip()
        # Stop at first documentation section header
        if any(stripped.startswith(s) for s in _STRIP_SECTIONS):
            break
        # Collect non-empty lines from first paragraph
        if stripped:
            lines.append(stripped)
        elif lines:
            # We've started collecting and hit an empty line —
            # this is the end of the first paragraph
            break

    if not lines:
        return ""

    result = " ".join(lines)

    if len(result) > max_length:
        # Try to break at a sentence boundary
        truncated = result[:max_length]
        # Find last sentence-ending punctuation
        for sep in (". ", "! ", "? "):
            last_sep = truncated.rfind(sep)
            if last_sep > max_length * 0.5:
                result = result[: last_sep + 1]
                break
        else:
            result = result[: max_length - 3] + "..."

    return result
