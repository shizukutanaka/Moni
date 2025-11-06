"""
Enterprise-grade resilience and error handling system for Moni.
Implements circuit breakers, retry mechanisms, graceful degradation,
and self-healing capabilities for maximum stability.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union
)

import psutil
from PySide6.QtCore import QObject, Signal, QTimer

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing recovery


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    FATAL = 5


class RecoveryStrategy(Enum):
    """Recovery strategies for errors."""
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAK = "circuit_break"
    DEGRADE = "degrade"
    RESTART = "restart"
    ISOLATE = "isolate"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    timestamp: datetime
    error_type: Type[Exception]
    error_message: str
    stack_trace: str
    component: str
    severity: ErrorSeverity
    recovery_attempts: int = 0
    recovered: bool = False
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "error_type": self.error_type.__name__,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "component": self.component,
            "severity": self.severity.value,
            "recovery_attempts": self.recovery_attempts,
            "recovered": self.recovered,
            "data": self.data
        }


@dataclass
class HealthMetrics:
    """System health metrics."""
    uptime_seconds: float
    error_rate: float
    success_rate: float
    average_response_time: float
    memory_usage_percent: float
    cpu_usage_percent: float
    active_circuits: int
    open_circuits: int
    total_errors: int
    total_recoveries: int
    health_score: float = 0.0

    def calculate_health_score(self) -> float:
        """Calculate overall health score (0-100)."""
        score = 100.0

        # Penalize for errors
        score -= min(30, self.error_rate * 100)

        # Penalize for resource usage
        score -= min(20, self.memory_usage_percent / 5)
        score -= min(20, self.cpu_usage_percent / 5)

        # Penalize for open circuits
        if self.active_circuits > 0:
            open_ratio = self.open_circuits / self.active_circuits
            score -= min(20, open_ratio * 20)

        # Bonus for high recovery rate
        if self.total_errors > 0:
            recovery_rate = self.total_recoveries / self.total_errors
            score += min(10, recovery_rate * 10)

        self.health_score = max(0, min(100, score))
        return self.health_score


class CircuitBreaker:
    """Circuit breaker pattern implementation."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: float = 60,
        half_open_max_calls: int = 3
    ):
        """Initialize circuit breaker."""
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        self._lock = threading.RLock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if not self._can_attempt():
                raise Exception(f"Circuit breaker '{self.name}' is OPEN")

            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _can_attempt(self) -> bool:
        """Check if call can be attempted."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.timeout_seconds:
                    self._transition_to_half_open()
                    return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return False

    def _on_success(self) -> None:
        """Handle successful call."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()
            elif self.state == CircuitState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)

    def _on_failure(self) -> None:
        """Handle failed call."""
        with self._lock:
            self.last_failure_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                self._transition_to_open()
            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self.state = CircuitState.OPEN
        self.half_open_calls = 0
        logger.warning(f"Circuit breaker '{self.name}' opened")

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' closed")

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' half-open")

    def reset(self) -> None:
        """Manually reset circuit breaker."""
        with self._lock:
            self._transition_to_closed()

    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "half_open_calls": self.half_open_calls
            }


class RetryPolicy:
    """Retry policy for transient failures."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """Initialize retry policy."""
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )

        if self.jitter:
            # Add random jitter (0-25% of delay)
            delay *= (1 + random.random() * 0.25)

        return delay

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if operation should be retried."""
        if attempt >= self.max_attempts:
            return False

        # Define retryable errors
        retryable_errors = (
            ConnectionError,
            TimeoutError,
            OSError,
            IOError
        )

        return isinstance(error, retryable_errors)


