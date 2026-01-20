"""OpenTelemetry integration for observability.

This module provides:
1. Distributed tracing for controller operations
2. Metrics for performance and cost monitoring
3. Structured logging integration
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar

# Try to import OpenTelemetry - it's optional
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore

# Try to import Prometheus client - it's optional
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TelemetryConfig:
    """Configuration for telemetry/observability."""
    
    enabled: bool = False
    
    # Tracing
    enable_tracing: bool = True
    trace_exporter: str = "console"  # console, otlp, jaeger
    otlp_endpoint: Optional[str] = None
    service_name: str = "rfsn-controller"
    
    # Metrics
    enable_metrics: bool = True
    metrics_port: int = 8080
    
    # Logging
    enable_structured_logging: bool = True


_config: TelemetryConfig = TelemetryConfig()
_tracer: Optional[Any] = None


def configure_telemetry(config: TelemetryConfig) -> None:
    """Configure telemetry with the given settings."""
    global _config, _tracer
    _config = config
    
    if not config.enabled:
        return
    
    if OTEL_AVAILABLE and config.enable_tracing:
        provider = TracerProvider()
        
        if config.trace_exporter == "console":
            processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
        
        # Add OTLP exporter if configured
        if config.trace_exporter == "otlp" and config.otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )
                otlp_exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            except ImportError:
                pass
        
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(config.service_name)
    
    if PROMETHEUS_AVAILABLE and config.enable_metrics:
        try:
            start_http_server(config.metrics_port)
        except Exception:
            pass  # Port might already be in use


def get_tracer():
    """Get the configured tracer, or a no-op tracer."""
    global _tracer
    if _tracer is None and OTEL_AVAILABLE:
        _tracer = trace.get_tracer("rfsn-controller")
    return _tracer


# ============================================================================
# METRICS (Prometheus-style)
# ============================================================================

if PROMETHEUS_AVAILABLE:
    # Counters
    PATCHES_EVALUATED = Counter(
        "rfsn_patches_evaluated_total",
        "Total number of patches evaluated",
        ["status", "model"],
    )
    
    LLM_CALLS = Counter(
        "rfsn_llm_calls_total",
        "Total number of LLM API calls",
        ["model", "status"],
    )
    
    LLM_TOKENS = Counter(
        "rfsn_llm_tokens_total",
        "Total LLM tokens used",
        ["model", "type"],  # labels: model name and token type (prompt or completion)
    )
    
    COMMANDS_EXECUTED = Counter(
        "rfsn_commands_executed_total",
        "Total commands executed in sandbox",
        ["command", "status"],
    )
    
    # Histograms
    PATCH_EVAL_DURATION = Histogram(
        "rfsn_patch_eval_seconds",
        "Patch evaluation duration in seconds",
        buckets=[1, 5, 10, 30, 60, 120, 300],
    )
    
    LLM_LATENCY = Histogram(
        "rfsn_llm_latency_seconds",
        "LLM API latency in seconds",
        ["model"],
        buckets=[0.5, 1, 2, 5, 10, 30],
    )
    
    TEST_DURATION = Histogram(
        "rfsn_test_duration_seconds",
        "Test execution duration in seconds",
        buckets=[1, 5, 10, 30, 60, 120, 300],
    )
    
    # Gauges
    ACTIVE_SANDBOXES = Gauge(
        "rfsn_active_sandboxes",
        "Number of active sandboxes",
    )
    
    CURRENT_STEP = Gauge(
        "rfsn_current_step",
        "Current controller step",
        ["run_id"],
    )

else:
    # No-op metrics when Prometheus not available
    class NoOpMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass
        def dec(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass
        def observe(self, *args, **kwargs):
            pass
        def time(self):
            return _no_op_context()
    
    @contextmanager
    def _no_op_context():
        yield
    
    PATCHES_EVALUATED = NoOpMetric()
    LLM_CALLS = NoOpMetric()
    LLM_TOKENS = NoOpMetric()
    COMMANDS_EXECUTED = NoOpMetric()
    PATCH_EVAL_DURATION = NoOpMetric()
    LLM_LATENCY = NoOpMetric()
    TEST_DURATION = NoOpMetric()
    ACTIVE_SANDBOXES = NoOpMetric()
    CURRENT_STEP = NoOpMetric()


# ============================================================================
# TRACING DECORATORS AND CONTEXT MANAGERS
# ============================================================================

T = TypeVar("T")


@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> Generator[Optional[Any], None, None]:
    """Create a trace span for an operation.
    
    Args:
        name: Name of the span.
        attributes: Optional attributes to add to the span.
        
    Yields:
        The span object (or None if tracing disabled).
    """
    tracer = get_tracer()
    
    if tracer is None or not _config.enabled:
        yield None
        return
    
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def traced(name: Optional[str] = None):
    """Decorator to trace a function.
    
    Args:
        name: Optional span name (defaults to function name).
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        span_name = name or func.__name__
        
        def wrapper(*args, **kwargs) -> T:
            with trace_span(span_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# STRUCTURED EVENT LOGGING
# ============================================================================

@dataclass
class TelemetryEvent:
    """A structured telemetry event."""
    
    name: str
    timestamp: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    status: str = "ok"
    error: Optional[str] = None


_event_buffer: List[TelemetryEvent] = []
_event_callbacks: List[Callable[[TelemetryEvent], None]] = []


def emit_event(event: TelemetryEvent) -> None:
    """Emit a telemetry event.
    
    Args:
        event: The event to emit.
    """
    _event_buffer.append(event)
    
    # Call registered callbacks
    for callback in _event_callbacks:
        try:
            callback(event)
        except Exception:
            pass
    
    # Also add to current span if tracing
    tracer = get_tracer()
    if tracer and _config.enabled:
        current_span = trace.get_current_span() if trace else None
        if current_span:
            current_span.add_event(
                event.name,
                attributes=event.attributes,
            )


def register_event_callback(callback: Callable[[TelemetryEvent], None]) -> None:
    """Register a callback for telemetry events.
    
    Args:
        callback: Function to call for each event.
    """
    _event_callbacks.append(callback)


def get_events(limit: int = 100) -> List[TelemetryEvent]:
    """Get recent telemetry events.
    
    Args:
        limit: Maximum number of events to return.
        
    Returns:
        List of recent events.
    """
    return _event_buffer[-limit:]


# ============================================================================
# CONVENIENCE FUNCTIONS FOR CONTROLLER
# ============================================================================

def track_patch_evaluation(
    diff: str,
    model: str,
    status: str,
    duration_sec: float,
) -> None:
    """Track a patch evaluation.
    
    Args:
        diff: The patch diff.
        model: Model that generated the patch.
        status: Result status (pass, fail, error).
        duration_sec: Evaluation duration.
    """
    PATCHES_EVALUATED.labels(status=status, model=model).inc()
    PATCH_EVAL_DURATION.observe(duration_sec)
    
    emit_event(TelemetryEvent(
        name="patch_evaluation",
        attributes={
            "model": model,
            "status": status,
            "diff_lines": diff.count("\n"),
        },
        duration_ms=duration_sec * 1000,
        status=status,
    ))


def track_llm_call(
    model: str,
    status: str,
    latency_sec: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Track an LLM API call.
    
    Args:
        model: Model name.
        status: Result status (success, error).
        latency_sec: API latency.
        prompt_tokens: Number of prompt tokens.
        completion_tokens: Number of completion tokens.
    """
    LLM_CALLS.labels(model=model, status=status).inc()
    LLM_LATENCY.labels(model=model).observe(latency_sec)
    
    if prompt_tokens:
        LLM_TOKENS.labels(model=model, type="prompt").inc(prompt_tokens)
    if completion_tokens:
        LLM_TOKENS.labels(model=model, type="completion").inc(completion_tokens)
    
    emit_event(TelemetryEvent(
        name="llm_call",
        attributes={
            "model": model,
            "status": status,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
        duration_ms=latency_sec * 1000,
        status=status,
    ))


def track_command_execution(
    command: str,
    status: str,
    duration_sec: float,
) -> None:
    """Track a sandbox command execution.
    
    Args:
        command: The command executed (first word only for privacy).
        status: Result status (success, fail, timeout).
        duration_sec: Execution duration.
    """
    cmd_base = command.split()[0] if command else "unknown"
    COMMANDS_EXECUTED.labels(command=cmd_base, status=status).inc()
    
    emit_event(TelemetryEvent(
        name="command_execution",
        attributes={
            "command": cmd_base,
            "status": status,
        },
        duration_ms=duration_sec * 1000,
        status=status,
    ))


def track_test_run(
    test_cmd: str,
    status: str,
    duration_sec: float,
    tests_passed: int = 0,
    tests_failed: int = 0,
) -> None:
    """Track a test run.
    
    Args:
        test_cmd: Test command.
        status: Result status (pass, fail, error).
        duration_sec: Test duration.
        tests_passed: Number of passing tests.
        tests_failed: Number of failing tests.
    """
    TEST_DURATION.observe(duration_sec)
    
    emit_event(TelemetryEvent(
        name="test_run",
        attributes={
            "command": test_cmd.split()[0] if test_cmd else "unknown",
            "status": status,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
        },
        duration_ms=duration_sec * 1000,
        status=status,
    ))


# ============================================================================
# INITIALIZATION HELPER
# ============================================================================

def init_telemetry(
    enabled: bool = False,
    enable_tracing: bool = True,
    enable_metrics: bool = True,
    metrics_port: int = 8080,
    otlp_endpoint: Optional[str] = None,
) -> None:
    """Initialize telemetry with common settings.
    
    Args:
        enabled: Whether to enable telemetry.
        enable_tracing: Whether to enable distributed tracing.
        enable_metrics: Whether to enable Prometheus metrics.
        metrics_port: Port for Prometheus metrics server.
        otlp_endpoint: OTLP collector endpoint for traces.
    """
    config = TelemetryConfig(
        enabled=enabled,
        enable_tracing=enable_tracing,
        enable_metrics=enable_metrics,
        metrics_port=metrics_port,
        trace_exporter="otlp" if otlp_endpoint else "console",
        otlp_endpoint=otlp_endpoint,
    )
    configure_telemetry(config)
