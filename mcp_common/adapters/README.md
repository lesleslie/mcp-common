# Adapters Layer

## Scope
This layer hosts lifecycle-aware components that surface infrastructure capabilities through ACB's adapter system. Each adapter extends `acb.config.AdapterBase`, defines a stable UUID, and exposes async helpers that DI consumers call via `depends(...)`.

## Available Adapters
- `HTTPClientAdapter` — Connection-pooled `httpx.AsyncClient` with structured logging.
- `HTTPClientSettings` — Pydantic settings object backing the adapter configuration.

## Extending
To add a new adapter, mirror the structure in `http/client.py`, export the class from `adapters/__init__.py`, and wire it into `mcp_common/__init__.py` so DI clients can import it directly. Keep heavy configuration defaults in the companion settings class and log initialization details through the injected ACB logger.
