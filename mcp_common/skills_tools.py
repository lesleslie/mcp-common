"""Factory for the Phase 1 list_skills + get_skill MCP tool pair.

Per ``docs/plans/2026-09-09-bodai-skill-agent-distribution.md`` Phase 1,
every Bodai MCP server publishes skills via two tools:
``<server>_list_skills`` and ``<server>_get_skill``. The wire shape, the
B-4 path-traversal allowlist, the body SHA-256 hashing (B-6), and
the registration plumbing are shared concerns — this factory owns
them so each server only writes its own catalog and its own signing
policy.

This factory is the parallel companion to
:mod:`mcp_common.agents_tools` — the two are mechanically identical
but the schemas differ. ``AgentCanonicalSchema`` carries an inline
``system_prompt`` field; ``SkillCanonicalSchema`` keeps the body
separate (returned under ``"body"`` in the ``get_skill`` envelope).
The factory's ``_build_unsigned_metadata`` builds the skill-shape
metadata with ``content_hash`` derived from the body bytes, then
the sign callback attaches ``signature`` and ``server_pubkey_id``.

Mechanism vs. policy
--------------------

The factory owns the **mechanism**: catalog validation at startup, the
allowlist check at the API boundary, body stripping + SHA-256 hashing,
the tool registration shape, the success/error envelope, and the
``list`` + ``get`` tool pair. Each server owns the **policy**: catalog
content, where bodies live (file vs synthesized), how the signer is
acquired (lifespan vs singleton vs future-dynamic), and the tool name
prefix.

Security gates (per plan §11):

- **B-1** — every ``get_skill`` response carries an ed25519 signature
  over the canonicalized metadata. The Phase 2 installer verifies
  this before any write to ``~/.claude/skills/<server>-<name>/SKILL.md``.
- **B-4** — the path-traversal allowlist
  ``^[a-z0-9][a-z0-9._-]{0,62}$`` lives in
  ``mcp_common.canonical_schemas._validators.NAME_OR_SERVER_RE``;
  the factory enforces it at the API boundary. The per-server regex
  copy that used to live in each server's skill_registry.py is gone.
- **B-6** — ``content_hash`` is the lowercase hex SHA-256 of the
  stripped body bytes. The schema's
  ``_validate_body_integrity`` (when present) or the factory's own
  post-signing assertion confirms equality.
- **B-7** — each successful tool call invokes ``on_call``,
  which bumps the cycles counter on the signer feed state.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from mcp_common.canonical_schemas._validators import allowlisted_name
from mcp_common.canonical_schemas.skill import SkillCanonicalSchema

logger = logging.getLogger(__name__)


# A catalog entry is a Mapping whose keys are SkillCanonicalSchema field
# names and whose values are JSON-safe. The body is always loaded via
# ``body_loader(name)`` at request time — the catalog stores the
# filename, the body is loaded on demand. There is no inline body
# option (skills are always file-backed; the agent factory's inline
# ``system_prompt`` is an agent-specific affordance for the LLM
# picker's body-preview path).
CatalogEntry = Mapping[str, Any]


def _strip_body(body: str) -> str:
    """Normalize a body for B-6 hash consistency.

    Strips leading/trailing whitespace. Internal whitespace is preserved.
    A body read from disk often has surrounding whitespace from
    frontmatter delimiters or the trailing newline the Write tool
    often drops — strip those so the content_hash is over the
    content-pure bytes. The schema's SkillCanonicalSchema does not
    require post-strip equality on the body (the body is returned
    separately, not stored in the metadata), but the factory's B-6
    invariant still computes the hash from the stripped bytes so
    clients can verify against the same canonical content.
    """
    return body.strip()


def _content_hash(body: str) -> str:
    """B-6 content_hash: lowercase hex SHA-256 of the (stripped) body bytes."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _build_unsigned_metadata(
    entry: CatalogEntry,
    *,
    server_key: str,
    body: str,
) -> SkillCanonicalSchema:
    """Build the unsigned :class:`SkillCanonicalSchema` for one catalog entry.

    The body has already been loaded + stripped by the caller. The
    content hash is computed from the body bytes here so the factory
    owns the B-6 invariant end-to-end. The Pydantic validators (B-4
    allowlist on name/server, B-6 body-integrity hash assertion when
    configured) run on construction; a bad catalog entry fails fast
    at request time.

    Schema-version aware: when the catalog entry carries
    ``"schema_version"`` (default 1), that value is forwarded to the
    schema's ``schema_version`` field. The current canonical schema
    pins ``Literal[1]`` so values other than 1 surface as a
    Pydantic ValidationError at request time.
    """
    name = entry["name"]
    version = entry.get("version", "0.0.0")
    body_bytes = body.encode("utf-8")
    return SkillCanonicalSchema(
        id=f"{server_key}:{name}:{version}",
        server=server_key,
        name=name,
        version=version,
        description=entry.get("description", ""),
        tags=list(entry.get("tags", [])),
        owner=entry.get("owner"),
        prompt=entry.get("prompt"),
        metadata=dict(entry.get("metadata", {})),
        schema_version=entry.get("schema_version", 1),
        tool_refs=list(entry.get("tool_refs", [])),
        dependencies=list(entry.get("dependencies", [])),
        content_type=entry.get("content_type", "skill"),
        content_hash=_content_hash(body),
        body_size=len(body_bytes),
        body_format=entry.get("body_format", "yaml-frontmatter+markdown"),
        allowed_tools=list(entry.get("allowed_tools", [])),
        timestamp=entry.get("timestamp", 0.0),
    )


