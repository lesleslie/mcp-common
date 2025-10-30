# RFC: Phases 4-10 Technical Specifications

**RFC Date**: 2025-10-28
**Author**: MCP Development Team
**Status**: DRAFT
**Related**: Phase 3.3 M6 - Planning for future architectural improvements

---

## Executive Summary

This RFC provides detailed technical specifications for Phases 4-10 of the MCP ecosystem evolution. Based on the Phase 3 Architecture Review recommendations, this document establishes clear priorities, success criteria, and implementation patterns for each phase.

### Priority Matrix

| Phase | Name | Priority | Status | Rationale |
|-------|------|----------|--------|-----------|
| **Phase 10** | Production Hardening | **HIGH** | Ready for implementation | Critical for production readiness |
| **Phase 7** | Documentation & DX | **HIGH** | Needs detailed roadmap | Essential for maintainability |
| **Phase 6** | Enhanced Observability | **MEDIUM** | Needs stack selection | Foundation for monitoring |
| **Phase 8** | Performance Optimization | **MEDIUM** | Needs baseline metrics | Requires Phase 6 data |
| **Phase 4** | Advanced Settings Migration | **LOW** | Defer until proven need | May conflict with P2 deferral |
| **Phase 9** | Advanced Features | **LOW** | Defer (YAGNI) | Speculative, no proven need |
| **Phase 5** | HTTPClientAdapter Migration | **CANCELLED** | Archive | Conflicts with SDK best practices |

---

## Phase 10: Production Hardening (HIGH PRIORITY)

### Objective

Ensure all MCP servers are production-ready with robust health checks, graceful shutdowns, error recovery, and container orchestration support.

### Technical Specification

#### 10.1 Health Check Endpoints

**Pattern**: FastMCP `/health` endpoint with component checks

```python
# mcp_common/health.py
from dataclasses import dataclass
from enum import Enum
import typing as t


class HealthStatus(Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status for individual component."""
    name: str
    status: HealthStatus
    message: str | None = None
    latency_ms: float | None = None


@dataclass
class HealthCheckResponse:
    """Comprehensive health check response."""
    status: HealthStatus
    timestamp: str
    version: str
    components: list[ComponentHealth]
    uptime_seconds: float
```

**Implementation Per Server Type**:

1. **External API Servers** (mailgun, unifi, raindropio, opera-cloud, session-mgmt):
   - Check external API connectivity (with timeout)
   - Validate API credentials still work
   - Check rate limit headroom
   - Measure API response latency

2. **Local Framework Servers** (acb, crackerjack):
   - Check file system access
   - Validate required tools available
   - Check Python environment health

3. **Database Servers** (session-mgmt with DuckDB):
   - Check database connectivity
   - Validate schema migrations
   - Check disk space availability

**Success Criteria**:
- All servers expose `/health` endpoint
- Health checks complete in <100ms
- Failures don't crash the server
- Includes component-level detail

#### 10.2 Graceful Shutdown

**Pattern**: Signal handling with cleanup sequence

```python
# mcp_common/lifecycle.py
import signal
import asyncio
import typing as t
from contextlib import asynccontextmanager


class GracefulShutdownHandler:
    """Handles graceful shutdown with cleanup tasks."""

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds
        self.cleanup_tasks: list[t.Callable[[], t.Awaitable[None]]] = []
        self.shutting_down = False

    def register_cleanup(self, task: t.Callable[[], t.Awaitable[None]]) -> None:
        """Register async cleanup task to run on shutdown."""
        self.cleanup_tasks.append(task)

    async def shutdown(self) -> None:
        """Execute all cleanup tasks with timeout."""
        if self.shutting_down:
            return

        self.shutting_down = True

        try:
            async with asyncio.timeout(self.timeout_seconds):
                for task in self.cleanup_tasks:
                    await task()
        except asyncio.TimeoutError:
            print(f"⚠️ Graceful shutdown timed out after {self.timeout_seconds}s")
```

**Cleanup Sequence**:
1. Stop accepting new requests (30s grace period)
2. Complete in-flight requests
3. Flush pending writes (database, logs)
4. Close external API connections
5. Release file handles and resources
6. Log final shutdown message

**Success Criteria**:
- Zero data loss on shutdown
- In-flight requests complete successfully
- All resources properly released
- Clean container termination

#### 10.3 Circuit Breaker Pattern

**Pattern**: Automatic failure detection and recovery

