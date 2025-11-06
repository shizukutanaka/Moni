"""
Observability Framework - Three Pillars Implementation
Integrates Structured Logging, Metrics, and Distributed Tracing

Modern observability architecture combining:
1. Structured Logging - Machine-readable event data
2. Metrics - Quantifiable measurements over time
3. Traces - Request flow through distributed systems

Replaces traditional reactive monitoring with proactive observability.
"""

from __future__ import annotations

import contextvars
import functools
import json
import logging
import threading
import time
import traceback
import uuid
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable, Union
import weakref

logger = logging.getLogger(__name__)


# ============================================================================
# Context Management
# ============================================================================

# Context variables for trace propagation
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'trace_id', default=None
)
span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'span_id', default=None
)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'user_id', default=None
)
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'request_id', default=None
)


# ============================================================================
# Enums
# ============================================================================

class LogLevel(Enum):
    """Log levels for structured logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SpanKind(Enum):
    """OpenTelemetry span kinds."""
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"  # Cumulative (only increases)
    GAUGE = "gauge"      # Current value
    HISTOGRAM = "histogram"  # Distribution
    SUMMARY = "summary"  # Distribution with quantiles


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class StructuredLogEntry:
    """Structured log entry with machine-readable fields."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    level: LogLevel = LogLevel.INFO
    message: str = ""
    logger_name: str = ""
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None

    # Structured fields
    fields: Dict[str, Any] = field(default_factory=dict)

    # Error information
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    exception_stacktrace: Optional[str] = None

    # Service context
    service_name: str = "moni"
    service_version: str = "1.0.0"
    hostname: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "logger_name": self.logger_name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "fields": self.fields,
            "exception": {
                "type": self.exception_type,
                "message": self.exception_message,
                "stacktrace": self.exception_stacktrace
            } if self.exception_type else None,
            "service": {
                "name": self.service_name,
                "version": self.service_version,
                "hostname": self.hostname
            }
        }


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    value: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Metric:
    """Metric with time series data."""
    name: str
    type: MetricType = MetricType.GAUGE
    unit: str = ""
    description: str = ""
    points: List[MetricPoint] = field(default_factory=list)

    def add_point(self, value: float, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add data point to metric."""
        point = MetricPoint(value=value, attributes=attributes or {})
        self.points.append(point)


@dataclass
class Span:
    """Distributed trace span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str = ""
    kind: SpanKind = SpanKind.INTERNAL
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None

    # Attributes for context
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Events within span
    events: List[Dict[str, Any]] = field(default_factory=list)

    # Status
    status: str = "OK"  # OK, ERROR
    error_message: Optional[str] = None

    def end(self) -> None:
        """End span recording."""
        self.end_time = datetime.now(timezone.utc)

    def duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        end = self.end_time or datetime.now(timezone.utc)
        delta = end - self.start_time
        return delta.total_seconds() * 1000

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add event to span."""
        event = {
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {}
        }
        self.events.append(event)


# ============================================================================
# Structured Logger
# ============================================================================

class StructuredLogger:
    """Structured logging with JSON output."""

    def __init__(self, name: str, output_file: Optional[Path] = None):
        """Initialize structured logger."""
        self.name = name
        self.output_file = output_file
        self.lock = threading.RLock()
        self.entries: List[StructuredLogEntry] = []

    def log(self, level: LogLevel, message: str, **fields) -> None:
        """Log structured message."""
        entry = StructuredLogEntry(
            level=level,
            message=message,
            logger_name=self.name,
            trace_id=trace_id_var.get(),
            span_id=span_id_var.get(),
            user_id=user_id_var.get(),
            request_id=request_id_var.get(),
            fields=fields
        )

        with self.lock:
            self.entries.append(entry)

            # Write to file if configured
            if self.output_file:
                with open(self.output_file, 'a') as f:
                    f.write(json.dumps(entry.to_dict()) + '\n')

    def debug(self, message: str, **fields) -> None:
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **fields)

    def info(self, message: str, **fields) -> None:
        """Log info message."""
        self.log(LogLevel.INFO, message, **fields)

    def warning(self, message: str, **fields) -> None:
        """Log warning message."""
        self.log(LogLevel.WARNING, message, **fields)

    def error(self, message: str, exception: Optional[Exception] = None, **fields) -> None:
        """Log error message with optional exception."""
        entry = StructuredLogEntry(
            level=LogLevel.ERROR,
            message=message,
            logger_name=self.name,
            trace_id=trace_id_var.get(),
            span_id=span_id_var.get(),
            user_id=user_id_var.get(),
            request_id=request_id_var.get(),
            fields=fields
        )

        if exception:
            entry.exception_type = type(exception).__name__
            entry.exception_message = str(exception)
            entry.exception_stacktrace = traceback.format_exc()

        with self.lock:
            self.entries.append(entry)

            if self.output_file:
                with open(self.output_file, 'a') as f:
                    f.write(json.dumps(entry.to_dict()) + '\n')

    def critical(self, message: str, **fields) -> None:
        """Log critical message."""
        self.log(LogLevel.CRITICAL, message, **fields)

    def get_entries(self) -> List[StructuredLogEntry]:
        """Get all log entries."""
        with self.lock:
            return list(self.entries)


# ============================================================================
# Metrics Collection
# ============================================================================

class MetricsCollector:
    """Collect and store metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, Metric] = {}
        self.lock = threading.RLock()

    def create_metric(self, name: str, type: MetricType = MetricType.GAUGE,
                     unit: str = "", description: str = "") -> Metric:
        """Create or get metric."""
        with self.lock:
            if name not in self.metrics:
                self.metrics[name] = Metric(
                    name=name,
                    type=type,
                    unit=unit,
                    description=description
                )
            return self.metrics[name]

    def record_counter(self, name: str, value: float = 1.0,
                      attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record counter metric (monotonically increasing)."""
        metric = self.create_metric(name, MetricType.COUNTER)
        metric.add_point(value, attributes)

    def record_gauge(self, name: str, value: float,
                    attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record gauge metric (current value)."""
        metric = self.create_metric(name, MetricType.GAUGE)
        metric.add_point(value, attributes)

    def record_histogram(self, name: str, value: float,
                        attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record histogram metric (distribution)."""
        metric = self.create_metric(name, MetricType.HISTOGRAM)
        metric.add_point(value, attributes)

    def get_metrics(self) -> Dict[str, Metric]:
        """Get all metrics."""
        with self.lock:
            return dict(self.metrics)

    def get_metric(self, name: str) -> Optional[Metric]:
        """Get specific metric."""
        with self.lock:
            return self.metrics.get(name)


# ============================================================================
# Distributed Tracing
# ============================================================================

class TracingContext:
    """Manage distributed tracing context."""

    def __init__(self):
        """Initialize tracing context."""
        self.spans: Dict[str, Span] = {}
        self.lock = threading.RLock()

    def start_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL,
                  attributes: Optional[Dict[str, Any]] = None) -> Span:
        """Start new span."""
        trace_id = trace_id_var.get() or str(uuid.uuid4())
        parent_span_id = span_id_var.get()
        span_id = str(uuid.uuid4())

        # Update context
        if not trace_id_var.get():
            trace_id_var.set(trace_id)
        span_id_var.set(span_id)

        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            attributes=attributes or {}
        )

        with self.lock:
            self.spans[span_id] = span

        return span

    def end_span(self, span: Span) -> None:
        """End span."""
        span.end()

    def get_span(self, span_id: str) -> Optional[Span]:
        """Get span by ID."""
        with self.lock:
            return self.spans.get(span_id)

    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans in trace."""
        with self.lock:
            return [s for s in self.spans.values() if s.trace_id == trace_id]

    def get_current_span(self) -> Optional[Span]:
        """Get current span from context."""
        span_id = span_id_var.get()
        if not span_id:
            return None
        return self.get_span(span_id)


# ============================================================================
# Decorators
# ============================================================================

def traced(name: Optional[str] = None, kind: SpanKind = SpanKind.INTERNAL) -> Callable:
    """Decorator for tracing function execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            span_name = name or func.__name__
            tracer = get_tracing_context()
            span = tracer.start_span(span_name, kind=kind)

            try:
                result = func(*args, **kwargs)
                span.status = "OK"
                return result
            except Exception as e:
                span.status = "ERROR"
                span.error_message = str(e)
                raise
            finally:
                tracer.end_span(span)

        return wrapper
    return decorator


def log_execution(message: str = None, log_args: bool = False) -> Callable:
    """Decorator for logging function execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            msg = message or f"Executing {func.__name__}"
            slogger = get_structured_logger(__name__)

            fields = {}
            if log_args:
                fields['args'] = str(args)
                fields['kwargs'] = str(kwargs)

            slogger.info(msg, **fields)

            try:
                result = func(*args, **kwargs)
                slogger.info(f"Completed {func.__name__}")
                return result
            except Exception as e:
                slogger.error(f"Failed {func.__name__}", exception=e)
                raise

        return wrapper
    return decorator


# ============================================================================
# Singletons
# ============================================================================

_structured_logger: Dict[str, StructuredLogger] = {}
_metrics_collector: Optional[MetricsCollector] = None
_tracing_context: Optional[TracingContext] = None


def get_structured_logger(name: str) -> StructuredLogger:
    """Get or create structured logger."""
    if name not in _structured_logger:
        _structured_logger[name] = StructuredLogger(name)
    return _structured_logger[name]


def get_metrics_collector() -> MetricsCollector:
    """Get or create metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_tracing_context() -> TracingContext:
    """Get or create tracing context."""
    global _tracing_context
    if _tracing_context is None:
        _tracing_context = TracingContext()
    return _tracing_context
