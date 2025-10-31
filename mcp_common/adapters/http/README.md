# HTTP Adapter

## Overview
`HTTPClientAdapter` centralizes outbound HTTP access with connection pooling, retry-friendly defaults, and structured logging. Settings are provided by `HTTPClientSettings`, which load from YAML and environment variables using ACB's configuration pipeline.

## Usage

```python
from acb.depends import depends
from mcp_common.adapters.http import HTTPClientAdapter

http = depends(HTTPClientAdapter)
client = await http._create_client()
response = await client.get("https://api.example.com/status")
```

Lifecycle hooks close the underlying client during shutdown, and helper methods such as `.get()` and `.post()` wrap standard `httpx.AsyncClient` calls with logging. Adjust timeouts, pool sizes, and redirect behavior via settings files (`settings/http.yaml`) or environment variables (`HTTP_TIMEOUT`, etc.).
