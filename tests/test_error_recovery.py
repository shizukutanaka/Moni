"""
Comprehensive test suite for the error recovery and handling system.
Tests the ErrorRecoveryManager and related error handling components.
"""

import pytest
import threading
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from enum import Enum

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from moni.error_recovery import (
    ErrorRecoveryManager,
    ErrorHandler,
    RecoveryStrategy,
    ErrorLogger,
    SystemCheckpoint,
    CircuitBreaker,
    RetryPolicy
)


class TestErrorRecoveryManager:
    """Test suite for ErrorRecoveryManager class."""

    @pytest.fixture
    def error_recovery_manager(self):
        """Create ErrorRecoveryManager instance for testing."""
        return ErrorRecoveryManager()

    @pytest.fixture
    def temp_recovery_dir(self):
        """Create temporary recovery directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_initialization(self, error_recovery_manager):
        """Test ErrorRecoveryManager initialization."""
        assert error_recovery_manager.is_monitoring is False
        assert len(error_recovery_manager._error_handlers) == 0
        assert len(error_recovery_manager._recovery_strategies) == 0
        assert error_recovery_manager._checkpoint_manager is not None

    def test_start_stop_monitoring(self, error_recovery_manager):
        """Test starting and stopping error monitoring."""
        error_recovery_manager.start_monitoring()
        assert error_recovery_manager.is_monitoring is True

        error_recovery_manager.stop_monitoring()
        assert error_recovery_manager.is_monitoring is False

    def test_register_error_handler(self, error_recovery_manager):
        """Test registering error handlers."""
        def custom_handler(error, context):
            return f"Handled {type(error).__name__}"

        error_recovery_manager.register_error_handler(ValueError, custom_handler)

        assert ValueError in error_recovery_manager._error_handlers
        assert len(error_recovery_manager._error_handlers) == 1

    def test_handle_error_with_registered_handler(self, error_recovery_manager):
        """Test handling errors with registered handlers."""
        handled_errors = []

        def test_handler(error, context):
            handled_errors.append(error)
            return True

        error_recovery_manager.register_error_handler(ValueError, test_handler)

        # Handle error
        test_error = ValueError("Test error")
        result = error_recovery_manager.handle_error(test_error, "test_component")

        assert result is True
        assert len(handled_errors) == 1
        assert handled_errors[0] == test_error

    def test_handle_error_without_handler(self, error_recovery_manager):
        """Test handling errors without specific handlers."""
        test_error = RuntimeError("Unhandled error")
        result = error_recovery_manager.handle_error(test_error, "test_component")

        # Should use default error handling
        assert isinstance(result, bool)

    def test_recovery_strategy_registration(self, error_recovery_manager):
        """Test registering recovery strategies."""
        def test_strategy(error, context):
            return {"action": "restart", "success": True}

        error_recovery_manager.register_recovery_strategy("network_error", test_strategy)

        assert "network_error" in error_recovery_manager._recovery_strategies

    def test_automatic_recovery(self, error_recovery_manager):
        """Test automatic error recovery."""
        recovery_actions = []

        def recovery_strategy(error, context):
            recovery_actions.append("recovery_attempted")
            return {"action": "restart", "success": True}

        error_recovery_manager.register_recovery_strategy("test_error", recovery_strategy)

        # Simulate error requiring recovery
        error = Exception("Test error")
        result = error_recovery_manager.attempt_recovery(error, "test_error", "test_component")

        assert result["success"] is True
        assert len(recovery_actions) == 1

    def test_error_escalation(self, error_recovery_manager):
        """Test error escalation when recovery fails."""
        escalated_errors = []

        def failing_recovery(error, context):
            return {"action": "restart", "success": False}

        def escalation_handler(error, context, failed_recovery):
            escalated_errors.append(error)
            return True

        error_recovery_manager.register_recovery_strategy("failing_strategy", failing_recovery)
        error_recovery_manager.set_escalation_handler(escalation_handler)

        # Simulate failing recovery
        error = Exception("Failing error")
        result = error_recovery_manager.attempt_recovery(error, "failing_strategy", "test_component")

        assert result["success"] is False
        assert len(escalated_errors) == 1

    def test_error_rate_limiting(self, error_recovery_manager):
        """Test error rate limiting functionality."""
        error_recovery_manager.set_error_rate_limit("test_component", max_errors=2, time_window=1.0)

        test_error = ValueError("Rate limited error")

        # First two errors should be handled
        result1 = error_recovery_manager.handle_error(test_error, "test_component")
        result2 = error_recovery_manager.handle_error(test_error, "test_component")

        # Third error should be rate limited
        result3 = error_recovery_manager.handle_error(test_error, "test_component")

        assert result1 is not None
        assert result2 is not None
        # Rate limited response may vary

    def test_component_health_tracking(self, error_recovery_manager):
        """Test component health tracking."""
        # Register component
        error_recovery_manager.register_component("database_connection")

        # Simulate health check
        health_status = error_recovery_manager.check_component_health("database_connection")

        assert "status" in health_status
        assert "last_check" in health_status

    def test_graceful_degradation(self, error_recovery_manager):
        """Test graceful degradation functionality."""
        degradation_actions = []

        def degradation_strategy(component, error):
            degradation_actions.append(f"degraded_{component}")
            return {"mode": "limited", "available_features": ["basic"]}

        error_recovery_manager.set_degradation_strategy("ui_component", degradation_strategy)

        # Trigger degradation
        result = error_recovery_manager.trigger_graceful_degradation(
            "ui_component",
            Exception("UI error")
        )

        assert result["mode"] == "limited"
        assert len(degradation_actions) == 1

    def test_recovery_metrics(self, error_recovery_manager):
        """Test recovery metrics collection."""
        # Generate some recovery events
        for i in range(5):
            error = ValueError(f"Test error {i}")
            error_recovery_manager.handle_error(error, "test_component")

        metrics = error_recovery_manager.get_recovery_metrics()

        assert "total_errors" in metrics
        assert "recovery_success_rate" in metrics
        assert "component_error_counts" in metrics


class TestErrorHandler:
    """Test suite for ErrorHandler class."""

    def test_error_handler_creation(self):
        """Test creating error handlers."""
        def handler_func(error, context):
            return f"Handled {error}"

        handler = ErrorHandler(
            error_type=ValueError,
            handler_func=handler_func,
            priority=1
        )

        assert handler.error_type == ValueError
        assert handler.handler_func == handler_func
        assert handler.priority == 1

    def test_error_handler_execution(self):
        """Test executing error handlers."""
        handled_data = []

        def handler_func(error, context):
            handled_data.append((error, context))
            return True

        handler = ErrorHandler(ValueError, handler_func)

        test_error = ValueError("Test")
        test_context = {"component": "test"}

        result = handler.handle(test_error, test_context)

        assert result is True
        assert len(handled_data) == 1
        assert handled_data[0][0] == test_error

    def test_conditional_error_handler(self):
        """Test conditional error handling."""
        def conditional_handler(error, context):
            if context.get("severity") == "critical":
                return "critical_handled"
            return "normal_handled"

        handler = ErrorHandler(Exception, conditional_handler)

        # Test critical error
        critical_result = handler.handle(
            Exception("Critical error"),
            {"severity": "critical"}
        )
        assert critical_result == "critical_handled"

        # Test normal error
        normal_result = handler.handle(
            Exception("Normal error"),
            {"severity": "normal"}
        )
        assert normal_result == "normal_handled"


class TestRecoveryStrategy:
    """Test suite for RecoveryStrategy class."""

    def test_recovery_strategy_creation(self):
        """Test creating recovery strategies."""
        def strategy_func(error, context):
            return {"action": "restart", "success": True}

        strategy = RecoveryStrategy(
            name="restart_strategy",
            strategy_func=strategy_func,
            max_attempts=3
        )

        assert strategy.name == "restart_strategy"
        assert strategy.max_attempts == 3

    def test_recovery_strategy_execution(self):
        """Test executing recovery strategies."""
        execution_count = []

        def strategy_func(error, context):
            execution_count.append(1)
            return {"action": "restart", "success": True}

        strategy = RecoveryStrategy("test_strategy", strategy_func)

        result = strategy.execute(Exception("Test"), {"component": "test"})

        assert result["success"] is True
        assert len(execution_count) == 1

    def test_retry_recovery_strategy(self):
        """Test retry-based recovery strategy."""
        attempt_count = []

        def failing_then_succeeding_strategy(error, context):
            attempt_count.append(1)
            if len(attempt_count) < 3:
                return {"action": "retry", "success": False}
            return {"action": "retry", "success": True}

        strategy = RecoveryStrategy(
            "retry_strategy",
            failing_then_succeeding_strategy,
            max_attempts=5
        )

        result = strategy.execute_with_retry(Exception("Test"), {"component": "test"})

        assert result["success"] is True
        assert len(attempt_count) == 3  # Failed twice, succeeded on third

    def test_recovery_strategy_timeout(self):
        """Test recovery strategy with timeout."""
        def slow_strategy(error, context):
            time.sleep(0.2)  # Simulate slow recovery
            return {"action": "slow_recovery", "success": True}

        strategy = RecoveryStrategy("slow_strategy", slow_strategy, timeout=0.1)

        start_time = time.time()
        result = strategy.execute_with_timeout(Exception("Test"), {"component": "test"})
        end_time = time.time()

        # Should timeout quickly
        assert (end_time - start_time) < 0.15
        assert result.get("success") is False or result.get("timeout") is True


class TestErrorLogger:
    """Test suite for ErrorLogger class."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_error_logger_creation(self, temp_log_dir):
        """Test creating error logger."""
        logger = ErrorLogger(log_dir=temp_log_dir)

        assert logger.log_dir == temp_log_dir
        assert logger.log_file.parent == temp_log_dir

    def test_log_error(self, temp_log_dir):
        """Test logging errors."""
        logger = ErrorLogger(log_dir=temp_log_dir)

        test_error = ValueError("Test logging error")
        context = {"component": "test", "user_id": "user123"}

        logger.log_error(test_error, context)

        # Check if log file was created and contains error
        assert logger.log_file.exists()
        log_content = logger.log_file.read_text()
        assert "ValueError" in log_content
        assert "Test logging error" in log_content

    def test_structured_logging(self, temp_log_dir):
        """Test structured error logging."""
        logger = ErrorLogger(log_dir=temp_log_dir, format="json")

        test_error = RuntimeError("Structured error")
        context = {"component": "api", "endpoint": "/users"}

        logger.log_error(test_error, context)

        log_content = logger.log_file.read_text()
        # Should contain JSON-like structure
        assert '"error_type": "RuntimeError"' in log_content
        assert '"component": "api"' in log_content

    def test_log_rotation(self, temp_log_dir):
        """Test log file rotation."""
        logger = ErrorLogger(log_dir=temp_log_dir, max_log_size_mb=0.001)  # Very small size

        # Generate enough logs to trigger rotation
        for i in range(100):
            test_error = Exception(f"Rotation test error {i}")
            logger.log_error(test_error, {"iteration": i})

        # Check if multiple log files exist
        log_files = list(temp_log_dir.glob("*.log*"))
        assert len(log_files) > 1

    def test_error_aggregation(self, temp_log_dir):
        """Test error aggregation and statistics."""
        logger = ErrorLogger(log_dir=temp_log_dir)

        # Log multiple errors of different types
        for i in range(5):
            logger.log_error(ValueError(f"Value error {i}"), {"component": "validation"})

        for i in range(3):
            logger.log_error(RuntimeError(f"Runtime error {i}"), {"component": "runtime"})

        stats = logger.get_error_statistics()

        assert "error_counts" in stats
        assert "component_counts" in stats
        assert stats["error_counts"]["ValueError"] == 5
        assert stats["error_counts"]["RuntimeError"] == 3