```python
# mcp_common/resilience/circuit_breaker.py
from enum import Enum
from dataclasses import dataclass
import time


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Failures before opening
    timeout_seconds: int = 60  # Time before attempting recovery
    success_threshold: int = 2  # Successes before fully closing


class CircuitBreaker:
    """Circuit breaker for external API calls."""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None

    async def call(self, func: t.Callable[[], t.Awaitable[T]]) -> T:
        """Execute function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

**Integration Points**:
- External API calls (mailgun, unifi, raindropio, opera-cloud)
- Database operations (session-mgmt)
- File system operations (all servers)

**Success Criteria**:
- Automatic failure detection
- Self-healing after timeout
- Metrics for circuit breaker events
- Configurable per endpoint

#### 10.4 Container Orchestration Support

**Docker Health Check** (all servers):
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -m mcp_server.health_check || exit 1
```

**Kubernetes Readiness/Liveness Probes**:
```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: mcp-server
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 30
    readinessProbe:
      httpGet:
        path: /health?ready=true
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 10
```

**Success Criteria**:
- Docker health checks work out of the box
- Kubernetes probes supported
- Container restarts are clean
- Zero-downtime deployments possible

---

## Phase 7: Documentation & Developer Experience (HIGH PRIORITY)

### Objective

Create comprehensive documentation and improve developer experience to reduce onboarding time and maintenance burden.

### Technical Specification

#### 7.1 Documentation Roadmap

**Core Documentation**:

1. **Architecture Guide** (`docs/ARCHITECTURE.md`)
   - Server patterns (External API, Local Framework, Database)
   - Dependency injection with ACB
   - Settings management patterns
   - Security patterns
   - Rate limiting patterns

2. **API Reference** (`docs/API_REFERENCE.md`)
   - `mcp_common.adapters.HTTPClientAdapter`
   - `mcp_common.config.MCPBaseSettings`
   - `mcp_common.config.ValidationMixin`
   - `mcp_common.security.api_keys`
   - `mcp_common.exceptions` hierarchy

3. **Migration Guides** (`docs/migrations/`)
   - Migrating to mcp-common
   - Adding rate limiting
   - Implementing custom exceptions
   - Using ValidationMixin

4. **Plugin/Extension Pattern** (`docs/PLUGIN_PATTERN.md`)
   - FastBlocks inheritance pattern
   - Creating custom MCP servers
   - Extending mcp-common

**Per-Server Documentation**:
- README.md with quick start
- Configuration examples
- Tool usage examples
- Troubleshooting guide

**Success Criteria**:
- New developer can create MCP server in <30 minutes
- Common questions answered in docs
- Zero unanswered Stack Overflow questions
- 90%+ documentation coverage

#### 7.2 Developer Experience Improvements

**DX Metrics**:
- Time to first successful server run
- Number of configuration errors
- Test execution time
- Documentation search time

**Improvements**:

1. **Better Error Messages**:
```python
# Instead of:
raise ValueError("Invalid configuration")

# Do:
raise ServerConfigurationError(
    message="Mailgun API key is required but not set. "
            "Set MAILGUN_API_KEY environment variable or add to config.yaml",
    field="api_key",
)
```

2. **Configuration Validation at Init**:
```python
class Settings(MCPBaseSettings, ValidationMixin):
    api_key: str

    def model_post_init(self, __context: t.Any) -> None:
        """Validate configuration after initialization."""
        self.validate_required_field("api_key", self.api_key)
```

3. **Template Generation**:
```bash
# New command for creating servers
mcp-common init my-server --type=external-api
```

**Success Criteria**:
- 50% reduction in configuration errors
- Clear error messages for all failures
- Template generation works
- IDE autocomplete support

---

## Phase 6: Enhanced Observability (MEDIUM PRIORITY)

### Objective

Implement comprehensive observability with metrics, logging, and distributed tracing for production monitoring.

### Technical Specification

#### 6.1 Observability Stack Selection

**Recommended Stack**:

| Component | Tool | Rationale |
|-----------|------|-----------|
| **Metrics** | Prometheus + OpenTelemetry | Industry standard, Python support excellent |
| **Logging** | Structured JSON logs | ELK/Loki compatible, searchable |
| **Tracing** | OpenTelemetry | Vendor-neutral, future-proof |
| **Dashboards** | Grafana | Free, powerful, Prometheus integration |

**Alternative** (Serverless/Cloud):
- AWS CloudWatch
- Google Cloud Operations
- Datadog (commercial)

#### 6.2 Metrics Implementation

