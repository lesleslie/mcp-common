"""Factory for the Phase 3 list_agents + get_agent MCP tool pair.

Per ``docs/plans/2026-09-09-bodai-skill-agent-distribution.md`` Phase 3 +
Phase 4 §11, every Bodai MCP server publishes agents via two tools:
``<server>_list_agents`` and ``<server>_get_agent``. The wire shape, the
B-4 path-traversal allowlist, the body normalization + content-hash
(B-6), and the registration plumbing are shared concerns — this
factory owns them so each server only writes its own catalog and its
own signing policy.

Mechanism vs. policy
--------------------

The factory owns the **mechanism**: catalog validation at startup, the
allowlist check at the API boundary, body stripping + SHA-256 hashing,
the tool registration shape, the success/error envelope, and the
``list`` + ``get`` tool pair. Each server owns the **policy**: catalog
content, where bodies live (file vs synthesized), how the signer is
acquired (lifespan vs singleton vs future-dynamic), and the tool name
prefix (``""`` for akosha's wire name ``list_agents``,
``"mahavishnu_"`` for the prefix convention used by the other four).

Usage
-----

::

    from mcp_common.agents_tools import build_register_agents_tools
    from mcp_common.canonical_schemas.agent import AgentCanonicalSchema

    # Server-specific catalog
    catalog = [
        {"name": "akosha-specialist", "description": "...",
         "model": "opus", "tools": [...], ...},
        ...
    ]

    # Server-specific body source
    def body_loader(name: str) -> str:
        return Path(f"agents/{name}.md").read_text()

    # Server-specific signing policy (opaque to the factory)
    def sign(metadata: AgentCanonicalSchema) -> AgentCanonicalSchema:
        signer = get_signer_feed_state().signer
        payload = canonical_payload_for_signing(metadata.model_dump(mode="json"))
        signed = signer.sign(payload)
        return metadata.model_copy(update={
            "signature": signed.signature_b64,
            "server_pubkey_id": signed.key_id,
        })

    # Server-specific cycle bump (B-7)
    def on_call() -> None:
        get_signer_feed_state().record_cycle()

    register = build_register_agents_tools(
        server_key="akosha",
        catalog=catalog,
        body_loader=body_loader,
        sign=sign,
        on_call=on_call,
        # tool_name_prefix="" matches akosha's existing wire name
        # "list_agents"; mahavishnu and crackerjack pass
        # "mahavishnu_" / "crackerjack_" to match theirs.
    )

    def setup_server(app: FastMCP) -> None:
        register(app)  # registers list_agents + get_agent

The catalog entry shape
----------------------

A catalog entry is a Mapping whose values populate
:class:`AgentCanonicalSchema` fields. Required: ``name``,
``description``. Recommended: ``model`` (default ``"sonnet"``),
``version`` (default ``"0.0.0"``), ``tools`` (default ``[]``),
``title``, ``category``, ``owner``, ``status`` (default ``"active"``),
``last_reviewed``, ``scope`` (default ``"user-global"``).
``system_prompt`` is optional — if absent (or empty), the factory
calls ``body_loader(name)`` at request time. This split lets the
server keep the catalog in code while bodies live as files (the
common case) OR keep both inline (a smaller catalog) OR synthesize
bodies on the fly from runtime state (oneiric's per-domain
specialists).

B-4 allowlist
-------------

The B-4 regex ``^[a-z0-9][a-z0-9._-]{0,62}$`` lives in
``mcp_common.canonical_schemas._validators`` and is the single source
of truth across all 5 servers. The factory uses it for both
eager-time catalog validation and per-call API-boundary enforcement,
so the per-server ``_NAME_ALLOWLIST_RE`` constants in the old
``agents_tools.py`` modules can be deleted.

B-6 body integrity
------------------

``content_hash`` is the lowercase hex SHA-256 of the **stripped**
``system_prompt`` bytes. The factory strips the body once (B-6's
invariance: the hash matches the system_prompt exactly), then
``model_copy(update={"signature": ..., "server_pubkey_id": ...})``
preserves the stripped body across signing. The
``get_agent`` response returns the same stripped body under
``"body"`` so the installer writes a fully-functional agent file
(Phase 3 B-6 critical contract).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from mcp_common.canonical_schemas._validators import allowlisted_name
from mcp_common.canonical_schemas.agent import AgentCanonicalSchema

logger = logging.getLogger(__name__)


# A catalog entry is a Mapping whose keys are AgentCanonicalSchema field
# names and whose values are JSON-safe. ``system_prompt`` is the only
# optional-with-special-handling field — if absent, the factory calls
# body_loader(name) to fetch the body at request time.
CatalogEntry = Mapping[str, Any]


def _strip_body(body: str) -> str:
    """Normalize a body for B-6 hash consistency.

    Strips leading/trailing whitespace. Internal whitespace is preserved.
    A body read from disk often has surrounding whitespace from
    frontmatter delimiters or the trailing newline the Write tool
    often drops — strip those so the content_hash is over the
    content-pure bytes. The schema's AgentCanonicalSchema does NOT
    set ``str_strip_whitespace`` on system_prompt (so the hash is
    over the exact body bytes); the factory is the single place
    that owns the strip, and the schema's
    ``_validate_body_integrity`` (B-6) confirms equality after
    construction.
    """
    return body.strip()


def _content_hash(body: str) -> str:
    """B-6 content_hash: lowercase hex SHA-256 of the (stripped) body bytes."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _build_unsigned_metadata(
    entry: CatalogEntry,
    *,
    server_key: str,
    body_loader: Callable[[str], str],
) -> AgentCanonicalSchema:
    """Build the unsigned :class:`AgentCanonicalSchema` for one catalog entry.

    Body is loaded via ``body_loader(name)`` if not provided inline in
    the entry. The content hash is computed from the stripped body.
    The Pydantic validators (B-4 allowlist on name/server_key, B-6
    body-integrity hash assertion) run on construction; a bad
    catalog entry fails fast at request time.
    """
    name = entry["name"]
    inline_body = entry.get("system_prompt")
    if isinstance(inline_body, str) and inline_body:
        raw_body = inline_body
    else:
        raw_body = body_loader(name)
    body = _strip_body(raw_body)
    version = entry.get("version", "0.0.0")
    return AgentCanonicalSchema(
        id=f"{server_key}:{name}:{version}",
        server_key=server_key,
        name=name,
        title=entry.get("title"),
        description=entry.get("description", ""),
        version=version,
        model=entry.get("model", "sonnet"),
        tools=list(entry.get("tools", [])),
        system_prompt=body,
        dependencies=list(entry.get("dependencies", [])),
        tool_refs=list(entry.get("tool_refs", [])),
        category=entry.get("category"),
        owner=entry.get("owner"),
        status=entry.get("status", "active"),
        last_reviewed=entry.get("last_reviewed"),
        scope=entry.get("scope", "user-global"),
        content_hash=_content_hash(body),
        schema_version=entry.get("schema_version", 1),
    )