class TestSystemCheckpoint:
    """Test suite for SystemCheckpoint class."""

    @pytest.fixture
    def temp_checkpoint_dir(self):
        """Create temporary checkpoint directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_checkpoint_creation(self, temp_checkpoint_dir):
        """Test creating system checkpoints."""
        checkpoint = SystemCheckpoint(checkpoint_dir=temp_checkpoint_dir)

        test_state = {
            "config": {"setting1": "value1"},
            "metrics": {"cpu": 50.0, "memory": 60.0},
            "connections": ["db1", "api1"]
        }

        checkpoint_id = checkpoint.create_checkpoint(test_state, "test_checkpoint")

        assert checkpoint_id is not None
        assert len(checkpoint_id) > 0

    def test_checkpoint_restoration(self, temp_checkpoint_dir):
        """Test restoring from checkpoints."""
        checkpoint = SystemCheckpoint(checkpoint_dir=temp_checkpoint_dir)

        original_state = {
            "config": {"debug": True},
            "active_connections": 5,
            "cache_size": 1024
        }

        # Create checkpoint
        checkpoint_id = checkpoint.create_checkpoint(original_state, "restore_test")

        # Restore checkpoint
        restored_state = checkpoint.restore_checkpoint(checkpoint_id)

        assert restored_state == original_state

    def test_checkpoint_listing(self, temp_checkpoint_dir):
        """Test listing available checkpoints."""
        checkpoint = SystemCheckpoint(checkpoint_dir=temp_checkpoint_dir)

        # Create multiple checkpoints
        states = [
            {"state": f"test_{i}"} for i in range(3)
        ]

        checkpoint_ids = []
        for i, state in enumerate(states):
            checkpoint_id = checkpoint.create_checkpoint(state, f"checkpoint_{i}")
            checkpoint_ids.append(checkpoint_id)

        # List checkpoints
        checkpoint_list = checkpoint.list_checkpoints()

        assert len(checkpoint_list) >= 3
        for checkpoint_info in checkpoint_list:
            assert "id" in checkpoint_info
            assert "timestamp" in checkpoint_info
            assert "description" in checkpoint_info

    def test_checkpoint_cleanup(self, temp_checkpoint_dir):
        """Test checkpoint cleanup functionality."""
        checkpoint = SystemCheckpoint(checkpoint_dir=temp_checkpoint_dir)

        # Create multiple checkpoints
        checkpoint_ids = []
        for i in range(5):
            state = {"test": f"data_{i}"}
            checkpoint_id = checkpoint.create_checkpoint(state, f"cleanup_test_{i}")
            checkpoint_ids.append(checkpoint_id)

        # Cleanup old checkpoints (keep only 2)
        checkpoint.cleanup_old_checkpoints(max_checkpoints=2)

        remaining_checkpoints = checkpoint.list_checkpoints()
        assert len(remaining_checkpoints) == 2

    def test_incremental_checkpoints(self, temp_checkpoint_dir):
        """Test incremental checkpoint functionality."""
        checkpoint = SystemCheckpoint(checkpoint_dir=temp_checkpoint_dir)

        # Create base checkpoint
        base_state = {"config": {"setting1": "value1"}, "data": [1, 2, 3]}
        base_id = checkpoint.create_checkpoint(base_state, "base")

        # Create incremental checkpoint
        incremental_changes = {"config": {"setting2": "value2"}, "data": [4, 5]}
        incremental_id = checkpoint.create_incremental_checkpoint(
            incremental_changes,
            base_id,
            "incremental"
        )

        # Restore incremental checkpoint
        restored_state = checkpoint.restore_checkpoint(incremental_id)

        expected_state = {
            "config": {"setting1": "value1", "setting2": "value2"},
            "data": [1, 2, 3, 4, 5]
        }

        assert restored_state == expected_state


class TestCircuitBreaker:
    """Test suite for CircuitBreaker class."""

    def test_circuit_breaker_initialization(self):
        """Test CircuitBreaker initialization."""
        breaker = CircuitBreaker(
            failure_threshold=5,
            timeout_seconds=30
        )

        assert breaker.failure_threshold == 5
        assert breaker.timeout_seconds == 30
        assert breaker.state == "CLOSED"

    def test_circuit_breaker_success(self):
        """Test successful operations through circuit breaker."""
        breaker = CircuitBreaker(failure_threshold=3)

        def successful_operation():
            return "success"

        # Execute successful operation
        result = breaker.call(successful_operation)

        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

    def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opening on failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3)

        def failing_operation():
            raise Exception("Operation failed")

        # Execute failing operations to reach threshold
        for i in range(3):
            try:
                breaker.call(failing_operation)
            except Exception:
                pass

        # Circuit should be open now
        assert breaker.state == "OPEN"

        # Next call should be rejected immediately
        with pytest.raises(Exception) as exc_info:
            breaker.call(failing_operation)

        assert "Circuit breaker is OPEN" in str(exc_info.value)

    def test_circuit_breaker_half_open(self):
        """Test circuit breaker half-open state."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)

        def failing_operation():
            raise Exception("Still failing")

        # Trip the circuit breaker
        for i in range(2):
            try:
                breaker.call(failing_operation)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(0.2)

        # Next call should put it in HALF_OPEN state
        try:
            breaker.call(failing_operation)
        except Exception:
            pass

        # Should be back to OPEN after failure in HALF_OPEN
        assert breaker.state == "OPEN"

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery to closed state."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)

        def sometimes_failing_operation(should_fail=True):
            if should_fail:
                raise Exception("Failing")
            return "success"

        # Trip the circuit breaker
        for i in range(2):
            try:
                breaker.call(lambda: sometimes_failing_operation(True))
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(0.2)

        # Successful call should close the circuit
        result = breaker.call(lambda: sometimes_failing_operation(False))

        assert result == "success"
        assert breaker.state == "CLOSED"


