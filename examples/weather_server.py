#!/usr/bin/env python3
"""Example ACB-native MCP server using mcp-common foundation library.

This weather API server demonstrates:
- HTTPClientAdapter for connection pooling (11x performance improvement)
- MCPBaseSettings for YAML + environment variable configuration
- ServerPanels for beautiful Rich UI output
- ACB dependency injection and lifecycle management
- FastMCP for MCP protocol implementation

Run this example:
    python examples/weather_server.py

Or via uvx:
    uvx --from mcp-common weather-server
"""

from __future__ import annotations

import asyncio
import typing as t

from acb.depends import depends
from fastmcp import FastMCP

from mcp_common import HTTPClientAdapter, HTTPClientSettings, MCPBaseSettings, ServerPanels

# Initialize FastMCP server
mcp = FastMCP("Weather MCP Server")


class WeatherSettings(MCPBaseSettings):
    """Weather API server settings with YAML + env var support.

    Configuration loading order (later overrides earlier):
    1. Default values (below)
    2. settings/local.yaml (gitignored, for development)
    3. settings/weather.yaml (committed, for production)
    4. Environment variables: WEATHER_API_KEY, WEATHER_BASE_URL, etc.
    """

    server_name: str = "Weather MCP"
    server_description: str = "Real-time weather data via OpenWeatherMap API"

    # API Configuration
    api_key: str = "demo"  # Override via WEATHER_API_KEY environment variable
    base_url: str = "https://api.openweathermap.org/data/2.5"
    timeout: int = 10
    max_retries: int = 3

    # HTTP Client Settings
    http_max_connections: int = 50
    http_max_keepalive: int = 10


@mcp.tool()
async def get_current_weather(city: str, units: str = "metric") -> dict[str, t.Any]:
    """Get current weather for a city.

    Args:
        city: City name (e.g., "London", "New York")
        units: Temperature units - "metric" (Celsius) or "imperial" (Fahrenheit)

    Returns:
        Weather data including temperature, description, humidity, wind speed

    Example:
        >>> await get_current_weather("London")
        {"temp": 15.2, "description": "cloudy", "humidity": 72, ...}
    """
    # Get configuration from DI container
    settings = depends.get_sync(WeatherSettings)

    # Get HTTP client adapter from DI container (connection pooling!)
    http_adapter = depends.get_sync(HTTPClientAdapter)

    try:
        # Make API request using connection-pooled client
        response = await http_adapter.get(
            f"{settings.base_url}/weather",
            params={
                "q": city,
                "units": units,
                "appid": settings.api_key,
            },
        )

        data = response.json()

        # Return clean weather data
        return {
            "city": data["name"],
            "country": data["sys"]["country"],
            "temperature": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "description": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "units": units,
        }

    except Exception as e:
        # Show error using ServerPanels
        ServerPanels.error(
            title="Weather API Error",
            message=f"Failed to fetch weather for {city}",
            suggestion=f"Check API key and city name. Error: {e}",
            error_type=type(e).__name__,
        )
        raise


@mcp.tool()
async def get_forecast(city: str, days: int = 3, units: str = "metric") -> list[dict[str, t.Any]]:
    """Get weather forecast for a city.

    Args:
        city: City name
        days: Number of days to forecast (1-5)
        units: Temperature units - "metric" or "imperial"

    Returns:
        List of daily forecasts
    """
    settings = depends.get_sync(WeatherSettings)
    http_adapter = depends.get_sync(HTTPClientAdapter)

    if not 1 <= days <= 5:
        ServerPanels.warning(
            title="Invalid Parameter",
            message=f"Days must be between 1 and 5, got {days}",
            details=["Using maximum of 5 days"],
        )
        days = min(5, max(1, days))

    try:
        response = await http_adapter.get(
            f"{settings.base_url}/forecast",
            params={
                "q": city,
                "units": units,
                "appid": settings.api_key,
                "cnt": days * 8,  # 8 forecasts per day (3-hour intervals)
            },
        )

        data = response.json()
        forecasts = []

        # Group by day and take midday forecast
        for i in range(0, min(len(data["list"]), days * 8), 8):
            forecast = data["list"][i]
            forecasts.append(
                {
                    "date": forecast["dt_txt"].split()[0],
                    "temperature": forecast["main"]["temp"],
                    "description": forecast["weather"][0]["description"],
                    "humidity": forecast["main"]["humidity"],
                }
            )

        return forecasts

    except Exception as e:
        ServerPanels.error(
            title="Forecast API Error",
            message=f"Failed to fetch forecast for {city}",
            suggestion=f"Error: {e}",
            error_type=type(e).__name__,
        )
        raise


async def main() -> None:
    """Main server initialization and startup."""
    # Initialize settings
    settings = WeatherSettings()

    # Display startup panel
    ServerPanels.startup_success(
        server_name=settings.server_name,
        version="2.0.0",
        features=[
            "Current weather by city",
            "5-day weather forecast",
            "Multiple temperature units",
            "Connection pooling (11x faster)",
        ],
        api_provider="OpenWeatherMap",
        http_pooling=f"{settings.http_max_connections} connections",
    )

    # Configure HTTP client adapter with settings
    http_settings = HTTPClientSettings(
        timeout=settings.timeout,
        max_connections=settings.http_max_connections,
        max_keepalive_connections=settings.http_max_keepalive,
        retry_attempts=settings.max_retries,
    )

    # Register adapters in DI container
    http_adapter = HTTPClientAdapter(settings=http_settings)
    depends.set(http_adapter)
    depends.set(settings)

    # Show server status
    ServerPanels.status_table(
        title="Server Status",
        rows=[
            ("HTTP Client", "✅ Ready", f"Pool: {settings.http_max_connections} connections"),
            ("Configuration", "✅ Loaded", f"API: {settings.base_url}"),
            ("MCP Tools", "✅ Registered", "2 tools available"),
        ],
    )

    # Show available tools
    ServerPanels.feature_list(
        server_name=settings.server_name,
        features={
            "get_current_weather": "Get real-time weather data for any city",
            "get_forecast": "Get 1-5 day weather forecast with 3-hour intervals",
        },
    )

    ServerPanels.separator()
    ServerPanels.simple_message(
        "Server ready! Use MCP tools to fetch weather data.",
        style="green bold",
    )

    # Run the FastMCP server
    try:
        await mcp.run()
    finally:
        # Cleanup: Close HTTP client connections
        await http_adapter._cleanup_resources()
        ServerPanels.simple_message("Server shutdown complete", style="yellow")


if __name__ == "__main__":
    asyncio.run(main())
