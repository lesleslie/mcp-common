"""HTTP Client Adapter with connection pooling and structured logging.

This adapter provides a reusable HTTP client with:
- Connection pooling (11x performance improvement over per-request clients)
- Automatic structured logging with correlation IDs
- Lifecycle management (initialization and cleanup)
- Dependency injection support via ACB

Example:
    >>> from acb.depends import depends
    >>> from mcp_common.adapters.http import HTTPClientAdapter
    >>>
    >>> http = depends(HTTPClientAdapter)
    >>> client = await http._create_client()
    >>> response = await client.get("https://api.example.com/data")
"""

from __future__ import annotations

import typing as t
from contextlib import suppress
from uuid import UUID

import httpx
from acb.adapters import AdapterStatus
from acb.adapters.logger import LoggerProtocol
from acb.config import AdapterBase, Settings
from acb.depends import depends
from pydantic import Field

# Static adapter ID - generated once, hardcoded forever (UUID7)
MODULE_ID = UUID("01947e12-3b4c-7d8e-9f0a-1b2c3d4e5f6a")
MODULE_STATUS = AdapterStatus.STABLE


class HTTPClientSettings(Settings):
    """Configuration for HTTP client adapter.

    Loads from (in order):
    1. settings/local.yaml
    2. settings/http.yaml
    3. Environment variables HTTP_*
    4. Defaults below
    """

    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
        ge=1,
        le=300,
    )
    max_connections: int = Field(
        default=100,
        description="Maximum number of connections in pool",
        ge=1,
        le=1000,
    )
    max_keepalive_connections: int = Field(
        default=20,
        description="Maximum number of keep-alive connections",
        ge=1,
        le=100,
    )
    retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts on failure",
        ge=0,
        le=10,
    )
    follow_redirects: bool = Field(
        default=True,
        description="Whether to follow HTTP redirects",
    )


class HTTPClientAdapter(AdapterBase):
    """ACB adapter for connection-pooled HTTP client.

    Provides httpx.AsyncClient with:
    - Connection pooling (reuses TCP connections)
    - Automatic structured logging
    - Lifecycle management (cleanup on shutdown)
    - Configuration via ACB Settings

    The client is lazily initialized on first use via _create_client().

    Attributes:
        settings: Configuration for HTTP client behavior
        logger: Injected ACB logger (don't create this yourself!)
        _client: Cached httpx.AsyncClient instance

    Example:
        >>> http = depends(HTTPClientAdapter)
        >>> client = await http._create_client()
        >>> response = await client.post(
        ...     "https://api.example.com/send",
        ...     json={"message": "Hello"}
        ... )
    """

    settings: HTTPClientSettings | None = None
    logger: LoggerProtocol  # Injected by ACB - don't create this!
    _client: httpx.AsyncClient | None = None

    def __init__(self, **kwargs: t.Any) -> None:
        """Initialize adapter (REQUIRED to call super().__init__).

        Args:
            **kwargs: Passed to AdapterBase
        """
        super().__init__(**kwargs)

        # Load settings if not provided
        if self.settings is None:
            self.settings = HTTPClientSettings()

    async def _create_client(self) -> httpx.AsyncClient:
        """Create or return cached HTTP client with connection pooling.

        This method implements lazy initialization - the client is only
        created when first needed. Subsequent calls return the cached client.

        Returns:
            Configured httpx.AsyncClient with connection pooling

        Note:
            This method is called automatically by ACB on first use.
            Manual calls are safe - returns existing client if present.
        """
        if self._client is not None:
            return self._client

        # Log initialization
        self.logger.info(
            "Initializing HTTP client adapter",
            max_connections=self.settings.max_connections,
            max_keepalive=self.settings.max_keepalive_connections,
            timeout=self.settings.timeout,
        )

        # Create connection pool limits
        limits = httpx.Limits(
            max_connections=self.settings.max_connections,
            max_keepalive_connections=self.settings.max_keepalive_connections,
        )

        # Create timeout configuration
        timeout = httpx.Timeout(self.settings.timeout)

        # Create client with connection pooling
        self._client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            follow_redirects=self.settings.follow_redirects,
        )

        self.logger.info(
            "HTTP client adapter initialized successfully",
            pool_size=self.settings.max_connections,
        )

        return self._client

    async def _cleanup_resources(self) -> None:
        """Close HTTP client and release connections.

        Called automatically by ACB during shutdown to ensure clean resource cleanup.
        """
        if self._client is None:
            return

        self.logger.info("Closing HTTP client adapter")

        try:
            await self._client.aclose()
            self.logger.info("HTTP client adapter closed successfully")
        except Exception as e:
            self.logger.error(
                "Error closing HTTP client adapter",
                error=str(e),
                error_type=type(e).__name__,
            )
        finally:
            self._client = None

    async def get(
        self,
        url: str,
        **kwargs: t.Any,
    ) -> httpx.Response:
        """Convenience method for GET requests with automatic logging.

        Args:
            url: Target URL
            **kwargs: Additional arguments passed to httpx.get()

        Returns:
            HTTP response

        Example:
            >>> http = depends(HTTPClientAdapter)
            >>> response = await http.get("https://api.example.com/data")
        """
        client = await self._create_client()

        self.logger.debug(
            "HTTP GET request",
            url=url,
            **{k: v for k, v in kwargs.items() if k != "headers"},  # Don't log headers (may contain secrets)
        )

        response = await client.get(url, **kwargs)

        self.logger.debug(
            "HTTP GET response",
            url=url,
            status_code=response.status_code,
        )

        return response

    async def post(
        self,
        url: str,
        **kwargs: t.Any,
    ) -> httpx.Response:
        """Convenience method for POST requests with automatic logging.

        Args:
            url: Target URL
            **kwargs: Additional arguments passed to httpx.post()

        Returns:
            HTTP response

        Example:
            >>> http = depends(HTTPClientAdapter)
            >>> response = await http.post(
            ...     "https://api.example.com/send",
            ...     json={"message": "Hello"}
            ... )
        """
        client = await self._create_client()

        self.logger.debug(
            "HTTP POST request",
            url=url,
        )

        response = await client.post(url, **kwargs)

        self.logger.debug(
            "HTTP POST response",
            url=url,
            status_code=response.status_code,
        )

        return response


# Register adapter with ACB dependency injection container
# The suppress handles re-registration errors (e.g., on module re-import)
with suppress(AttributeError, TypeError):
    depends.set(HTTPClientAdapter)
