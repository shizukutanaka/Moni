"""
Comprehensive error handling and recovery system for production-grade stability.
Provides graceful error handling, automatic recovery, and system resilience.
"""

from __future__ import annotations

import sys
import traceback
import logging
import threading
import time
import signal
import gc
import weakref
from typing import Dict, Any, Optional, List, Callable, Type, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque, defaultdict
import json
import pickle
import tempfile
import shutil
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RETRY = "retry"
    RESTART_COMPONENT = "restart_component"
    RESTART_APPLICATION = "restart_application"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    NOTIFY_USER = "notify_user"
    IGNORE = "ignore"


@dataclass
class ErrorContext:
    """Detailed error context information."""
    timestamp: datetime
    error_type: str
    error_message: str
    severity: ErrorSeverity
    traceback: str
    component: str
    thread_id: int
    process_id: int
    system_state: Dict[str, Any] = field(default_factory=dict)
    user_context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3


@dataclass
class RecoveryAction:
    """Recovery action definition."""
    strategy: RecoveryStrategy
    handler: Callable[[ErrorContext], bool]
    condition: Callable[[ErrorContext], bool]
    priority: int = 50
    max_attempts: int = 3
    cooldown_seconds: int = 60


@dataclass
class ComponentHealth:
    """Component health status."""
    name: str
    status: str  # 'healthy', 'degraded', 'failed'
    last_error: Optional[ErrorContext] = None
    error_count: int = 0
    last_restart: Optional[datetime] = None
    restart_count: int = 0
    uptime_seconds: float = 0.0