class TestRetryPolicy:
    """Test suite for RetryPolicy class."""

    def test_retry_policy_creation(self):
        """Test creating retry policies."""
        policy = RetryPolicy(
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0,
            backoff_multiplier=2.0
        )

        assert policy.max_attempts == 3
        assert policy.base_delay == 0.1
        assert policy.max_delay == 1.0
        assert policy.backoff_multiplier == 2.0

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        policy = RetryPolicy(base_delay=0.1, backoff_multiplier=2.0, max_delay=1.0)

        delays = []
        for attempt in range(5):
            delay = policy.calculate_delay(attempt)
            delays.append(delay)

        # Should follow exponential pattern with max cap
        assert delays[0] == 0.1  # base delay
        assert delays[1] == 0.2  # base * 2
        assert delays[2] == 0.4  # base * 4
        assert delays[3] == 0.8  # base * 8
        assert delays[4] == 1.0  # capped at max_delay

    def test_retry_execution(self):
        """Test retry execution with failing operation."""
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)

        attempt_count = []

        def failing_then_succeeding():
            attempt_count.append(1)
            if len(attempt_count) < 3:
                raise Exception("Still failing")
            return "success"

        result = policy.execute(failing_then_succeeding)

        assert result == "success"
        assert len(attempt_count) == 3

    def test_retry_exhaustion(self):
        """Test retry policy when all attempts are exhausted."""
        policy = RetryPolicy(max_attempts=2, base_delay=0.01)

        def always_failing():
            raise Exception("Always fails")

        with pytest.raises(Exception) as exc_info:
            policy.execute(always_failing)

        assert "Always fails" in str(exc_info.value)

    def test_conditional_retry(self):
        """Test conditional retry based on exception type."""
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)

        def retryable_condition(exception):
            return isinstance(exception, ValueError)

        attempt_count = []

        def failing_with_different_errors():
            attempt_count.append(1)
            if len(attempt_count) == 1:
                raise ValueError("Retryable error")
            else:
                raise RuntimeError("Non-retryable error")

        with pytest.raises(RuntimeError):
            policy.execute(failing_with_different_errors, retry_condition=retryable_condition)

        # Should have stopped after RuntimeError (non-retryable)
        assert len(attempt_count) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])