class Bulkhead:
    """Bulkhead pattern for resource isolation."""

    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        max_queue: int = 100,
        timeout: float = 30.0
    ):
        """Initialize bulkhead."""
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.timeout = timeout

        self._semaphore = threading.Semaphore(max_concurrent)
        self._queue_size = 0
        self._queue_lock = threading.Lock()

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with bulkhead protection."""
        # Check queue limit
        with self._queue_lock:
            if self._queue_size >= self.max_queue:
                raise Exception(f"Bulkhead '{self.name}' queue full")
            self._queue_size += 1

        try:
            # Acquire semaphore with timeout
            acquired = self._semaphore.acquire(timeout=self.timeout)
            if not acquired:
                raise TimeoutError(f"Bulkhead '{self.name}' timeout")

            try:
                return func(*args, **kwargs)
            finally:
                self._semaphore.release()
        finally:
            with self._queue_lock:
                self._queue_size -= 1


class ErrorRecoveryManager:
    """Manages error recovery strategies."""

    def __init__(self):
        """Initialize error recovery manager."""
        self._handlers: Dict[Type[Exception], List[Callable]] = {}
        self._fallbacks: Dict[str, Callable] = {}
        self._error_history: deque[ErrorContext] = deque(maxlen=1000)
        self._recovery_strategies: Dict[Type[Exception], RecoveryStrategy] = {}

    def register_handler(
        self,
        error_type: Type[Exception],
        handler: Callable[[ErrorContext], None]
    ) -> None:
        """Register error handler."""
        if error_type not in self._handlers:
            self._handlers[error_type] = []
        self._handlers[error_type].append(handler)

    def register_fallback(
        self,
        component: str,
        fallback: Callable[[], Any]
    ) -> None:
        """Register fallback function."""
        self._fallbacks[component] = fallback

    def handle_error(
        self,
        error: Exception,
        component: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        **context_data
    ) -> Optional[Any]:
        """Handle error with appropriate strategy."""
        # Create error context
        error_context = ErrorContext(
            timestamp=datetime.now(),
            error_type=type(error),
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            component=component,
            severity=severity,
            data=context_data
        )

        self._error_history.append(error_context)

        # Get recovery strategy
        strategy = self._get_recovery_strategy(error, severity)

        # Apply recovery
        result = None
        if strategy == RecoveryStrategy.FALLBACK:
            result = self._apply_fallback(component)
            if result is not None:
                error_context.recovered = True

        elif strategy == RecoveryStrategy.RETRY:
            # Retry is handled by decorator
            pass

        # Execute handlers
        handlers = self._handlers.get(type(error), [])
        for handler in handlers:
            try:
                handler(error_context)
            except Exception as e:
                logger.error(f"Error handler failed: {e}")

        # Log critical errors
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            self._log_critical_error(error_context)

        return result

    def _get_recovery_strategy(
        self,
        error: Exception,
        severity: ErrorSeverity
    ) -> RecoveryStrategy:
        """Determine recovery strategy for error."""
        # Check registered strategies
        if type(error) in self._recovery_strategies:
            return self._recovery_strategies[type(error)]

        # Default strategies based on severity
        if severity == ErrorSeverity.LOW:
            return RecoveryStrategy.RETRY
        elif severity == ErrorSeverity.MEDIUM:
            return RecoveryStrategy.FALLBACK
        elif severity == ErrorSeverity.HIGH:
            return RecoveryStrategy.CIRCUIT_BREAK
        else:
            return RecoveryStrategy.ISOLATE

    def _apply_fallback(self, component: str) -> Optional[Any]:
        """Apply fallback for component."""
        if component in self._fallbacks:
            try:
                return self._fallbacks[component]()
            except Exception as e:
                logger.error(f"Fallback failed for {component}: {e}")
        return None

    def _log_critical_error(self, error_context: ErrorContext) -> None:
        """Log critical error for analysis."""
        log_path = Path.home() / ".moni" / "critical_errors.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import json
            with log_path.open("a") as f:
                f.write(json.dumps(error_context.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to log critical error: {e}")


class HealthMonitor(QObject):
    """Monitors system health and triggers self-healing."""

    health_changed = Signal(float)
    alert_triggered = Signal(str)

    def __init__(self):
        """Initialize health monitor."""
        super().__init__()
        self._start_time = time.time()
        self._error_count = 0
        self._success_count = 0
        self._recovery_count = 0
        self._response_times: deque[float] = deque(maxlen=100)
        self._check_timer = QTimer()
        self._check_timer.timeout.connect(self._perform_health_check)
        self._check_timer.start(10000)  # Check every 10 seconds

    def record_operation(
        self,
        success: bool,
        response_time: Optional[float] = None
    ) -> None:
        """Record operation outcome."""
        if success:
            self._success_count += 1
        else:
            self._error_count += 1

        if response_time is not None:
            self._response_times.append(response_time)

    def record_recovery(self) -> None:
        """Record successful recovery."""
        self._recovery_count += 1

    def get_health_metrics(self) -> HealthMetrics:
        """Get current health metrics."""
        uptime = time.time() - self._start_time
        total_ops = self._success_count + self._error_count

        error_rate = self._error_count / max(1, total_ops)
        success_rate = self._success_count / max(1, total_ops)

        avg_response_time = (
            sum(self._response_times) / len(self._response_times)
            if self._response_times else 0.0
        )

        process = psutil.Process()
        memory_percent = process.memory_percent()
        cpu_percent = process.cpu_percent()

        metrics = HealthMetrics(
            uptime_seconds=uptime,
            error_rate=error_rate,
            success_rate=success_rate,
            average_response_time=avg_response_time,
            memory_usage_percent=memory_percent,
            cpu_usage_percent=cpu_percent,
            active_circuits=0,  # To be filled by resilience manager
            open_circuits=0,
            total_errors=self._error_count,
            total_recoveries=self._recovery_count
        )

        metrics.calculate_health_score()
        return metrics

    def _perform_health_check(self) -> None:
        """Perform periodic health check."""
        metrics = self.get_health_metrics()
        self.health_changed.emit(metrics.health_score)

        # Trigger alerts for poor health
        if metrics.health_score < 30:
            self.alert_triggered.emit("CRITICAL: System health below 30%")
        elif metrics.health_score < 50:
            self.alert_triggered.emit("WARNING: System health below 50%")


class ResilienceManager:
    """Main resilience coordination manager."""

    def __init__(self):
        """Initialize resilience manager."""
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._bulkheads: Dict[str, Bulkhead] = {}
        self._retry_policies: Dict[str, RetryPolicy] = {}
        self._error_recovery = ErrorRecoveryManager()
        self._health_monitor = HealthMonitor()
        self._self_healing_enabled = True

    def get_circuit_breaker(
        self,
        name: str,
        **kwargs
    ) -> CircuitBreaker:
        """Get or create circuit breaker."""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(name, **kwargs)
        return self._circuit_breakers[name]

    def get_bulkhead(
        self,
        name: str,
        **kwargs
    ) -> Bulkhead:
        """Get or create bulkhead."""
        if name not in self._bulkheads:
            self._bulkheads[name] = Bulkhead(name, **kwargs)
        return self._bulkheads[name]

    def get_retry_policy(
        self,
        name: str,
        **kwargs
    ) -> RetryPolicy:
        """Get or create retry policy."""
        if name not in self._retry_policies:
            self._retry_policies[name] = RetryPolicy(**kwargs)
        return self._retry_policies[name]

    def with_resilience(
        self,
        circuit_breaker: Optional[str] = None,
        bulkhead: Optional[str] = None,
        retry_policy: Optional[str] = None,
        fallback: Optional[Callable] = None,
        component: str = "unknown"
    ) -> Callable:
        """Decorator to add resilience patterns to function."""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Apply bulkhead if specified
                if bulkhead:
                    bulkhead_inst = self.get_bulkhead(bulkhead)
                    func_to_call = lambda: bulkhead_inst.execute(func, *args, **kwargs)
                else:
                    func_to_call = lambda: func(*args, **kwargs)

                # Apply retry if specified
                if retry_policy:
                    policy = self.get_retry_policy(retry_policy)
                    original_func = func_to_call

                    def func_with_retry():
                        last_error = None
                        for attempt in range(policy.max_attempts):
                            try:
                                return original_func()
                            except Exception as e:
                                last_error = e
                                if not policy.should_retry(attempt + 1, e):
                                    raise
                                time.sleep(policy.calculate_delay(attempt))
                        raise last_error

                    func_to_call = func_with_retry

                # Apply circuit breaker if specified
                if circuit_breaker:
                    cb = self.get_circuit_breaker(circuit_breaker)
                    func_to_call = lambda: cb.call(func_to_call)

                # Execute with error handling
                start_time = time.time()
                try:
                    result = func_to_call()
                    response_time = time.time() - start_time
                    self._health_monitor.record_operation(True, response_time)
                    return result

                except Exception as e:
                    response_time = time.time() - start_time
                    self._health_monitor.record_operation(False, response_time)

                    # Try fallback
                    if fallback:
                        try:
                            result = fallback(*args, **kwargs)
                            self._health_monitor.record_recovery()
                            return result
                        except Exception as fallback_error:
                            logger.error(f"Fallback failed: {fallback_error}")

                    # Handle error
                    self._error_recovery.handle_error(
                        e,
                        component=component,
                        severity=ErrorSeverity.MEDIUM
                    )
                    raise

            return wrapper
        return decorator

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        health_metrics = self._health_monitor.get_health_metrics()

        # Update circuit breaker counts
        active_circuits = len(self._circuit_breakers)
        open_circuits = sum(
            1 for cb in self._circuit_breakers.values()
            if cb.state == CircuitState.OPEN
        )

        health_metrics.active_circuits = active_circuits
        health_metrics.open_circuits = open_circuits
        health_metrics.calculate_health_score()

        circuit_states = {
            name: cb.get_state()
            for name, cb in self._circuit_breakers.items()
        }

        return {
            "health": health_metrics.__dict__,
            "circuits": circuit_states,
            "self_healing": self._self_healing_enabled
        }

    def trigger_self_healing(self) -> Dict[str, Any]:
        """Trigger self-healing procedures."""
        if not self._self_healing_enabled:
            return {"status": "disabled"}

        healing_actions = []

        # Reset stuck circuit breakers
        for name, cb in self._circuit_breakers.items():
            if cb.state == CircuitState.OPEN:
                if cb.last_failure_time:
                    elapsed = (datetime.now() - cb.last_failure_time).total_seconds()
                    if elapsed > cb.timeout_seconds * 2:
                        cb.reset()
                        healing_actions.append(f"Reset circuit breaker: {name}")

        # Clear error history if too large
        if len(self._error_recovery._error_history) > 900:
            old_size = len(self._error_recovery._error_history)
            self._error_recovery._error_history = deque(
                list(self._error_recovery._error_history)[-500:],
                maxlen=1000
            )
            healing_actions.append(f"Cleared {old_size - 500} old errors")

        # Trigger garbage collection if memory is high
        process = psutil.Process()
        if process.memory_percent() > 80:
            import gc
            collected = gc.collect()
            healing_actions.append(f"Garbage collected {collected} objects")

        return {
            "status": "completed",
            "actions": healing_actions,
            "timestamp": datetime.now().isoformat()
        }


# Global resilience manager
_resilience_manager: Optional[ResilienceManager] = None


def get_resilience_manager() -> ResilienceManager:
    """Get or create global resilience manager."""
    global _resilience_manager
    if _resilience_manager is None:
        _resilience_manager = ResilienceManager()
    return _resilience_manager


def resilient(
    circuit_breaker: Optional[str] = None,
    retry: bool = True,
    fallback: Optional[Callable] = None
) -> Callable:
    """Quick decorator for adding resilience to functions."""
    manager = get_resilience_manager()

    retry_policy = "default" if retry else None

    return manager.with_resilience(
        circuit_breaker=circuit_breaker,
        retry_policy=retry_policy,
        fallback=fallback
    )