class SystemCheckpoint:
    """System state checkpoint for recovery."""

    def __init__(self):
        self.checkpoint_data: Dict[str, Any] = {}
        self.checkpoint_time: Optional[datetime] = None
        self.checkpoint_file: Optional[Path] = None

    def create_checkpoint(self, data: Dict[str, Any], checkpoint_dir: Path) -> bool:
        """Create a system checkpoint."""
        try:
            self.checkpoint_time = datetime.now()
            self.checkpoint_data = data.copy()

            # Create checkpoint file
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            timestamp = self.checkpoint_time.strftime("%Y%m%d_%H%M%S")
            self.checkpoint_file = checkpoint_dir / f"checkpoint_{timestamp}.pkl"

            # Serialize checkpoint data
            with open(self.checkpoint_file, 'wb') as f:
                pickle.dump({
                    'timestamp': self.checkpoint_time,
                    'data': self.checkpoint_data
                }, f)

            logger.info(f"System checkpoint created: {self.checkpoint_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return False

    def restore_checkpoint(self, checkpoint_file: Path) -> Optional[Dict[str, Any]]:
        """Restore from checkpoint."""
        try:
            if not checkpoint_file.exists():
                return None

            with open(checkpoint_file, 'rb') as f:
                checkpoint = pickle.load(f)

            self.checkpoint_time = checkpoint['timestamp']
            self.checkpoint_data = checkpoint['data']
            self.checkpoint_file = checkpoint_file

            logger.info(f"System restored from checkpoint: {checkpoint_file}")
            return self.checkpoint_data

        except Exception as e:
            logger.error(f"Failed to restore checkpoint {checkpoint_file}: {e}")
            return None

    def cleanup_old_checkpoints(self, checkpoint_dir: Path, max_age_days: int = 7) -> None:
        """Clean up old checkpoint files."""
        try:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            for checkpoint_file in checkpoint_dir.glob("checkpoint_*.pkl"):
                try:
                    file_time = datetime.fromtimestamp(checkpoint_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        checkpoint_file.unlink()
                        logger.debug(f"Removed old checkpoint: {checkpoint_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove old checkpoint {checkpoint_file}: {e}")

        except Exception as e:
            logger.error(f"Failed to cleanup old checkpoints: {e}")


class ErrorHandler:
    """Advanced error handler with context and recovery."""

    def __init__(self):
        self.error_history: deque = deque(maxlen=1000)
        self.recovery_actions: List[RecoveryAction] = []
        self.component_health: Dict[str, ComponentHealth] = {}
        self.error_patterns: Dict[str, List[ErrorContext]] = defaultdict(list)
        self.recovery_cooldowns: Dict[str, float] = {}
        self.system_checkpoint = SystemCheckpoint()

        # Error statistics
        self.error_stats: Dict[str, int] = defaultdict(int)
        self.recovery_stats: Dict[str, int] = defaultdict(int)

        # Monitoring
        self.monitoring_enabled = True
        self.health_check_interval = 30.0  # seconds

        # Setup default recovery actions
        self._setup_default_recovery_actions()

    def _setup_default_recovery_actions(self) -> None:
        """Set up default recovery actions."""
        # Memory cleanup for memory errors
        self.add_recovery_action(RecoveryAction(
            strategy=RecoveryStrategy.RETRY,
            handler=self._memory_cleanup_handler,
            condition=lambda ctx: "memory" in ctx.error_message.lower() or "MemoryError" in ctx.error_type,
            priority=80,
            max_attempts=2
        ))

        # Restart component for recurring errors
        self.add_recovery_action(RecoveryAction(
            strategy=RecoveryStrategy.RESTART_COMPONENT,
            handler=self._restart_component_handler,
            condition=lambda ctx: ctx.recovery_attempts >= 2,
            priority=60,
            max_attempts=1
        ))

        # Graceful degradation for non-critical errors
        self.add_recovery_action(RecoveryAction(
            strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
            handler=self._graceful_degradation_handler,
            condition=lambda ctx: ctx.severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM],
            priority=40
        ))

        # User notification for critical errors
        self.add_recovery_action(RecoveryAction(
            strategy=RecoveryStrategy.NOTIFY_USER,
            handler=self._notify_user_handler,
            condition=lambda ctx: ctx.severity == ErrorSeverity.CRITICAL,
            priority=90
        ))

    def add_recovery_action(self, action: RecoveryAction) -> None:
        """Add a recovery action."""
        self.recovery_actions.append(action)
        self.recovery_actions.sort(key=lambda x: x.priority, reverse=True)

    def handle_error(self, error: Exception, component: str = "unknown",
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    user_context: Optional[Dict[str, Any]] = None) -> bool:
        """Handle an error with context and recovery."""
        try:
            # Create error context
            error_context = ErrorContext(
                timestamp=datetime.now(),
                error_type=type(error).__name__,
                error_message=str(error),
                severity=severity,
                traceback=traceback.format_exc(),
                component=component,
                thread_id=threading.get_ident(),
                process_id=sys.maxsize,  # Simplified process ID
                system_state=self._capture_system_state(),
                user_context=user_context or {}
            )

            # Log error
            self._log_error(error_context)

            # Add to history and patterns
            self.error_history.append(error_context)
            self.error_patterns[error_context.error_type].append(error_context)
            self.error_stats[error_context.error_type] += 1

            # Update component health
            self._update_component_health(component, error_context)

            # Attempt recovery
            recovery_success = self._attempt_recovery(error_context)

            # Update recovery statistics
            if recovery_success:
                self.recovery_stats["successful"] += 1
                logger.info(f"Successfully recovered from {error_context.error_type} in {component}")
            else:
                self.recovery_stats["failed"] += 1
                logger.error(f"Failed to recover from {error_context.error_type} in {component}")

            return recovery_success

        except Exception as e:
            # Prevent recursive error handling
            logger.critical(f"Error in error handler: {e}")
            return False

    def _capture_system_state(self) -> Dict[str, Any]:
        """Capture current system state."""
        try:
            import psutil

            return {
                'memory_percent': psutil.virtual_memory().percent,
                'cpu_percent': psutil.cpu_percent(),
                'thread_count': threading.active_count(),
                'gc_counts': gc.get_count(),
                'timestamp': time.time()
            }
        except Exception:
            return {'timestamp': time.time()}

    def _log_error(self, error_context: ErrorContext) -> None:
        """Log error with appropriate level."""
        log_message = (
            f"Error in {error_context.component}: {error_context.error_type} - "
            f"{error_context.error_message}"
        )

        if error_context.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif error_context.severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Log full traceback at debug level
        logger.debug(f"Full traceback:\n{error_context.traceback}")

    def _update_component_health(self, component: str, error_context: ErrorContext) -> None:
        """Update component health status."""
        if component not in self.component_health:
            self.component_health[component] = ComponentHealth(
                name=component,
                status="healthy"
            )

        health = self.component_health[component]
        health.last_error = error_context
        health.error_count += 1

        # Determine health status based on error frequency and severity
        if error_context.severity == ErrorSeverity.CRITICAL:
            health.status = "failed"
        elif health.error_count >= 5:  # Too many errors
            health.status = "degraded"
        elif error_context.severity == ErrorSeverity.HIGH:
            health.status = "degraded"

    def _attempt_recovery(self, error_context: ErrorContext) -> bool:
        """Attempt to recover from the error."""
        # Check cooldown periods
        recovery_key = f"{error_context.component}:{error_context.error_type}"
        current_time = time.time()

        if recovery_key in self.recovery_cooldowns:
            if current_time < self.recovery_cooldowns[recovery_key]:
                logger.debug(f"Recovery for {recovery_key} is in cooldown")
                return False

        # Find applicable recovery actions
        applicable_actions = [
            action for action in self.recovery_actions
            if action.condition(error_context) and error_context.recovery_attempts < action.max_attempts
        ]

        if not applicable_actions:
            logger.warning(f"No applicable recovery actions for {error_context.error_type}")
            return False

        # Try recovery actions in priority order
        for action in applicable_actions:
            try:
                logger.info(f"Attempting recovery strategy: {action.strategy.value}")
                error_context.recovery_attempts += 1

                success = action.handler(error_context)

                if success:
                    logger.info(f"Recovery successful using strategy: {action.strategy.value}")
                    return True
                else:
                    # Set cooldown if recovery failed
                    self.recovery_cooldowns[recovery_key] = current_time + action.cooldown_seconds

            except Exception as e:
                logger.error(f"Recovery action {action.strategy.value} failed: {e}")

        return False

    def _memory_cleanup_handler(self, error_context: ErrorContext) -> bool:
        """Handle memory-related errors."""
        try:
            # Force garbage collection
            collected = gc.collect()
            logger.info(f"Memory cleanup: collected {collected} objects")

            # Clear caches if available
            # This would be customized based on your application's caches

            return True

        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
            return False

    def _restart_component_handler(self, error_context: ErrorContext) -> bool:
        """Handle component restart."""
        try:
            component = error_context.component
            health = self.component_health.get(component)

            if health:
                health.last_restart = datetime.now()
                health.restart_count += 1
                health.status = "healthy"  # Reset status after restart
                health.error_count = 0  # Reset error count

            logger.info(f"Component {component} marked for restart")

            # The actual restart logic would be implemented by the component
            # This handler just marks it for restart
            return True

        except Exception as e:
            logger.error(f"Component restart failed: {e}")
            return False

    def _graceful_degradation_handler(self, error_context: ErrorContext) -> bool:
        """Handle graceful degradation."""
        try:
            component = error_context.component
            health = self.component_health.get(component)

            if health:
                health.status = "degraded"

            logger.info(f"Component {component} entering degraded mode")

            # The actual degradation logic would be implemented by the component
            # This might involve disabling non-essential features
            return True

        except Exception as e:
            logger.error(f"Graceful degradation failed: {e}")
            return False

    def _notify_user_handler(self, error_context: ErrorContext) -> bool:
        """Handle user notification."""
        try:
            # Create user-friendly error message
            user_message = self._create_user_error_message(error_context)

            # Log for user notification system
            logger.error(f"USER_NOTIFICATION: {user_message}")

            # The actual notification would be handled by the UI layer
            return True

        except Exception as e:
            logger.error(f"User notification failed: {e}")
            return False

    def _create_user_error_message(self, error_context: ErrorContext) -> str:
        """Create user-friendly error message."""
        component_name = error_context.component.replace('_', ' ').title()

        if error_context.severity == ErrorSeverity.CRITICAL:
            return f"Critical error in {component_name}. The application may need to restart."
        elif error_context.severity == ErrorSeverity.HIGH:
            return f"Error in {component_name}. Some features may be temporarily unavailable."
        else:
            return f"Minor issue in {component_name}. Functionality may be reduced."

    @contextmanager
    def error_context(self, component: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                     user_context: Optional[Dict[str, Any]] = None):
        """Context manager for error handling."""
        try:
            yield
        except Exception as e:
            self.handle_error(e, component, severity, user_context)
            raise  # Re-raise unless specifically handled

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        total_errors = sum(self.error_stats.values())
        total_recoveries = sum(self.recovery_stats.values())

        return {
            'total_errors': total_errors,
            'total_recoveries': total_recoveries,
            'recovery_rate': (self.recovery_stats.get("successful", 0) / total_recoveries * 100) if total_recoveries > 0 else 0,
            'error_types': dict(self.error_stats),
            'recovery_stats': dict(self.recovery_stats),
            'component_health': {
                name: {
                    'status': health.status,
                    'error_count': health.error_count,
                    'restart_count': health.restart_count,
                    'last_error_time': health.last_error.timestamp.isoformat() if health.last_error else None
                }
                for name, health in self.component_health.items()
            },
            'recent_errors': [
                {
                    'timestamp': error.timestamp.isoformat(),
                    'type': error.error_type,
                    'component': error.component,
                    'severity': error.severity.value,
                    'message': error.error_message[:100] + '...' if len(error.error_message) > 100 else error.error_message
                }
                for error in list(self.error_history)[-10:]  # Last 10 errors
            ]
        }

    def export_error_report(self, file_path: Path) -> bool:
        """Export comprehensive error report."""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'statistics': self.get_error_statistics(),
                'error_patterns': {
                    error_type: [
                        {
                            'timestamp': error.timestamp.isoformat(),
                            'component': error.component,
                            'severity': error.severity.value,
                            'message': error.error_message,
                            'traceback': error.traceback
                        }
                        for error in errors[-5:]  # Last 5 of each type
                    ]
                    for error_type, errors in self.error_patterns.items()
                },
                'recovery_actions': [
                    {
                        'strategy': action.strategy.value,
                        'priority': action.priority,
                        'max_attempts': action.max_attempts,
                        'cooldown_seconds': action.cooldown_seconds
                    }
                    for action in self.recovery_actions
                ]
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"Error report exported to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export error report: {e}")
            return False

    def cleanup_error_history(self, max_age_days: int = 30) -> None:
        """Clean up old error history."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # Clean error history
        self.error_history = deque(
            (error for error in self.error_history if error.timestamp > cutoff_date),
            maxlen=self.error_history.maxlen
        )

        # Clean error patterns
        for error_type in list(self.error_patterns.keys()):
            self.error_patterns[error_type] = [
                error for error in self.error_patterns[error_type]
                if error.timestamp > cutoff_date
            ]
            if not self.error_patterns[error_type]:
                del self.error_patterns[error_type]

        logger.info(f"Cleaned up error history older than {max_age_days} days")


class SignalHandler:
    """Handle system signals for graceful shutdown."""

    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
        self.shutdown_handlers: List[Callable[[], None]] = []
        self.setup_signal_handlers()

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.graceful_shutdown()

        # Handle common shutdown signals
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
        else:
            # Windows signal handling
            signal.signal(signal.SIGINT, signal_handler)

    def add_shutdown_handler(self, handler: Callable[[], None]) -> None:
        """Add a shutdown handler."""
        self.shutdown_handlers.append(handler)

    def graceful_shutdown(self) -> None:
        """Perform graceful shutdown."""
        try:
            logger.info("Starting graceful shutdown sequence")

            # Run shutdown handlers
            for handler in self.shutdown_handlers:
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Error in shutdown handler: {e}")

            # Export final error report
            reports_dir = Path.home() / ".config" / "moni" / "error_reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"error_report_shutdown_{timestamp}.json"
            self.error_handler.export_error_report(report_file)

            logger.info("Graceful shutdown completed")

        except Exception as e:
            logger.critical(f"Error during graceful shutdown: {e}")


class ErrorRecoveryManager:
    """Main error recovery management system."""

    def __init__(self):
        self.error_handler = ErrorHandler()
        self.signal_handler = SignalHandler(self.error_handler)
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False

        # Setup checkpoint directory
        self.checkpoint_dir = Path.home() / ".config" / "moni" / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def start_monitoring(self) -> None:
        """Start error monitoring and health checks."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Error recovery monitoring started")

    def stop_monitoring(self) -> None:
        """Stop error monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Error recovery monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Health checks for all components
                self._perform_health_checks()

                # Cleanup old data
                self._periodic_cleanup()

                # Sleep until next check
                time.sleep(self.error_handler.health_check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Brief pause before retrying

    def _perform_health_checks(self) -> None:
        """Perform health checks on all components."""
        for component_name, health in self.error_handler.component_health.items():
            try:
                # Check if component needs restart
                if health.status == "failed" and health.restart_count < 3:
                    logger.warning(f"Component {component_name} marked for restart due to failed status")
                    # Actual restart logic would be implemented here

                # Check for too many errors
                elif health.error_count > 10:
                    logger.warning(f"Component {component_name} has excessive errors ({health.error_count})")

            except Exception as e:
                logger.error(f"Health check failed for {component_name}: {e}")

    def _periodic_cleanup(self) -> None:
        """Perform periodic cleanup tasks."""
        try:
            # Clean old error history
            self.error_handler.cleanup_error_history()

            # Clean old checkpoints
            self.error_handler.system_checkpoint.cleanup_old_checkpoints(self.checkpoint_dir)

        except Exception as e:
            logger.error(f"Periodic cleanup failed: {e}")

    def create_system_checkpoint(self, data: Dict[str, Any]) -> bool:
        """Create a system checkpoint."""
        return self.error_handler.system_checkpoint.create_checkpoint(data, self.checkpoint_dir)

    def restore_from_checkpoint(self, checkpoint_file: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Restore system from checkpoint."""
        if checkpoint_file is None:
            # Find latest checkpoint
            checkpoints = list(self.checkpoint_dir.glob("checkpoint_*.pkl"))
            if not checkpoints:
                return None
            checkpoint_file = max(checkpoints, key=lambda p: p.stat().st_mtime)

        return self.error_handler.system_checkpoint.restore_checkpoint(checkpoint_file)

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            'error_recovery': {
                'monitoring_active': self.monitoring_active,
                'total_components': len(self.error_handler.component_health),
                'healthy_components': len([
                    h for h in self.error_handler.component_health.values()
                    if h.status == "healthy"
                ]),
                'degraded_components': len([
                    h for h in self.error_handler.component_health.values()
                    if h.status == "degraded"
                ]),
                'failed_components': len([
                    h for h in self.error_handler.component_health.values()
                    if h.status == "failed"
                ])
            },
            'statistics': self.error_handler.get_error_statistics(),
            'checkpoints': {
                'available': len(list(self.checkpoint_dir.glob("checkpoint_*.pkl"))),
                'latest': max(
                    (p.stat().st_mtime for p in self.checkpoint_dir.glob("checkpoint_*.pkl")),
                    default=None
                )
            }
        }


# Global error recovery manager instance
error_recovery_manager = ErrorRecoveryManager()