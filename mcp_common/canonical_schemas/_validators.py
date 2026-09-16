"""Shared validators and helpers for canonical agent/skill schemas.

Per Phase 10 task 4 / spec §4.11 — the B-4 path-traversal allowlist and
the B-6 body-integrity invariant are substrate-level concerns shared by
every Bodai MCP server. Keeping the regex + helpers here means the
four local schemas (akosha, mahavishnu, session-buddy, crackerjack) no
longer re-define the same logic — they re-export from this module.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import field_validator

# Strict allowlist regex per B-4 / plan §5 task #4. Anchored to the
# full string. The first character is one lowercase letter or digit;
# the remaining 0..62 characters are drawn from ``[a-z0-9._-]``. Total
# length is therefore 1..63 characters (the unit tests assert that 64
# chars is rejected).
NAME_OR_SERVER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


def allowlisted_name(value: str) -> bool:
    """B-4 API-boundary check on a ``name`` (or ``server_key`` / ``server``).

    Mirrors the field_validator so failures at the API boundary return
    a uniform error envelope rather than raising past the MCP boundary.

    Forbids ``/``, leading ``.``, uppercase characters, any character
    outside ``[a-z0-9._-]``, total length > 63, and the literal
    substring ``..`` (defense-in-depth, since the regex already forbids
    leading ``.`` but does not forbid ``..`` in the middle).
    """
    return bool(NAME_OR_SERVER_RE.fullmatch(value)) and ".." not in value


def _validate_allowlist_value(value: str, field_label: str) -> str:
    """Reusable B-4 allowlist validator body.

    Raises ``ValueError`` with a uniform message so all four repos
    raise the same error class.
    """
    if not NAME_OR_SERVER_RE.fullmatch(value):
        raise ValueError(
            f"{field_label} {value!r} does not match allowlist regex "
            r"'^[a-z0-9][a-z0-9._-]{0,62}$' "
            "(forbidden: '/', uppercase, leading '.', length > 63)"
        )
    if ".." in value:
        raise ValueError(f"{field_label} {value!r} contains forbidden substring '..'")
    return value


def validate_allowlist_allowlist() -> Any:
    """Pydantic v2 ``field_validator`` factory for B-4 allowlist enforcement.

    Usage::

        @field_validator("server_key", "name")
        @classmethod
        def _check(cls, value: str) -> str:
            return _validate_allowlist_value(value, "value")

    The factory exists so the four repos can wire the validator without
    redefining the regex + ``..`` substring check.
    """
    return field_validator("server_key", "name")(_allowlist_pair)


def _allowlist_pair(cls: Any, value: str) -> str:  # pragma: no cover - factory glue
    """Standalone validator body matching the canonical schema field names."""
    return _validate_allowlist_value(value, "value")


def build_agent_id(server_key: str, name: str, version: str) -> str:
    """Build the canonical agent ``id`` field.

    Convenience helper used by the agents_tools catalog builder. NOT a
    validator — assumes ``server_key`` / ``name`` already pass the
    B-4 allowlist. Splitting this out keeps the tool handler free of
    f-string duplication.
    """
    return f"{server_key}:{name}:{version}"


def compute_content_hash(system_prompt: str) -> str:
    """Compute the lowercase hex SHA-256 of ``system_prompt`` bytes.

    Used by the agents_tools catalog builder. Mirrors the
    ``validate_body_integrity`` invariant so callers can build the
    metadata without re-deriving the hash function.
    """
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()


def coerce_tools_value(value: Any) -> list[str]:
    """Normalize a tools entry from the static catalog to ``list[str]``.

    The catalog row may carry a single string (rare) or a sequence; we
    always coerce to a list to match the schema's ``list[str]`` field.
    """
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


__all__ = [
    "NAME_OR_SERVER_RE",
    "allowlisted_name",
    "build_agent_id",
    "compute_content_hash",
    "coerce_tools_value",
    "_validate_allowlist_value",
]