def _validate_server_key(server_key: str) -> None:
    """Raise ``ValueError`` if ``server_key`` fails the B-4 allowlist."""
    if not allowlisted_name(server_key):
        raise ValueError(
            f"server_key {server_key!r} violates B-4 allowlist "
            r"'^[a-z0-9][a-z0-9._-]{0,62}$' "
            "(forbidden: '/', uppercase, leading '.', length > 63)"
        )


def _validate_skill_catalog(catalog: Sequence[CatalogEntry]) -> dict[str, CatalogEntry]:
    """Eagerly validate the skill catalog, returning ``name -> entry``.

    Surface catalog errors at factory time so they fail at import,
    not at the first request. The body is still loaded on demand.
    """
    name_to_entry: dict[str, CatalogEntry] = {}
    for entry in catalog:
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"catalog entry missing 'name' field (or wrong type): {entry!r}"
            )
        if not allowlisted_name(name):
            raise ValueError(
                f"catalog entry name {name!r} violates B-4 allowlist "
                r"'^[a-z0-9][a-z0-9._-]{0,62}$'"
            )
        if "body_filename" not in entry:
            # The factory itself doesn't read body_filename, but the
            # body_loader callable will. Surface the omission at
            # factory time so a missing filename fails fast.
            raise ValueError(
                f"catalog entry {name!r} missing required 'body_filename' field"
            )
        if name in name_to_entry:
            raise ValueError(f"duplicate catalog entry name: {name!r}")
        name_to_entry[name] = entry
    return name_to_entry


async def _list_skills_impl(
    *,
    server_key: str,
    name_to_entry: dict[str, CatalogEntry],
    body_loader: Callable[[str], str],
    list_tool_name: str,
    on_call: Callable[[], None] | None,
) -> list[dict[str, Any]]:
    """Body of the ``list_skills`` tool (B-6 + B-7 contract).

    Per Phase 1 §11 B-6: the metadata's ``content_hash`` is
    computed from the stripped body bytes; the body itself is NOT
    inlined (use ``get_skill`` for the body). The ``signature`` and
    ``server_pubkey_id`` fields are ``None`` here — they are filled
    by ``get_skill`` since the signature is over the canonical
    payload WITHOUT the signing fields themselves.

    Per B-7: ``on_call`` is invoked to bump ``cycles_total`` so the
    four mandatory feed signals stay accurate.
    """
    if on_call is not None:
        on_call()
    result: list[dict[str, Any]] = []
    for entry in name_to_entry.values():
        try:
            raw_body = body_loader(entry["name"])
        except FileNotFoundError:
            logger.exception(
                "%s: failed to load body for %s",
                list_tool_name,
                entry["name"],
            )
            continue
        body = _strip_body(raw_body)
        metadata = _build_unsigned_metadata(
            entry,
            server_key=server_key,
            body=body,
        )
        result.append(metadata.model_dump(mode="json"))
    return result


async def _get_skill_impl(
    name: str,
    *,
    server_key: str,
    name_to_entry: dict[str, CatalogEntry],
    body_loader: Callable[[str], str],
    sign: Callable[[SkillCanonicalSchema], SkillCanonicalSchema],
    on_call: Callable[[], None] | None,
) -> dict[str, Any]:
    """Body of the ``get_skill`` tool.

    Returns
    ``{"success": True, "metadata": <signed>, "body": <body>}``
    on success. Returns
    ``{"success": False, "error": "..."}`` on:

    - name allowlist violation (B-4) — uniform envelope
      so callers don't have to handle a different error
      class than the Pydantic ValidationError.
    - name not found in this server's catalog
    - body_loader raised (e.g. file missing)
    - Pydantic metadata validation failed
    - ``sign()`` raised (e.g. signer not initialized)
    """
    if on_call is not None:
        on_call()

    # B-4: enforce the allowlist at the API boundary, before
    # constructing the metadata. Uniform error envelope
    # shape across all rejection modes.
    if not allowlisted_name(name):
        return {
            "success": False,
            "error": (
                f"name {name!r} violates path-traversal allowlist "
                "(B-4): must match ^[a-z0-9][a-z0-9._-]{0,62}$ "
                "with no '..' substring"
            ),
        }

    entry = name_to_entry.get(name)
    if entry is None:
        return {
            "success": False,
            "error": f"skill {name!r} not found on this server",
        }

    try:
        raw_body = body_loader(name)
    except FileNotFoundError as exc:
        return {"success": False, "error": str(exc)}
    body = _strip_body(raw_body)

    try:
        unsigned = _build_unsigned_metadata(
            entry,
            server_key=server_key,
            body=body,
        )
    except ValueError as exc:
        # Pydantic ValidationError raises ValueError; a bad
        # catalog entry surfaces here with a clear error.
        return {"success": False, "error": f"metadata validation failed: {exc}"}

    try:
        signed = sign(unsigned)
    except Exception as exc:  # noqa: BLE001  # the server's policy decides what to raise
        return {
            "success": False,
            "error": f"signing failed: {exc!r}",
        }

    if not isinstance(signed, SkillCanonicalSchema):
        return {
            "success": False,
            "error": "sign() must return a SkillCanonicalSchema",
        }

    return {
        "success": True,
        "metadata": signed.model_dump(mode="json"),
        "body": body,
    }


