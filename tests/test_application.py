"""
Comprehensive test suite for the main application module.
Tests the MoniApplication class and its core functionality.
"""

import pytest
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from moni.application import MoniApplication, MoniContext
from moni.config import Config
from moni.metrics import MetricRegistry, MetricHistory


class TestMoniContext:
    """Test the MoniContext dependency injection container."""

    def test_context_initialization(self):
        """Test that MoniContext initializes with correct dependencies."""
        context = MoniContext()

        assert context.config is not None
        assert context.metric_registry is not None
        assert context.metric_history is not None
        assert hasattr(context, 'performance_monitor')
        assert hasattr(context, 'error_recovery_manager')

    def test_context_singleton_behavior(self):
        """Test that MoniContext maintains singleton behavior for shared components."""
        context1 = MoniContext()
        context2 = MoniContext()

        # Config should be the same instance
        assert context1.config is context2.config
        assert context1.metric_registry is context2.metric_registry


class TestMoniApplication:
    """Test suite for MoniApplication class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_context(self):
        """Create a mock MoniContext for testing."""
        context = Mock(spec=MoniContext)
        context.config = Mock(spec=Config)
        context.metric_registry = Mock(spec=MetricRegistry)
        context.metric_history = Mock(spec=MetricHistory)
        context.performance_monitor = Mock()
        context.error_recovery_manager = Mock()
        return context

    @pytest.fixture
    def app(self, mock_context):
        """Create MoniApplication instance for testing."""
        with patch('moni.application.MoniContext', return_value=mock_context):
            return MoniApplication()

    def test_application_initialization(self, app):
        """Test application initializes correctly."""
        assert app.context is not None
        assert app.running is False
        assert app.main_window is None
        assert app.tray_icon is None

    def test_application_start_stop(self, app):
        """Test application start and stop functionality."""
        # Mock the UI components
        app.main_window = Mock()
        app.tray_icon = Mock()

        # Test start
        app.start()
        assert app.running is True
        app.context.performance_monitor.start_monitoring.assert_called_once()
        app.context.error_recovery_manager.start_monitoring.assert_called_once()

        # Test stop
        app.stop()
        assert app.running is False
        app.context.performance_monitor.stop_monitoring.assert_called_once()
        app.context.error_recovery_manager.stop_monitoring.assert_called_once()

    def test_config_loading(self, app, temp_config_dir):
        """Test configuration loading."""
        config_file = temp_config_dir / "test_config.json"
        config_file.write_text('{"monitoring": {"interval_ms": 2000}}')

        app.load_config(config_file)
        app.context.config.load_from_file.assert_called_once_with(config_file)

    def test_plugin_loading(self, app):
        """Test plugin loading functionality."""
        mock_plugin = Mock()
        mock_plugin.name = "test_plugin"
        mock_plugin.version = "1.0.0"

        with patch('moni.application.load_plugins', return_value=[mock_plugin]):
            loaded_plugins = app.load_plugins()

        assert len(loaded_plugins) == 1
        assert loaded_plugins[0].name == "test_plugin"

    def test_metric_collection_start_stop(self, app):
        """Test metric collection lifecycle."""
        app.start_metric_collection()
        app.context.metric_registry.start_collection.assert_called_once()

        app.stop_metric_collection()
        app.context.metric_registry.stop_collection.assert_called_once()

    def test_application_error_handling(self, app):
        """Test application error handling."""
        test_error = RuntimeError("Test error")

        # Mock error handler
        app.context.error_recovery_manager.handle_error = Mock()

        # Trigger error handling
        app.handle_application_error(test_error, "test_component")

        app.context.error_recovery_manager.handle_error.assert_called_once()

    @patch('moni.application.QApplication')
    def test_ui_initialization(self, mock_qapp, app):
        """Test UI initialization."""
        mock_qapp_instance = Mock()
        mock_qapp.return_value = mock_qapp_instance

        app.initialize_ui()

        mock_qapp.assert_called_once()
        assert app.qt_app is not None

    def test_tray_icon_creation(self, app):
        """Test system tray icon creation."""
        with patch('moni.application.QSystemTrayIcon') as mock_tray:
            mock_tray_instance = Mock()
            mock_tray.return_value = mock_tray_instance

            app.create_tray_icon()

            assert app.tray_icon is not None
            mock_tray_instance.show.assert_called_once()

    def test_graceful_shutdown(self, app):
        """Test graceful shutdown process."""
        app.running = True
        app.main_window = Mock()
        app.tray_icon = Mock()

        # Start shutdown
        app.graceful_shutdown()

        # Verify shutdown sequence
        app.context.performance_monitor.stop_monitoring.assert_called_once()
        app.context.error_recovery_manager.stop_monitoring.assert_called_once()
        assert app.running is False

    def test_application_recovery_after_crash(self, app):
        """Test application recovery mechanisms."""
        # Simulate a crash scenario
        app.running = True
        app.context.error_recovery_manager.restore_from_checkpoint = Mock(return_value={'test': 'data'})

        recovered_data = app.recover_from_crash()

        assert recovered_data is not None
        app.context.error_recovery_manager.restore_from_checkpoint.assert_called_once()

    def test_configuration_hot_reload(self, app):
        """Test configuration hot reloading."""
        # Mock configuration change callback
        app.context.config.add_change_callback = Mock()

        def test_callback(change):
            pass

        app.setup_config_hot_reload(test_callback)
        app.context.config.add_change_callback.assert_called_once_with(test_callback)

    def test_performance_monitoring_integration(self, app):
        """Test performance monitoring integration."""
        # Mock performance metrics
        mock_metrics = {
            'cpu_usage': 45.0,
            'memory_usage': 512.0,
            'active_threads': 8
        }

        app.context.performance_monitor.get_performance_report = Mock(return_value=mock_metrics)

        report = app.get_performance_status()
        assert report == mock_metrics

    def test_security_context_integration(self, app):
        """Test security context integration."""
        # Test security context creation
        security_context = app.create_security_context("test_user", "test_operation")

        assert security_context is not None
        assert hasattr(security_context, 'user_id')
        assert hasattr(security_context, 'operation')

    def test_concurrent_operations(self, app):
        """Test concurrent operation handling."""
        results = []

        def worker_task(task_id):
            time.sleep(0.1)  # Simulate work
            results.append(f"task_{task_id}")

        # Start multiple concurrent tasks
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_task, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        assert len(results) == 5
        assert all(f"task_{i}" in results for i in range(5))

    def test_memory_usage_optimization(self, app):
        """Test memory usage optimization."""
        # Create large data structure
        large_data = list(range(100000))

        # Test memory cleanup
        app.context.performance_monitor.memory_profiler = Mock()
        app.context.performance_monitor.memory_profiler.cleanup_memory = Mock()

        app.optimize_memory_usage()

        app.context.performance_monitor.memory_profiler.cleanup_memory.assert_called_once()

    def test_application_state_persistence(self, app, temp_config_dir):
        """Test application state persistence."""
        state_file = temp_config_dir / "app_state.json"

        # Test state saving
        test_state = {"window_position": [100, 200], "theme": "dark"}
        app.save_application_state(test_state, state_file)

        assert state_file.exists()

        # Test state loading
        loaded_state = app.load_application_state(state_file)
        assert loaded_state == test_state

    def test_plugin_error_isolation(self, app):
        """Test plugin error isolation."""
        # Create a failing plugin
        failing_plugin = Mock()
        failing_plugin.initialize.side_effect = RuntimeError("Plugin failed")
        failing_plugin.name = "failing_plugin"

        # Test that plugin errors don't crash the application
        with patch('moni.application.load_plugins', return_value=[failing_plugin]):
            loaded_plugins = app.load_plugins_safely()

        # Application should continue running despite plugin failure
        assert app.running is False  # Should still be False since we didn't start
        # Plugin should not be in loaded plugins due to error
        assert len(loaded_plugins) == 0

    def test_configuration_validation(self, app):
        """Test configuration validation."""
        # Test valid configuration
        valid_config = {
            "monitoring": {"interval_ms": 1000},
            "security": {"encryption_enabled": True}
        }

        app.context.config.validate = Mock(return_value=True)
        assert app.validate_configuration(valid_config) is True

        # Test invalid configuration
        invalid_config = {
            "monitoring": {"interval_ms": -1}  # Invalid value
        }

        app.context.config.validate = Mock(return_value=False)
        assert app.validate_configuration(invalid_config) is False

    def test_resource_cleanup_on_exit(self, app):
        """Test proper resource cleanup on application exit."""
        # Setup resources
        app.running = True
        app.main_window = Mock()
        app.tray_icon = Mock()
        app.qt_app = Mock()

        # Mock cleanup methods
        app.context.metric_registry.cleanup = Mock()
        app.context.performance_monitor.cleanup = Mock()
        app.context.error_recovery_manager.cleanup = Mock()

        # Perform cleanup
        app.cleanup_resources()

        # Verify all resources are cleaned up
        app.context.metric_registry.cleanup.assert_called_once()
        app.context.performance_monitor.cleanup.assert_called_once()
        app.context.error_recovery_manager.cleanup.assert_called_once()


class TestApplicationIntegration:
    """Integration tests for MoniApplication."""

    @pytest.fixture
    def real_app(self):
        """Create a real MoniApplication instance for integration testing."""
        app = MoniApplication()
        yield app
        # Cleanup
        if app.running:
            app.stop()

    def test_full_application_lifecycle(self, real_app):
        """Test complete application lifecycle."""
        # Start application
        real_app.start()
        assert real_app.running is True

        # Verify services are running
        time.sleep(0.1)  # Brief pause for startup

        # Stop application
        real_app.stop()
        assert real_app.running is False

    def test_configuration_integration(self, real_app):
        """Test configuration system integration."""
        # Test that configuration is properly loaded
        config = real_app.context.config
        assert config is not None

        # Test configuration access
        monitoring_interval = config.get('monitoring.interval_ms', 1000)
        assert isinstance(monitoring_interval, int)
        assert monitoring_interval > 0

    def test_metrics_integration(self, real_app):
        """Test metrics system integration."""
        # Start application
        real_app.start()

        # Start metric collection
        real_app.start_metric_collection()

        # Wait briefly for metrics to be collected
        time.sleep(0.5)

        # Verify metrics are being collected
        registry = real_app.context.metric_registry
        assert len(registry._metrics) > 0

        # Stop metric collection
        real_app.stop_metric_collection()
        real_app.stop()

    @pytest.mark.performance
    def test_application_performance(self, real_app):
        """Test application performance characteristics."""
        import psutil
        process = psutil.Process()

        # Measure startup time
        start_time = time.time()
        real_app.start()
        startup_time = time.time() - start_time

        # Startup should be reasonably fast
        assert startup_time < 5.0, f"Startup took {startup_time:.2f}s, should be < 5s"

        # Measure memory usage
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        assert memory_usage < 200, f"Memory usage {memory_usage:.1f}MB is too high"

        real_app.stop()

    @pytest.mark.security
    def test_security_integration(self, real_app):
        """Test security system integration."""
        # Test security context creation
        from moni.government_security import SecurityLevel

        context = real_app.create_security_context(
            user_id="test_user",
            operation="test_operation",
            clearance_level=SecurityLevel.CONFIDENTIAL
        )

        assert context is not None
        assert context.user_id == "test_user"
        assert context.clearance_level == SecurityLevel.CONFIDENTIAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])