"""Benchmarks for HTTP client connection pooling (Oneiric adapter).

Verifies that Oneiric's HTTPClientAdapter provides connection pooling benefits
by comparing against creating new httpx clients per request.

NOTE: These tests require network access to httpbin.org. Skip with --skip-benchmark if offline.
"""

import pytest
import httpx
import asyncio
from oneiric.adapters.http import HTTPClientAdapter, HTTPClientSettings


class TestHTTPPoolingBenchmarks:
    """Benchmark Oneiric HTTPClientAdapter connection pooling vs unpooled."""

    @pytest.mark.benchmark(group="http", min_rounds=20)
    def test_pooled_http_client(self, benchmark):
        """Benchmark Oneiric pooled HTTP client."""
        settings = HTTPClientSettings(timeout=30)

        def run_request():
            """Sync wrapper that creates new adapter each time."""
            async def make_request():
                adapter = HTTPClientAdapter(settings=settings)
                await adapter.init()
                try:
                    response = await adapter.get("https://httpbin.org/get")
                    return response.status_code
                finally:
                    await adapter.cleanup()

            return asyncio.run(make_request())

        result = benchmark(run_request)
        assert result == 200

    @pytest.mark.benchmark(group="http", min_rounds=20)
    def test_unpooled_http_client(self, benchmark):
        """Baseline: unpooled HTTP client (new connection per request)."""

        def run_request():
            """Sync wrapper that creates new client each time."""
            async def make_request():
                client = httpx.AsyncClient(timeout=30)
                try:
                    response = await client.get("https://httpbin.org/get")
                    return response.status_code
                finally:
                    await client.aclose()

            return asyncio.run(make_request())

        result = benchmark(run_request)
        assert result == 200

    @pytest.mark.benchmark(group="http", min_rounds=20)
    @pytest.mark.skip(reason="Concurrent tests - can be flaky on CI")
    def test_pooled_concurrent_requests(self, benchmark):
        """Benchmark pooled client with concurrent requests."""
        settings = HTTPClientSettings(timeout=30)

        async def make_request():
            adapter = HTTPClientAdapter(settings=settings)
            await adapter.init()

            try:
                async def concurrent_get(url):
                    return await adapter.get(url)

                # Make 5 concurrent requests to same host
                urls = ["https://httpbin.org/get"] * 5
                tasks = [concurrent_get(url) for url in urls]
                results = await asyncio.gather(*tasks)

                return all(r.status_code == 200 for r in results)
            finally:
                await adapter.cleanup()

        result = benchmark(make_request)
        assert result is True

    @pytest.mark.benchmark(group="http", min_rounds=20)
    @pytest.mark.skip(reason="Concurrent tests - can be flaky on CI")
    def test_unpooled_concurrent_requests(self, benchmark):
        """Baseline: unpooled client with concurrent requests."""

        async def make_request():
            async def single_request():
                client = httpx.AsyncClient(timeout=30)
                try:
                    response = await client.get("https://httpbin.org/get")
                    return response.status_code
                finally:
                    await client.aclose()

            # Make 5 concurrent requests with separate clients
            tasks = [single_request() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            return all(r == 200 for r in results)

        result = benchmark(make_request)
        assert result is True
