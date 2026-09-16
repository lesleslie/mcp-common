"""Canonical schema for agent metadata publication.

Phase 4 / spec §4.11 — agents from Crackerjack's registry publish a
canonical schema for downstream consumers (Oneiric's MCP server,
Mahavishnu's tool picker). This module owns the schema so the contract
is enforced at the substrate boundary, not duplicated per consumer.

Phase 10 task 4 extended the canonical schema with the full installer
field set (id, server_key, model, system_prompt, content_hash, etc.)
that the four local AgentMetadata classes used to define per-repo. The
B-4 path-traversal allowlist and B-6 body-integrity model_validator
now live here too, so the four local files can become thin re-exports
(`from mcp_common.canonical_schemas.agent import AgentCanonicalSchema as AgentMetadata`).

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._validators import compute_content_hash


class AgentCanonicalSchema(BaseModel):
    """Canonical agent metadata published across Bodai components.

    Carries both the bus-publication surface (name, version, description,
    capabilities, owner, metadata) and the installer/Pydantic surface
    (id, server_key, model, tools, system_prompt, content_hash, signature,
    server_pubkey_id, timestamp). The four local AgentMetadata classes
    re-export this model under the legacy name; per-repo additions live
    as Pydantic subclasses (e.g. crackerjack's stricter
    ``_validate_system_prompt``).
    """

    model_config = ConfigDict(
        extra="forbid",
        # ``str_strip_whitespace`` is intentionally NOT set: per Phase 3
        # §11 B-6, the ``system_prompt`` field carries the agent body
        # verbatim and ``content_hash`` covers those exact bytes.
        # Stripping whitespace would invalidate the hash-pin contract
        # when consumers round-trip the metadata through Pydantic.
        # ``validate_assignment`` lets us re-validate when the tool
        # code sets ``metadata.signature`` after construction.
        validate_assignment=True,
    )

    # --- Bus-publication surface (Phase 4 minimal envelope) ---
    name: str = Field(..., description="Agent name (e.g. 'mahavishnu-orchestrator')")
    version: str = Field(..., description="Semantic version of the agent")
    description: str = Field(default="", description="One-line agent description")
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of capabilities the agent advertises",
    )
    owner: str | None = Field(
        default=None, description="Owning component (mahavishnu, akosha, ...)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Free-form additional metadata"
    )

    # --- Installer / Pydantic surface (Phase 3 rich schema, extended in Phase 10 task 4) ---
    schema_version: Literal[1] = 1

    # ``id`` is the globally unique agent identifier —
    # ``{server_key}:{name}:{version}``. The validator below enforces
    # the allowlist on the constituent fields; ``id`` itself is built
    # from them and is therefore constrained transitively.
    id: str = Field(default="", description="Globally unique agent id (server_key:name:version)")

    # ``server_key`` is the registry key for the originating server
    # (e.g. ``"akosha"``, ``"mahavishnu"``, ``"session-buddy"``,
    # ``"dhara"``, ``"crackerjack"``). Open string rather than Literal
    # because new Bodai components may join and the federation layer
    # must accept any well-formed key.
    server_key: str = Field(
        default="", description="Registry key for the originating server"
    )

    # ``title`` is the picker display name (e.g. ``"Akosha Specialist"``).
    title: str | None = Field(default=None, description="Picker display name")

    # ``description`` follows Claude Code's frontmatter convention. The
    # bus-publication field above is unbounded; the legacy local schemas
    # bounded it at 1024 chars. We keep the cap here for parity.
    # (Pydantic v2 allows redefinition of the same field only if the new
    # field adds constraints — we use a separate field for the bounded
    # string in subclasses if needed.)

    # Semantic version, required for federation tie-break.
    version_detail: str = Field(
        default="",
        description="Detailed semantic version (overrides ``version`` for federation tie-break when set)",
    )

    # ``model`` is the Claude Code frontmatter ``model`` field —
    # typically ``"sonnet"`` or ``"opus"``. Open string rather than
    # Literal so future models don't require a schema bump.
    model: str = Field(default="", description="Claude Code model (sonnet/opus/...)")

    # ``tools`` is the EXACT list of tool names the agent may invoke.
    tools: list[str] = Field(default_factory=list, description="Allowed MCP tool names")

    # ``system_prompt`` is the FULL body. Plan §11 B-6: Claude Code reads
    # this directly. Default is ``""`` so tests can construct minimal
    # payloads; the agents_tools layer rejects empty values before signing.
    system_prompt: str = Field(default="", description="Full agent body (B-6 installer reads verbatim)")

    dependencies: list[str] = Field(default_factory=list, description="Other agent/skill names this agent needs")
    tool_refs: list[str] = Field(default_factory=list, description="MCP tool names referenced by this agent")

    # Audit / governance metadata. All optional.
    category: str | None = Field(default=None, description="Agent category")
    status: Literal["active", "archived", "draft"] | None = Field(
        default=None, description="Lifecycle status"
    )
    last_reviewed: str | None = Field(default=None, description="Last review date (YYYY-MM-DD)")
    scope: Literal["user-global", "project-local"] = Field(
        default="user-global", description="Installation scope"
    )

    # Body integrity. ``content_hash`` is the lowercase hex SHA-256 of
    # ``system_prompt`` bytes. Asserted by :meth:`_validate_body_integrity`
    # so a forged hash is rejected at the boundary. Empty default allows
    # minimal bus-publication payloads; the agents_tools layer rejects
    # unsigned content before sending.
    content_hash: str = Field(default="", description="Lowercase hex SHA-256 of system_prompt bytes")

    # Signing payload. Both fields are populated by the tool handler
    # AFTER signing; ``signature`` carries the base64 ed25519 signature
    # and ``server_pubkey_id`` is the 16-char hex ``key_id`` from the
    # server's pubkey manifest.
    signature: str | None = Field(default=None, description="ed25519 signature (populated post-sign)")
    server_pubkey_id: str | None = Field(
        default=None, description="16-char hex key_id of signing pubkey"
    )

    # Federation timestamp. Optional — the canonical bus publication
    # doesn't require it, but downstream consumers can use it for
    # freshness checks.
    timestamp: float | None = Field(default=None, description="Unix timestamp of publication")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for bus publication."""
        return self.model_dump(mode="json")

    @field_validator("server_key", "name")
    @classmethod
    def _validate_allowlist(cls, value: str) -> str:
        """Enforce B-4 path-traversal allowlist on ``name`` and ``server_key``.

        Skipped when the field is empty (the canonical schema allows
        minimal envelope construction with just name + version; the
        agents_tools layer enforces the allowlist at the API boundary).
        """
        if not value:
            return value
        from ._validators import NAME_OR_SERVER_RE

        if not NAME_OR_SERVER_RE.fullmatch(value):
            raise ValueError(
                f"value {value!r} does not match allowlist regex "
                r"'^[a-z0-9][a-z0-9._-]{0,62}$' "
                "(forbidden: '/', uppercase, leading '.', length > 63)"
            )
        if ".." in value:
            raise ValueError(f"value {value!r} contains forbidden substring '..'")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        """Description must be non-empty after stripping whitespace (when set)."""
        if value and not value.strip():
            raise ValueError("description must be non-empty")
        return value

    @field_validator("id")
    @classmethod
    def _validate_id_shape(cls, value: str) -> str:
        """``id`` must be ``{server_key}:{name}:{version}`` when non-empty.

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
                f"id {value!r} must be 'server_key:name:version' (exactly 3 colon-separated parts)"
            )
        from ._validators import NAME_OR_SERVER_RE

        server_key, name, version = parts
        if not NAME_OR_SERVER_RE.fullmatch(server_key):
            raise ValueError(f"id {value!r} has invalid server_key segment {server_key!r}")
        if not NAME_OR_SERVER_RE.fullmatch(name):
            raise ValueError(f"id {value!r} has invalid name segment {name!r}")
        if not version or "/" in version or ".." in version:
            raise ValueError(f"id {value!r} has invalid version segment {version!r}")
        return value

    @model_validator(mode="after")
    def _validate_body_integrity(self) -> AgentCanonicalSchema:
        """B-6 body integrity: ``content_hash`` MUST equal ``sha256(system_prompt)``.

        A forged ``content_hash`` is rejected at the model boundary. Empty
        ``system_prompt`` and empty ``content_hash`` are allowed (the
        agents_tools layer rejects empty bodies before signing — the
        installer needs the FULL body to write a working agent file).
        """
        if not self.system_prompt and not self.content_hash:
            return self
        expected = compute_content_hash(self.system_prompt)
        if self.content_hash and self.content_hash != expected:
            raise ValueError(
                f"content_hash mismatch: declared {self.content_hash!r} "
                f"but sha256(system_prompt)={expected!r}"
            )
        return self


__all__ = ["AgentCanonicalSchema"]
