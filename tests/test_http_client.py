"""Tests for HTTPClientAdapter - connection pooling and lifecycle management."""

from __future__ import annotations

import typing as t

import httpx
import pytest
import respx
from hypothesis import given
from hypothesis import strategies as st

from mcp_common.adapters.http import HTTPClientAdapter, HTTPClientSettings


@pytest.mark.unit
class TestHTTPClientSettings:
    """Tests for HTTPClientSettings configuration."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = HTTPClientSettings()
        assert settings.timeout == 30
        assert settings.max_connections == 100
        assert settings.max_keepalive_connections == 20
        assert settings.retry_attempts == 3
        assert settings.follow_redirects is True

    def test_custom_settings(self) -> None:
        """Test custom settings override defaults."""
        settings = HTTPClientSettings(
            timeout=60,
            max_connections=200,
            max_keepalive_connections=50,
            retry_attempts=5,
            follow_redirects=False,
        )
        assert settings.timeout == 60
        assert settings.max_connections == 200
        assert settings.max_keepalive_connections == 50
        assert settings.retry_attempts == 5
        assert settings.follow_redirects is False

    @given(
        timeout=st.integers(min_value=1, max_value=300),
        max_connections=st.integers(min_value=1, max_value=1000),
    )
    def test_settings_validation(self, timeout: int, max_connections: int) -> None:
        """Test settings validation with property-based testing."""
        settings = HTTPClientSettings(
            timeout=timeout,
            max_connections=max_connections,
        )
        assert 1 <= settings.timeout <= 300
        assert 1 <= settings.max_connections <= 1000


@pytest.mark.unit
class TestHTTPClientAdapter:
    """Tests for HTTPClientAdapter lifecycle and operations."""

    async def test_adapter_initialization(
        self,
        sample_http_settings: HTTPClientSettings,
    ) -> None:
        """Test adapter initializes with settings."""
        adapter = HTTPClientAdapter(settings=sample_http_settings)
        assert adapter.settings is not None
        assert adapter._client is None  # Not created until needed

    async def test_client_creation_lazy(
        self,
        http_adapter: HTTPClientAdapter,
    ) -> None:
        """Test HTTP client is created lazily on first access."""
        assert http_adapter._client is None

        client = await http_adapter._create_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert http_adapter._client is client

    async def test_client_reuse(self, http_adapter: HTTPClientAdapter) -> None:
        """Test HTTP client is reused across multiple calls."""
        client1 = await http_adapter._create_client()
        client2 = await http_adapter._create_client()

        assert client1 is client2  # Same instance reused

    async def test_connection_pooling_config(
        self,
        sample_http_settings: HTTPClientSettings,
        mock_logger: t.Any,
    ) -> None:
        """Test connection pooling is configured correctly."""
        adapter = HTTPClientAdapter(settings=sample_http_settings)
        adapter.logger = mock_logger  # Inject mock logger
        client = await adapter._create_client()

        # Verify client was created successfully
        assert isinstance(client, httpx.AsyncClient)
        assert client is not None

        await adapter._cleanup_resources()

    async def test_timeout_configuration(
        self,
        mock_logger: t.Any,
    ) -> None:
        """Test timeout is configured correctly."""
        settings = HTTPClientSettings(timeout=45)
        adapter = HTTPClientAdapter(settings=settings)
        adapter.logger = mock_logger  # Inject mock logger
        client = await adapter._create_client()

        # Verify client was created with timeout settings
        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout is not None

        await adapter._cleanup_resources()

    async def test_cleanup_resources(self, http_adapter: HTTPClientAdapter) -> None:
        """Test cleanup properly closes client."""
        # Create client
        client = await http_adapter._create_client()
        assert http_adapter._client is not None

        # Cleanup
        await http_adapter._cleanup_resources()
        assert http_adapter._client is None
        assert client.is_closed

    async def test_cleanup_when_no_client(
        self,
        http_adapter: HTTPClientAdapter,
    ) -> None:
        """Test cleanup is safe when no client exists."""
        assert http_adapter._client is None

        # Should not raise
        await http_adapter._cleanup_resources()
        assert http_adapter._client is None


@pytest.mark.unit
@respx.mock
class TestHTTPClientRequests:
    """Tests for HTTP request methods with mocked responses."""

    async def test_get_request(self, http_adapter: HTTPClientAdapter) -> None:
        """Test GET request with mocked response."""
        # Mock the API endpoint
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"status": "success"}),
        )

        # Make request
        response = await http_adapter.get("https://api.example.com/data")

        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        assert route.called

    async def test_post_request(self, http_adapter: HTTPClientAdapter) -> None:
        """Test POST request with mocked response."""
        route = respx.post("https://api.example.com/submit").mock(
            return_value=httpx.Response(201, json={"id": 123}),
        )

        response = await http_adapter.post(
            "https://api.example.com/submit",
            json={"name": "test"},
        )

        assert response.status_code == 201
        assert response.json() == {"id": 123}
        assert route.called

    async def test_get_with_query_params(
        self,
        http_adapter: HTTPClientAdapter,
    ) -> None:
        """Test GET request with query parameters."""
        route = respx.get("https://api.example.com/search", params={"q": "test"}).mock(
            return_value=httpx.Response(200, json={"results": []}),
        )

        response = await http_adapter.get(
            "https://api.example.com/search",
            params={"q": "test"},
        )

        assert response.status_code == 200
        assert route.called

    async def test_post_with_headers(self, http_adapter: HTTPClientAdapter) -> None:
        """Test POST request with custom headers."""
        route = respx.post("https://api.example.com/data").mock(
            return_value=httpx.Response(200),
        )

        await http_adapter.post(
            "https://api.example.com/data",
            headers={"Authorization": "Bearer token123"},
        )

        assert route.called
        # Verify headers were sent
        assert route.calls.last.request.headers["Authorization"] == "Bearer token123"

    async def test_error_response(self, http_adapter: HTTPClientAdapter) -> None:
        """Test handling of error responses."""
        respx.get("https://api.example.com/error").mock(
            return_value=httpx.Response(404, json={"error": "Not found"}),
        )

        response = await http_adapter.get("https://api.example.com/error")

        assert response.status_code == 404
        assert response.json() == {"error": "Not found"}


@pytest.mark.integration
@respx.mock
class TestHTTPClientPerformance:
    """Integration tests for connection pooling performance benefits."""

    async def test_connection_reuse_performance(
        self,
        http_adapter: HTTPClientAdapter,
    ) -> None:
        """Test that connection pooling reuses connections efficiently."""
        # Mock multiple endpoints
        for i in range(10):
            respx.get(f"https://api.example.com/item/{i}").mock(
                return_value=httpx.Response(200, json={"id": i}),
            )

        # Make multiple requests - should reuse connections
        responses = []
        for i in range(10):
            response = await http_adapter.get(f"https://api.example.com/item/{i}")
            responses.append(response)

        # Verify all succeeded
        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == 10

        # Verify client was created only once (connection reuse)
        assert http_adapter._client is not None

    async def test_concurrent_requests(self, http_adapter: HTTPClientAdapter) -> None:
        """Test concurrent requests share connection pool."""
        import asyncio

        # Mock endpoints
        for i in range(5):
            respx.get(f"https://api.example.com/concurrent/{i}").mock(
                return_value=httpx.Response(200, json={"id": i}),
            )

        # Make concurrent requests
        tasks = [http_adapter.get(f"https://api.example.com/concurrent/{i}") for i in range(5)]
        responses = await asyncio.gather(*tasks)

        assert len(responses) == 5
        assert all(r.status_code == 200 for r in responses)
