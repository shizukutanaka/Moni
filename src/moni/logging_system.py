"""
Advanced logging system for Moni system monitor.
Provides structured logging, error handling, and monitoring integration.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import traceback
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List, Union
from enum import Enum
import inspect

from .security import InputValidator, security_logger


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Log category enumeration."""
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    USER_ACTION = "USER_ACTION"
    SYSTEM = "SYSTEM"
    NETWORK = "NETWORK"
    EXPORT = "EXPORT"
    CONFIG = "CONFIG"
    METRIC = "METRIC"


class StructuredLogger:
    """Enhanced logger with structured logging and security features."""

    def __init__(self, name: str, log_dir: Optional[Path] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.log_dir = log_dir or Path.home() / ".config" / "moni" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Thread-local storage for context
        self._context = threading.local()

        # Setup formatters and handlers
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging formatters and handlers."""
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers.clear()

        # JSON formatter for structured logging
        json_formatter = JsonFormatter()

        # File handler with rotation
        log_file = self.log_dir / f"{self.name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(json_formatter)

        # Console handler for development
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)

        # Error file handler for errors and above
        error_file = self.log_dir / f"{self.name}_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(error_handler)

    def set_context(self, **kwargs):
        """Set logging context for current thread."""
        if not hasattr(self._context, 'data'):
            self._context.data = {}

        self._context.data.update(kwargs)

    def clear_context(self):
        """Clear logging context for current thread."""
        if hasattr(self._context, 'data'):
            self._context.data.clear()

    def get_context(self) -> Dict[str, Any]:
        """Get current logging context."""
        if hasattr(self._context, 'data'):
            return self._context.data.copy()
        return {}

    def _build_log_record(
        self,
        level: LogLevel,
        message: str,
        category: Optional[LogCategory] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        exc_info: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Build structured log record."""
        # Get caller information
        frame = inspect.currentframe()
        try:
            # Go up the stack to find the actual caller
            caller_frame = frame.f_back.f_back.f_back
            caller_info = {
                'file': caller_frame.f_code.co_filename,
                'function': caller_frame.f_code.co_name,
                'line': caller_frame.f_lineno
            }
        except AttributeError:
            caller_info = {'file': 'unknown', 'function': 'unknown', 'line': 0}
        finally:
            del frame

        # Build base record
        record = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level.value,
            'logger': self.name,
            'message': InputValidator.sanitize_log_data(message),
            'caller': caller_info
        }

        # Add category if provided
        if category:
            record['category'] = category.value

        # Add context data
        context = self.get_context()
        if context:
            record['context'] = InputValidator.sanitize_log_data(context)

        # Add extra data
        if extra_data:
            record['extra'] = InputValidator.sanitize_log_data(extra_data)

        # Add exception information
        if exc_info:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if exc_type:
                record['exception'] = {
                    'type': exc_type.__name__,
                    'message': str(exc_value),
                    'traceback': traceback.format_exception(exc_type, exc_value, exc_traceback)
                }

        return record

    def debug(self, message: str, category: Optional[LogCategory] = None, **kwargs):
        """Log debug message."""
        record = self._build_log_record(LogLevel.DEBUG, message, category, kwargs)
        self.logger.debug(json.dumps(record), extra={'structured_record': record})

    def info(self, message: str, category: Optional[LogCategory] = None, **kwargs):
        """Log info message."""
        record = self._build_log_record(LogLevel.INFO, message, category, kwargs)
        self.logger.info(json.dumps(record), extra={'structured_record': record})

    def warning(self, message: str, category: Optional[LogCategory] = None, **kwargs):
        """Log warning message."""
        record = self._build_log_record(LogLevel.WARNING, message, category, kwargs)
        self.logger.warning(json.dumps(record), extra={'structured_record': record})

    def error(self, message: str, category: Optional[LogCategory] = None, exc_info: bool = False, **kwargs):
        """Log error message."""
        record = self._build_log_record(LogLevel.ERROR, message, category, kwargs, exc_info)
        self.logger.error(json.dumps(record), extra={'structured_record': record})

    def critical(self, message: str, category: Optional[LogCategory] = None, exc_info: bool = False, **kwargs):
        """Log critical message."""
        record = self._build_log_record(LogLevel.CRITICAL, message, category, kwargs, exc_info)
        self.logger.critical(json.dumps(record), extra={'structured_record': record})

        # Also send to security logger for critical events
        security_logger.log_security_event(
            'CRITICAL_ERROR',
            {'message': message, 'logger': self.name, **kwargs},
            'CRITICAL'
        )


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        if hasattr(record, 'structured_record'):
            return json.dumps(record.structured_record, ensure_ascii=False)

        # Fallback to standard formatting for non-structured records
        log_obj = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