def _validate_server_key(server_key: str) -> None:
    """Raise ``ValueError`` if ``server_key`` fails the B-4 allowlist."""
    if not allowlisted_name(server_key):
        raise ValueError(
            f"server_key {server_key!r} violates B-4 allowlist "
            r"'^[a-z0-9][a-z0-9._-]{0,62}$' "
            "(forbidden: '/', uppercase, leading '.', length > 63)"
        )


def _validate_agent_catalog(catalog: Sequence[CatalogEntry]) -> dict[str, CatalogEntry]:
    """Eagerly validate the agent catalog, returning ``name -> entry``.

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
        if name in name_to_entry:
            raise ValueError(f"duplicate catalog entry name: {name!r}")
        name_to_entry[name] = entry
    return name_to_entry


async def _list_agents_impl(
    *,
    server_key: str,
    name_to_entry: dict[str, CatalogEntry],
    body_loader: Callable[[str], str],
    on_call: Callable[[], None] | None,
) -> list[dict[str, Any]]:
    """Body of the ``list_agents`` tool (B-6 + B-7 contract).

    Per Phase 3 §11 B-6: ``system_prompt`` IS populated so the
    picker can preview the body without a second ``get_agent``
    round-trip. The ``signature`` and ``server_pubkey_id`` fields
    are ``None`` here — they are filled by ``get_agent`` since the
    signature is over the canonical payload WITHOUT the signing
    fields themselves.

    Per B-7: ``on_call`` is invoked to bump ``cycles_total`` so
    the four mandatory feed signals stay accurate.
    """
    if on_call is not None:
        on_call()
    result: list[dict[str, Any]] = []
    for entry in name_to_entry.values():
        metadata = _build_unsigned_metadata(
            entry,
            server_key=server_key,
            body_loader=body_loader,
        )
        result.append(metadata.model_dump(mode="json"))
    return result


async def _get_agent_impl(
    name: str,
    *,
    server_key: str,
    name_to_entry: dict[str, CatalogEntry],
    body_loader: Callable[[str], str],
    sign: Callable[[AgentCanonicalSchema], AgentCanonicalSchema],
    on_call: Callable[[], None] | None,
) -> dict[str, Any]:
    """Body of the ``get_agent`` tool.

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

    The body returned in the success case is the
    ``system_prompt`` from the signed metadata — guaranteed
    equal to the B-6 content_hash input (the schema's
    body-integrity model_validator asserts this on
    construction).
    """
    if on_call is not None:
        on_call()

    # B-4: enforce the allowlist at the API boundary, before
    # constructing the metadata. Uniform error envelope
    # shape across all four rejection modes.
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
            "error": f"agent {name!r} not found on this server",
        }

    try:
        unsigned = _build_unsigned_metadata(
            entry,
            server_key=server_key,
            body_loader=body_loader,
        )
    except FileNotFoundError as exc:
        return {"success": False, "error": str(exc)}
    except ValueError as exc:
        # Pydantic ValidationError raises ValueError too
        # (the field_validators raise ValueError); a bad
        # catalog entry surfaces here with a clear error.
        return {"success": False, "error": f"metadata validation failed: {exc}"}

    try:
        signed = sign(unsigned)
    except Exception as exc:  # noqa: BLE001  # the server's policy decides what to raise
        return {
            "success": False,
            "error": f"signing failed: {exc!r}",
        }

    if not isinstance(signed, AgentCanonicalSchema):
        return {
            "success": False,
            "error": "sign() must return an AgentCanonicalSchema",
        }

    return {
        "success": True,
        "metadata": signed.model_dump(mode="json"),
        "body": signed.system_prompt,
    }


def build_register_agents_tools(
    *,
    server_key: str,
    catalog: Sequence[CatalogEntry],
    body_loader: Callable[[str], str],
    sign: Callable[[AgentCanonicalSchema], AgentCanonicalSchema],
    on_call: Callable[[], None] | None = None,
    tool_name_prefix: str = "",
) -> Callable[[Any], None]:
    """Build a ``register(app)`` closure for the given server's catalog.

    Parameters
    ----------
    server_key : str
        Canonical key (``"akosha"``, ``"mahavishnu"``, ``"crackerjack"``,
        ``"session-buddy"``, ``"oneiric"``). Must match the B-4
        allowlist ``^[a-z0-9][a-z0-9._-]{0,62}$``.
    catalog : sequence of Mapping
        One entry per agent. See module docstring for the field
        contract. Validated eagerly at factory construction time so
        config errors surface at import, not at first request.
    body_loader : callable
        ``name -> body_string``. Called at request time for catalog
        entries that don't provide ``system_prompt`` inline. The
        factory strips and hashes the returned body (B-6).
    sign : callable
        ``unsigned_metadata -> signed_metadata``. The server's policy:
        acquire its signer (lifespan / singleton / future-dynamic),
        canonicalize the payload using its local
        ``canonical_payload_for_signing``, call ``signer.sign(...)``,
        and return a copy of the metadata with ``signature`` and
        ``server_pubkey_id`` populated. The factory treats this as
        opaque; it only checks that the returned object is still an
        :class:`AgentCanonicalSchema`.
    on_call : callable, optional
        Invoked at the start of every ``list_agents`` and
        ``get_agent`` call. The B-7 contract — bump
        ``SignerFeedState.cycles_total`` so the four mandatory feed
        signals stay accurate. Servers wire this to their
        ``get_signer_feed_state().record_cycle``.
    tool_name_prefix : str
        Prefix for the registered tool names. Default empty
        (``"list_agents"`` and ``"get_agent"`` — matches akosha's
        existing wire name). Other servers pass
        ``"mahavishnu_"``, ``"crackerjack_"``, ``"session_buddy_"``,
        ``"oneiric_"`` to match their existing wire names.

    Returns
    -------
    register : callable
        A function ``register(app: FastMCP) -> None`` that registers
        the two tools. The server picks WHERE to call it (inline
        during lifespan setup, profile-gated via
        :func:`mcp_common.tools.dispatch._apply_tool_profile`, or
        dynamically after the registry has data). The factory does
        not care which.

    Raises
    ------
    ValueError
        At factory construction time if ``server_key`` fails the B-4
        allowlist, if any catalog entry has a missing/invalid
        ``name``, or if duplicate names appear in the catalog.
    """
    _validate_server_key(server_key)
    name_to_entry = _validate_agent_catalog(catalog)

    list_tool_name = f"{tool_name_prefix}list_agents"
    get_tool_name = f"{tool_name_prefix}get_agent"

    def register(app: Any) -> None:
        """Register ``list_agents`` + ``get_agent`` on the given FastMCP app."""

        @app.tool(name=list_tool_name)
        async def list_agents() -> list[dict[str, Any]]:
            return await _list_agents_impl(
                server_key=server_key,
                name_to_entry=name_to_entry,
                body_loader=body_loader,
                on_call=on_call,
            )

        @app.tool(name=get_tool_name)
        async def get_agent(name: str) -> dict[str, Any]:
            return await _get_agent_impl(
                name,
                server_key=server_key,
                name_to_entry=name_to_entry,
                body_loader=body_loader,
                sign=sign,
                on_call=on_call,
            )

    return register


__all__ = ["build_register_agents_tools"]
