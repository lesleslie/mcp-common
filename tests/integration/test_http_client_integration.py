"""Integration tests for HTTPClientAdapter (Oneiric re-export).

Tests that mcp-common correctly re-exports Oneiric's HTTPClientAdapter
and that it works as expected for basic HTTP operations.
"""

import pytest
from oneiric.adapters.http import HTTPClientAdapter as OneiricHTTPClientAdapter
from oneiric.adapters.http import HTTPClientSettings as OneiricHTTPClientSettings


class TestHTTPClientAdapterReExport:
    """Test that HTTPClientAdapter is correctly re-exported from Oneiric."""

    def test_http_client_adapter_import(self):
        """Test HTTPClientAdapter can be imported from mcp_common."""
        from mcp_common import HTTPClientAdapter

        # Should be the same as Oneiric's adapter
        assert HTTPClientAdapter is OneiricHTTPClientAdapter
        assert HTTPClientAdapter.__name__ == "HTTPClientAdapter"

    def test_http_client_settings_import(self):
        """Test HTTPClientSettings can be imported from mcp_common."""
        from mcp_common import HTTPClientSettings

        # Should be the same as Oneiric's settings
        assert HTTPClientSettings is OneiricHTTPClientSettings
        assert HTTPClientSettings.__name__ == "HTTPClientSettings"

    def test_http_client_settings_instantiation(self):
        """Test HTTPClientSettings can be instantiated with Oneiric's parameters."""
        from mcp_common import HTTPClientSettings

        # Test with minimal parameters
        settings = HTTPClientSettings(timeout=10.0)
        assert settings.timeout == 10.0
        assert settings.verify is True  # Default value

        # Test with all parameters
        settings = HTTPClientSettings(
            timeout=30.0,
            verify=False,
            headers={"User-Agent": "test"},
            healthcheck_path="/health",
        )
        assert settings.timeout == 30.0
        assert settings.verify is False
        assert settings.headers == {"User-Agent": "test"}
        assert settings.healthcheck_path == "/health"

    @pytest.mark.asyncio
    async def test_http_client_adapter_lifecycle(self):
        """Test HTTPClientAdapter lifecycle (init/cleanup)."""
        from mcp_common import HTTPClientAdapter, HTTPClientSettings

        settings = HTTPClientSettings(timeout=10.0)
        adapter = HTTPClientAdapter(settings=settings)

        # Test init
        await adapter.init()
        assert adapter._client is not None

        # Test cleanup
        await adapter.cleanup()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_http_client_adapter_health(self):
        """Test HTTPClientAdapter health check."""
        from mcp_common import HTTPClientAdapter, HTTPClientSettings

        settings = HTTPClientSettings(timeout=10.0)
        adapter = HTTPClientAdapter(settings=settings)

        # Health should return True when no base_url is configured
        await adapter.init()
        health = await adapter.health()
        assert health is True

        await adapter.cleanup()

    def test_http_client_adapter_metadata(self):
        """Test HTTPClientAdapter has Oneiric's metadata."""
        from mcp_common import HTTPClientAdapter

        # Oneiric's adapter has a metadata attribute
        assert hasattr(HTTPClientAdapter, "metadata")
        assert HTTPClientAdapter.metadata.category == "http"
        assert HTTPClientAdapter.metadata.provider == "httpx"


class TestHTTPClientAdapterBasicUsage:
    """Test basic HTTP client adapter usage patterns."""

    @pytest.mark.asyncio
    async def test_simple_get_request(self):
        """Test simple GET request using httpbin (public HTTP test API)."""
        from mcp_common import HTTPClientAdapter, HTTPClientSettings

        settings = HTTPClientSettings(
            timeout=10.0,
            base_url="https://httpbin.org",
        )
        adapter = HTTPClientAdapter(settings=settings)

        await adapter.init()

        try:
            # Make a simple GET request
            response = await adapter.get("/get")

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "url" in data
        finally:
            await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test concurrent requests using connection pooling."""
        import asyncio

        from mcp_common import HTTPClientAdapter, HTTPClientSettings

        settings = HTTPClientSettings(
            timeout=10.0,
            base_url="https://httpbin.org",
        )
        adapter = HTTPClientAdapter(settings=settings)

        await adapter.init()

        async def make_request(path):
            response = await adapter.get(path)
            return response.status_code

        try:
            # Make 5 concurrent requests
            tasks = [make_request("/get") for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert all(r == 200 for r in results)
        finally:
            await adapter.cleanup()