def build_register_skills_tools(
    *,
    server_key: str,
    catalog: Sequence[CatalogEntry],
    body_loader: Callable[[str], str],
    sign: Callable[[SkillCanonicalSchema], SkillCanonicalSchema],
    on_call: Callable[[], None] | None = None,
    tool_name_prefix: str = "",
) -> Callable[[Any], None]:
    """Build a ``register(app)`` closure for the given server's skill catalog.

    Parameters
    ----------
    server_key : str
        Canonical key (``"akosha"``, ``"mahavishnu"``, ``"crackerjack"``,
        ``"session-buddy"``, ``"oneiric"``). Must match the B-4
        allowlist ``^[a-z0-9][a-z0-9._-]{0,62}$``.
    catalog : sequence of Mapping
        One entry per skill. Required: ``name``, ``body_filename``.
        Recommended: ``version`` (default ``"0.0.0"``), ``description``,
        ``tool_refs``, ``dependencies``, ``allowed_tools``,
        ``content_type`` (default ``"skill"``), ``body_format``
        (default ``"yaml-frontmatter+markdown"``), ``owner``, ``tags``.
        The ``body_filename`` entry is consumed by the factory's
        body_loader wiring — the factory itself doesn't read files,
        it calls ``body_loader(entry["name"])`` which the server
        implements in terms of its own catalog layout.
    body_loader : callable
        ``name -> body_string``. Called at request time to fetch the
        skill body. The factory strips and hashes the returned body
        (B-6). Crackerjack / akosha / session-buddy / oneiric each
        implement this as ``read_file(catalog[name]["body_filename"])``.
    sign : callable
        ``unsigned_metadata -> signed_metadata``. The server's policy:
        acquire its signer (lifespan / singleton / future-dynamic),
        canonicalize the payload using its local
        ``canonical_payload_for_signing``, call ``signer.sign(...)``,
        and return a copy of the metadata with ``signature`` and
        ``server_pubkey_id`` populated. The factory treats this as
        opaque; it only checks that the returned object is still a
        :class:`SkillCanonicalSchema`.
    on_call : callable, optional
        Invoked at the start of every ``list_skills`` and
        ``get_skill`` call. The B-7 contract — bump
        ``SignerFeedState.cycles_total`` so the four mandatory feed
        signals stay accurate.
    tool_name_prefix : str
        Prefix for the registered tool names. Default empty
        (``"list_skills"`` and ``"get_skill"``). Other servers pass
        ``"mahavishnu_"``, ``"crackerjack_"``, etc. to match their
        existing wire names.

    Returns
    -------
    register : callable
        A function ``register(app: FastMCP) -> None`` that registers
        the two tools.

    Raises
    ------
    ValueError
        At factory construction time if ``server_key`` fails the B-4
        allowlist, if any catalog entry has a missing/invalid
        ``name``, if duplicate names appear, or if a catalog entry
        lacks a ``body_filename`` (the factory treats body_filename
        as advisory metadata, but warns the user if missing).
    """
    _validate_server_key(server_key)
    name_to_entry = _validate_skill_catalog(catalog)

    list_tool_name = f"{tool_name_prefix}list_skills"
    get_tool_name = f"{tool_name_prefix}get_skill"

    def register(app: Any) -> None:
        """Register ``list_skills`` + ``get_skill`` on the given FastMCP app."""

        @app.tool(name=list_tool_name)
        async def list_skills() -> list[dict[str, Any]]:
            return await _list_skills_impl(
                server_key=server_key,
                name_to_entry=name_to_entry,
                body_loader=body_loader,
                list_tool_name=list_tool_name,
                on_call=on_call,
            )

        @app.tool(name=get_tool_name)
        async def get_skill(name: str) -> dict[str, Any]:
            return await _get_skill_impl(
                name,
                server_key=server_key,
                name_to_entry=name_to_entry,
                body_loader=body_loader,
                sign=sign,
                on_call=on_call,
            )

    return register


__all__ = ["build_register_skills_tools"]