class ErrorHandler:
    """Global error handler with recovery strategies."""

    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.error_counts: Dict[str, int] = {}
        self.error_timestamps: Dict[str, List[float]] = {}
        self.recovery_strategies: Dict[str, callable] = {}

    def register_recovery_strategy(self, error_type: str, strategy: callable):
        """Register a recovery strategy for specific error types."""
        self.recovery_strategies[error_type] = strategy

    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        category: LogCategory = LogCategory.SYSTEM,
        attempt_recovery: bool = True
    ) -> bool:
        """Handle an error with logging and potential recovery."""
        error_type = type(error).__name__
        error_message = str(error)

        # Track error frequency
        self._track_error_frequency(error_type)

        # Log the error
        self.logger.error(
            f"Unhandled error: {error_message}",
            category=category,
            exc_info=True,
            error_type=error_type,
            context=context or {},
            error_count=self.error_counts.get(error_type, 0)
        )

        # Attempt recovery if enabled
        if attempt_recovery and error_type in self.recovery_strategies:
            try:
                self.logger.info(
                    f"Attempting recovery for {error_type}",
                    category=category,
                    error_type=error_type
                )

                recovery_success = self.recovery_strategies[error_type](error, context)

                if recovery_success:
                    self.logger.info(
                        f"Recovery successful for {error_type}",
                        category=category,
                        error_type=error_type
                    )
                    return True
                else:
                    self.logger.warning(
                        f"Recovery failed for {error_type}",
                        category=category,
                        error_type=error_type
                    )

            except Exception as recovery_error:
                self.logger.critical(
                    f"Recovery strategy failed: {recovery_error}",
                    category=category,
                    exc_info=True,
                    original_error=error_type,
                    recovery_error=str(recovery_error)
                )

        return False

    def _track_error_frequency(self, error_type: str):
        """Track error frequency for monitoring."""
        current_time = time.time()

        # Increment error count
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

        # Track timestamps for frequency analysis
        if error_type not in self.error_timestamps:
            self.error_timestamps[error_type] = []

        self.error_timestamps[error_type].append(current_time)

        # Keep only last hour of timestamps
        one_hour_ago = current_time - 3600
        self.error_timestamps[error_type] = [
            ts for ts in self.error_timestamps[error_type]
            if ts > one_hour_ago
        ]

        # Check for error storm (>10 errors in 5 minutes)
        five_minutes_ago = current_time - 300
        recent_errors = len([
            ts for ts in self.error_timestamps[error_type]
            if ts > five_minutes_ago
        ])

        if recent_errors > 10:
            self.logger.critical(
                f"Error storm detected: {recent_errors} {error_type} errors in 5 minutes",
                category=LogCategory.SYSTEM,
                error_type=error_type,
                recent_error_count=recent_errors
            )

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        current_time = time.time()
        one_hour_ago = current_time - 3600

        stats = {
            'total_errors': sum(self.error_counts.values()),
            'error_types': len(self.error_counts),
            'errors_last_hour': {},
            'most_frequent_errors': []
        }

        # Calculate errors in last hour
        for error_type, timestamps in self.error_timestamps.items():
            recent_count = len([ts for ts in timestamps if ts > one_hour_ago])
            if recent_count > 0:
                stats['errors_last_hour'][error_type] = recent_count

        # Find most frequent errors
        sorted_errors = sorted(
            self.error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        stats['most_frequent_errors'] = sorted_errors[:5]

        return stats


class PerformanceLogger:
    """Logger for performance metrics and profiling."""

    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.active_operations: Dict[str, Dict[str, Any]] = {}

    def start_operation(self, operation_id: str, operation_name: str, **metadata):
        """Start tracking a performance operation."""
        self.active_operations[operation_id] = {
            'name': operation_name,
            'start_time': time.time(),
            'metadata': metadata
        }

        self.logger.debug(
            f"Started operation: {operation_name}",
            category=LogCategory.PERFORMANCE,
            operation_id=operation_id,
            operation_name=operation_name,
            **metadata
        )

    def end_operation(self, operation_id: str, success: bool = True, **result_metadata):
        """End tracking a performance operation."""
        if operation_id not in self.active_operations:
            self.logger.warning(
                f"Attempted to end unknown operation: {operation_id}",
                category=LogCategory.PERFORMANCE,
                operation_id=operation_id
            )
            return

        operation = self.active_operations.pop(operation_id)
        end_time = time.time()
        duration = end_time - operation['start_time']

        self.logger.info(
            f"Completed operation: {operation['name']}",
            category=LogCategory.PERFORMANCE,
            operation_id=operation_id,
            operation_name=operation['name'],
            duration_seconds=duration,
            success=success,
            **operation['metadata'],
            **result_metadata
        )

        # Log warning for slow operations
        if duration > 5.0:  # 5 seconds
            self.logger.warning(
                f"Slow operation detected: {operation['name']} took {duration:.2f}s",
                category=LogCategory.PERFORMANCE,
                operation_id=operation_id,
                duration_seconds=duration
            )

    def log_metric(self, metric_name: str, value: Union[int, float], unit: str = "", **metadata):
        """Log a performance metric."""
        self.logger.info(
            f"Performance metric: {metric_name} = {value}{unit}",
            category=LogCategory.PERFORMANCE,
            metric_name=metric_name,
            metric_value=value,
            metric_unit=unit,
            **metadata
        )


def exception_handler(logger: StructuredLogger, category: LogCategory = LogCategory.SYSTEM):
    """Decorator for automatic exception handling and logging."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Exception in {func.__name__}: {str(e)}",
                    category=category,
                    exc_info=True,
                    function_name=func.__name__,
                    args_count=len(args),
                    kwargs_keys=list(kwargs.keys())
                )
                raise
        return wrapper
    return decorator


def log_function_calls(logger: StructuredLogger, level: LogLevel = LogLevel.DEBUG):
    """Decorator to log function calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(
                f"Calling function: {func.__name__}",
                category=LogCategory.SYSTEM,
                function_name=func.__name__,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                logger.debug(
                    f"Function completed: {func.__name__}",
                    category=LogCategory.SYSTEM,
                    function_name=func.__name__,
                    duration_seconds=duration,
                    success=True
                )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Function failed: {func.__name__}",
                    category=LogCategory.SYSTEM,
                    function_name=func.__name__,
                    duration_seconds=duration,
                    success=False,
                    error=str(e),
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


# Global logger instances
main_logger = StructuredLogger("moni.main")
security_system_logger = StructuredLogger("moni.security")
performance_logger_instance = PerformanceLogger(StructuredLogger("moni.performance"))
error_handler = ErrorHandler(main_logger)

# Default recovery strategies
def default_memory_error_recovery(error: Exception, context: Optional[Dict[str, Any]]) -> bool:
    """Default recovery strategy for memory errors."""
    try:
        import gc
        gc.collect()
        main_logger.info("Memory cleanup performed", category=LogCategory.SYSTEM)
        return True
    except Exception:
        return False

def default_network_error_recovery(error: Exception, context: Optional[Dict[str, Any]]) -> bool:
    """Default recovery strategy for network errors."""
    try:
        import time
        time.sleep(1)  # Brief pause before retry
        main_logger.info("Network retry delay applied", category=LogCategory.NETWORK)
        return True
    except Exception:
        return False

# Register default recovery strategies
error_handler.register_recovery_strategy("MemoryError", default_memory_error_recovery)
error_handler.register_recovery_strategy("ConnectionError", default_network_error_recovery)
error_handler.register_recovery_strategy("TimeoutError", default_network_error_recovery)