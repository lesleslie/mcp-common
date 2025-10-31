# Middleware Layer

## Focus
`mcp_common.middleware` packages reusable policies that sit between incoming requests and business logic. For now it centers on rate limiting profiles shared across MCP servers.

## Rate Limiting
- `RateLimitProfile` enumerates standard throughput tiers (conservative, moderate, aggressive).
- `RateLimitConfig` stores the numeric limits and validation logic.
- `PROFILES` supplies ready-made configurations, while `SERVER_CONFIGS` captures tuned values for known servers.

Use `get_config_for_server("crackerjack")` to retrieve a preconfigured profile or derive your own `RateLimitConfig` when wiring middleware in FastMCP tools.