**Core Metrics** (all servers):
```python
# mcp_common/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge


# Request metrics
http_requests_total = Counter(
    "mcp_http_requests_total",
    "Total HTTP requests",
    ["server", "method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "mcp_http_request_duration_seconds",
    "HTTP request duration",
    ["server", "method", "endpoint"],
)

# External API metrics
external_api_calls_total = Counter(
    "mcp_external_api_calls_total",
    "Total external API calls",
    ["server", "provider", "operation", "status"],
)

external_api_duration_seconds = Histogram(
    "mcp_external_api_duration_seconds",
    "External API call duration",
    ["server", "provider", "operation"],
)

# Rate limiting metrics
rate_limit_rejections_total = Counter(
    "mcp_rate_limit_rejections_total",
    "Total rate limit rejections",
    ["server"],
)

rate_limit_tokens_available = Gauge(
    "mcp_rate_limit_tokens_available",
    "Available rate limit tokens",
    ["server"],
)

# Health metrics
health_check_duration_seconds = Histogram(
    "mcp_health_check_duration_seconds",
    "Health check duration",
    ["server", "component"],
)

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    "mcp_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half-open, 2=open)",
    ["server", "endpoint"],
)
```

**Server-Specific Metrics**:

1. **mailgun-mcp**:
   - `mailgun_emails_sent_total`
   - `mailgun_email_send_duration_seconds`
   - `mailgun_api_errors_total`

2. **session-mgmt-mcp**:
   - `session_active_sessions_total`
   - `reflection_database_size_bytes`
   - `reflection_search_duration_seconds`

3. **acb/crackerjack**:
   - `component_execution_duration_seconds`
   - `quality_check_results_total`

**Success Criteria**:
- All servers expose `/metrics` endpoint
- Key business metrics tracked
- Grafana dashboards available
- Alerts configured

#### 6.3 Structured Logging

**Pattern**: JSON-structured logs with context

```python
# mcp_common/observability/logging.py
import logging
import json
from contextvars import ContextVar


# Request context
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


class StructuredLogger:
    """Structured JSON logger with context."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def log(
        self,
        level: int,
        message: str,
        **extra: t.Any,
    ) -> None:
        """Log with structured context."""
        log_entry = {
            "message": message,
            "timestamp": time.time(),
            "level": logging.getLevelName(level),
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
            **extra,
        }

        self.logger.log(level, json.dumps(log_entry))
```

**Log Levels**:
- **DEBUG**: Detailed diagnostic information
- **INFO**: General operational events
- **WARNING**: Recoverable errors, degraded performance
- **ERROR**: Operation failures
- **CRITICAL**: System-wide failures

**Success Criteria**:
- All logs structured JSON
- Context propagates through call chain
- Searchable in log aggregator
- Sensitive data masked

#### 6.4 Distributed Tracing

**Pattern**: OpenTelemetry with automatic instrumentation

```python
# mcp_common/observability/tracing.py
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


def setup_tracing(app: FastMCP, service_name: str) -> None:
    """Setup OpenTelemetry tracing."""
    # Configure tracer provider
    tracer_provider = TracerProvider()
    trace.set_tracer_provider(tracer_provider)

    # Auto-instrument FastMCP
    FastAPIInstrumentor.instrument_app(app)

    # Auto-instrument httpx (for HTTPClientAdapter)
    HTTPXClientInstrumentor().instrument()
```

**Trace Points**:
- HTTP requests (automatic)
- External API calls (automatic via httpx)
- Database operations (manual spans)
- Business operations (manual spans)

**Success Criteria**:
- End-to-end request tracing
- External API calls traced
- Performance bottlenecks visible
- Works with Jaeger/Zipkin

---

## Phase 8: Performance Optimization (MEDIUM PRIORITY)

### Objective

Establish performance baselines and optimize based on production metrics from Phase 6.

### Prerequisites

**Must Complete First**:
- Phase 6 (metrics collection)
- Phase 10.1 (health checks for baseline)

### Technical Specification

#### 8.1 Performance Baseline Establishment

**Benchmarking Framework**: pytest-benchmark

```python
# tests/benchmark/test_api_performance.py
import pytest


@pytest.mark.benchmark(group="api-calls")
def test_external_api_call_performance(benchmark, mailgun_client):
    """Baseline: Mailgun API call should complete in <500ms."""
    result = benchmark(mailgun_client.send_email, ...)
    assert result.stats.mean < 0.5  # 500ms
```

**Baseline Metrics Per Server**:

