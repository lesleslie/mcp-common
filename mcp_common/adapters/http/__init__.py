"""HTTP Client adapter for MCP servers.

Provides connection-pooled HTTP client with structured logging and lifecycle management.
"""

from __future__ import annotations

from .client import HTTPClientAdapter, HTTPClientSettings

__all__ = ["HTTPClientAdapter", "HTTPClientSettings"]
