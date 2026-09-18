"""Canonical schema for skill metadata publication.

Phase 4 / spec §4.11 — skills from Crackerjack's registry publish a
canonical schema for downstream consumers. Skill payloads are signed
by ``mcp_common.signing.SkillsSigner`` so consumers can verify provenance.

Phase 10 task 4 extended the canonical schema with the full installer
field set (id, server, tool_refs, dependencies, content_type, content_hash,
body_size, body_format, allowed_tools, server_pubkey_id, timestamp) that
the four local SkillMetadata classes used to define per-repo. The
B-4 path-traversal allowlist now lives in the canonical schema so the
four local files can become thin re-exports.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._validators import NAME_OR_SERVER_RE


class SkillCanonicalSchema(BaseModel):
    """Canonical skill metadata published across Bodai components.

    Carries both the bus-publication surface (name, version, description,
    tags, owner, prompt, signature, metadata) and the installer/Pydantic
    surface (id, server, tool_refs, dependencies, content_type,
    content_hash, body_size, body_format, allowed_tools, server_pubkey_id,
    timestamp). The four local SkillMetadata classes re-export this model
    under the legacy name.

    Validation behavior:

    - ``name``, ``version`` — required, strict (empty string rejected).
    - ``server``, ``id`` — optional with empty default; when set, strict.
    - ``description`` — optional with empty default; when set, must be
      non-empty after strip AND bounded at 1024 chars.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        # ``validate_assignment`` lets us re-validate when the tool
        # code sets ``metadata.signature`` after construction. Pydantic
        # v2 keeps this opt-in because it has a small cost; here the
        # cost is worth the safety.
        validate_assignment=True,
    )

    # --- Required identity (canonical envelope minimum) ---
    # Empty strings rejected by the ``_validate_name`` validator below —
    # keeping the constraint in code rather than ``min_length`` so the
    # error message carries the B-4 allowlist wording (the akosha
    # test suite matches on the literal ``"allowlist"`` token).
    name: str = Field(..., description="Skill name (e.g. 'crackerjack-fast-hooks')")
    # Local SkillMetadata schemas had ``version: str`` (no default).
    # Keep it required.
    version: str = Field(..., min_length=1, description="Semantic version of the skill")

    # --- Bus-publication surface (Phase 4 minimal envelope) ---
    description: str = Field(
        default="",
        max_length=1024,
        description="One-line skill description (≤1024 chars, non-empty when set)",
    )
    tags: list[str] = Field(default_factory=list, description="Search/discovery tags")
    owner: str | None = Field(default=None, description="Owning component")
    prompt: str | None = Field(default=None, description="Optional prompt body")
    signature: str | None = Field(
        default=None,
        description="ed25519 signature produced by mcp_common.signing.SkillsSigner",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Free-form additional metadata"
    )

    # --- Installer / Pydantic surface (Phase 3 rich schema, extended in Phase 10 task 4) ---
    schema_version: Literal[1] = 1

    # ``id`` is the globally unique skill identifier — ``{server}:{name}:{version}``.
    id: str = Field(
        default="", description="Globally unique skill id (server:name:version)"
    )

    server: str = Field(default="", description="Originating server (registry key)")

    tool_refs: list[str] = Field(
        default_factory=list, description="MCP tool names referenced by this skill"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Other agent/skill names this skill needs"
    )
    content_type: Literal["skill", "agent", "prompt"] = Field(
        default="skill", description="Body content classification"
    )

    # Body integrity. ``content_hash`` is the lowercase hex SHA-256 of
    # the body bytes; ``body_size`` is the byte length. Both are
    # asserted by the client before write (B-1 / plan §11 B-1).
    content_hash: str = Field(
        default="", description="Lowercase hex SHA-256 of body bytes"
    )
    body_size: int = Field(default=0, description="Body byte length")
    body_format: Literal["yaml-frontmatter+markdown"] = Field(
        default="yaml-frontmatter+markdown",
        description="Wire format of the body (B-1 contract)",
    )

    allowed_tools: list[str] = Field(
        default_factory=list, description="Tools this skill may invoke"
    )

    # Signing payload. ``server_pubkey_id`` is populated by the tool
    # handler AFTER signing; the canonical signing payload is the
    # model_dump of this model with that field stripped (see
    # ``canonical_payload_for_signing``).
    server_pubkey_id: str | None = Field(
        default=None, description="16-char hex key_id of signing pubkey"
    )

    timestamp: float = Field(default=0.0, description="Unix timestamp of publication")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for bus publication."""
        return self.model_dump(mode="json")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        """Enforce B-4 path-traversal allowlist on ``name`` (strict).

        Empty strings ARE rejected — the local akosha test suite matches
        the literal ``"allowlist"`` token for ``test_empty_string``.
        """
        if not NAME_OR_SERVER_RE.fullmatch(value):
            raise ValueError(
                f"name {value!r} does not match allowlist regex "
                r"'^[a-z0-9][a-z0-9._-]{0,62}$' "
                "(forbidden: '/', uppercase, leading '.', length > 63)"
            )
        if ".." in value:
            raise ValueError(f"name {value!r} contains forbidden substring '..'")
        return value

    @field_validator("server")
    @classmethod
    def _validate_server(cls, value: str) -> str:
        """Enforce B-4 path-traversal allowlist on ``server`` (when set).

        Empty ``server`` is allowed because the canonical envelope
        contract requires only ``name`` + ``version``.
        """
        if not value:
            return value
        if not NAME_OR_SERVER_RE.fullmatch(value):
            raise ValueError(
                f"server {value!r} does not match allowlist regex "
                r"'^[a-z0-9][a-z0-9._-]{0,62}$' "
                "(forbidden: '/', uppercase, leading '.', length > 63)"
            )
        if ".." in value:
            raise ValueError(f"server {value!r} contains forbidden substring '..'")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        """Description must be non-empty after stripping whitespace (when set).

        With ``str_strip_whitespace=True``, Pydantic strips leading/trailing
        whitespace BEFORE the validator runs, so a whitespace-only value
        arrives here as ``""``. We reject empty descriptions.
        """
        if not value.strip():
            raise ValueError("description must be non-empty")
        return value

    @field_validator("id")
    @classmethod
    def _validate_id_shape(cls, value: str) -> str:
        """``id`` must be ``{server}:{name}:{version}`` when non-empty.

        The constituent fields are individually validated by their own
        validators; this check ensures the composite matches the
        documented format and disallows extra colons in unexpected places.
        Skipped when empty.
        """
        if not value:
            return value
        parts = value.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"id {value!r} must be 'server:name:version' (exactly 3 colon-separated parts)"
            )
        server, name, version = parts
        if not NAME_OR_SERVER_RE.fullmatch(server):
            raise ValueError(f"id {value!r} has invalid server segment {server!r}")
        if not NAME_OR_SERVER_RE.fullmatch(name):
            raise ValueError(f"id {value!r} has invalid name segment {name!r}")
        if not version or "/" in version or ".." in version:
            raise ValueError(f"id {value!r} has invalid version segment {version!r}")
        return value


__all__ = ["SkillCanonicalSchema"]