| Server | Operation | P50 Target | P95 Target | P99 Target |
|--------|-----------|------------|------------|------------|
| mailgun-mcp | send_email | 200ms | 500ms | 1000ms |
| unifi-mcp | get_devices | 100ms | 300ms | 600ms |
| session-mgmt-mcp | search_reflections | 50ms | 150ms | 300ms |
| acb | component_execution | 10ms | 50ms | 100ms |

**Success Criteria**:
- Baselines documented
- Regression tests prevent degradation
- Load testing framework in place

#### 8.2 Optimization Strategies

**Only Optimize If**:
1. Metrics show degradation
2. User complaints about performance
3. SLO violations

**Common Optimizations**:

1. **Connection Pooling** (already done via HTTPClientAdapter)
2. **Caching** (add if metrics show repeated identical requests)
3. **Async Optimization** (profile for blocking calls)
4. **Database Indexing** (add for slow queries)

**Anti-Patterns to Avoid**:
- Premature optimization
- Over-caching
- Complex async patterns without profiling

**Success Criteria**:
- No performance regressions
- SLOs met 99.9% of time
- Optimization ROI documented

---

## Phase 4: Advanced MCPBaseSettings Migration (LOW PRIORITY)

### Status: DEFERRED

**Rationale**: Phase P2 analysis recommended deferring complex base class patterns. Current pattern works well.

**Reconsider If**:
- Multiple servers need identical settings patterns
- Configuration validation becomes repetitive across 5+ servers
- ACB settings evolution requires it

**Success Criteria for Future Consideration**:
- Clear pain point documented
- Benefits quantified
- Migration path non-disruptive

---

## Phase 9: Advanced Features (LOW PRIORITY)

### Status: DEFERRED (YAGNI)

**Features Under Consideration**:
1. Multi-tenancy support
2. Advanced caching strategies
3. Request/response transformation

**Reconsider If**:
- User demand proven (3+ requests)
- Clear use cases documented
- Cost-benefit analysis favorable

**Success Criteria for Future Consideration**:
- User stories written
- Technical design approved
- No simpler solution exists

---

## Phase 5: HTTPClientAdapter Migration (CANCELLED)

### Status: ARCHIVED

**Decision**: Do NOT migrate OpenAI/Gemini SDKs to HTTPClientAdapter

**Rationale**:
- Official SDKs provide better abstraction
- SDKs handle auth, retries, rate limits internally
- httpx connection pooling already used by SDKs
- Migration provides zero performance benefit
- Breaks SDK updates and bug fixes

**Documentation**: Add to `docs/ARCHITECTURE.md` explaining why some servers don't use HTTPClientAdapter

**Success Criteria**:
- Decision documented
- Phase 5 removed from roadmap
- No future attempts to "complete" this phase

---

## Implementation Roadmap

### Immediate (Next 2 Weeks)
1. ✅ Phase 3.3 M1-M6 completion
2. 🎯 Phase 10.1: Health check endpoints
3. 🎯 Phase 7.1: Core documentation

### Short Term (1-2 Months)
1. Phase 10.2: Graceful shutdown
2. Phase 7.2: DX improvements
3. Phase 6.1: Observability stack setup

### Medium Term (3-6 Months)
1. Phase 6.2-6.4: Full observability rollout
2. Phase 10.3: Circuit breaker implementation
3. Phase 8.1: Performance baseline establishment

### Long Term (6+ Months)
1. Phase 8.2: Optimization based on metrics
2. Phase 10.4: Container orchestration hardening
3. Phase 4/9: Reconsider if proven need emerges

---

## Success Metrics

### Phase 10 (Production Hardening)
- 100% health check coverage
- Zero unclean shutdowns
- Circuit breaker prevents cascading failures
- 99.9% uptime in production

### Phase 7 (Documentation & DX)
- Developer onboarding time <30 minutes
- Zero unanswered documentation questions
- 90%+ doc coverage
- Positive developer feedback

### Phase 6 (Observability)
- All critical metrics tracked
- Dashboards provide actionable insights
- Incidents detected in <1 minute
- MTTR reduced by 50%

### Phase 8 (Performance)
- SLOs met 99.9% of time
- No performance regressions
- Optimization ROI >3x investment

---

## References

- Phase 3 Architecture Review
- INTEGRATION_TRACKING.md
- PHASE3_CONSOLIDATED_REVIEW.md
- OpenTelemetry Documentation
- Prometheus Best Practices
- Kubernetes Health Checks Guide
