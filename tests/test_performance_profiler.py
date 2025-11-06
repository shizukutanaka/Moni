"""
Comprehensive test suite for the performance profiling system.
Tests the PerformanceMonitor and related performance optimization components.
"""

import pytest
import threading
import time
import psutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from collections import deque

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from moni.performance_profiler import (
    PerformanceMonitor,
    MemoryProfiler,
    CPUProfiler,
    PerformanceOptimizer,
    PerformanceAlert,
    SystemResourceMonitor
)


class TestPerformanceMonitor:
    """Test suite for PerformanceMonitor class."""

    @pytest.fixture
    def performance_monitor(self):
        """Create PerformanceMonitor instance for testing."""
        return PerformanceMonitor()

    def test_initialization(self, performance_monitor):
        """Test PerformanceMonitor initialization."""
        assert performance_monitor.is_monitoring is False
        assert performance_monitor.monitoring_interval == 1.0
        assert performance_monitor._monitoring_thread is None
        assert len(performance_monitor._performance_history) == 0

    def test_start_monitoring(self, performance_monitor):
        """Test starting performance monitoring."""
        performance_monitor.start_monitoring(interval_seconds=0.1)

        assert performance_monitor.is_monitoring is True
        assert performance_monitor._monitoring_thread is not None
        assert performance_monitor._monitoring_thread.is_alive()

        # Let it collect some data
        time.sleep(0.3)

        # Stop monitoring
        performance_monitor.stop_monitoring()

        assert performance_monitor.is_monitoring is False
        assert len(performance_monitor._performance_history) > 0

    def test_stop_monitoring(self, performance_monitor):
        """Test stopping performance monitoring."""
        performance_monitor.start_monitoring(interval_seconds=0.1)
        time.sleep(0.2)

        performance_monitor.stop_monitoring()

        assert performance_monitor.is_monitoring is False
        assert not performance_monitor._monitoring_thread.is_alive()

    def test_get_current_metrics(self, performance_monitor):
        """Test getting current performance metrics."""
        metrics = performance_monitor.get_current_metrics()

        required_keys = ['cpu_percent', 'memory_percent', 'memory_used_mb', 'timestamp']
        for key in required_keys:
            assert key in metrics

        assert 0 <= metrics['cpu_percent'] <= 100
        assert 0 <= metrics['memory_percent'] <= 100
        assert metrics['memory_used_mb'] > 0

    def test_get_performance_report(self, performance_monitor):
        """Test getting comprehensive performance report."""
        # Start monitoring to collect some data
        performance_monitor.start_monitoring(interval_seconds=0.1)
        time.sleep(0.3)
        performance_monitor.stop_monitoring()

        report = performance_monitor.get_performance_report()

        assert 'summary' in report
        assert 'history' in report
        assert 'alerts' in report
        assert 'recommendations' in report

        # Check summary data
        summary = report['summary']
        assert 'avg_cpu' in summary
        assert 'avg_memory' in summary
        assert 'peak_cpu' in summary
        assert 'peak_memory' in summary

    def test_set_alert_thresholds(self, performance_monitor):
        """Test setting performance alert thresholds."""
        thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 90.0,
            'memory_used_mb': 1000.0
        }

        performance_monitor.set_alert_thresholds(thresholds)

        assert performance_monitor._alert_thresholds == thresholds

    def test_performance_alerts(self, performance_monitor):
        """Test performance alert generation."""
        # Set low thresholds to trigger alerts
        thresholds = {
            'cpu_percent': 0.1,  # Very low threshold
            'memory_percent': 0.1
        }
        performance_monitor.set_alert_thresholds(thresholds)

        # Start monitoring
        performance_monitor.start_monitoring(interval_seconds=0.1)
        time.sleep(0.3)
        performance_monitor.stop_monitoring()

        # Check if alerts were generated
        alerts = performance_monitor.get_active_alerts()
        assert len(alerts) > 0

    def test_memory_profiling_integration(self, performance_monitor):
        """Test integration with memory profiler."""
        # Create memory profiler
        memory_profiler = MemoryProfiler()
        performance_monitor.set_memory_profiler(memory_profiler)

        # Start profiling
        memory_profiler.start_profiling()

        # Allocate some memory
        large_list = [i for i in range(10000)]

        # Stop profiling
        profile_data = memory_profiler.stop_profiling()

        assert profile_data is not None
        assert 'peak_memory_mb' in profile_data
        assert 'memory_growth_mb' in profile_data

    def test_cpu_profiling_integration(self, performance_monitor):
        """Test integration with CPU profiler."""
        cpu_profiler = CPUProfiler()
        performance_monitor.set_cpu_profiler(cpu_profiler)

        # Start profiling
        cpu_profiler.start_profiling()

        # CPU intensive task
        def cpu_intensive_task():
            total = 0
            for i in range(100000):
                total += i * i
            return total

        result = cpu_intensive_task()

        # Stop profiling
        profile_data = cpu_profiler.stop_profiling()

        assert profile_data is not None
        assert 'total_time' in profile_data
        assert 'function_stats' in profile_data

    def test_performance_optimization_suggestions(self, performance_monitor):
        """Test performance optimization suggestions."""
        # Start monitoring to collect baseline data
        performance_monitor.start_monitoring(interval_seconds=0.1)
        time.sleep(0.3)
        performance_monitor.stop_monitoring()

        suggestions = performance_monitor.get_optimization_suggestions()

        assert isinstance(suggestions, list)
        for suggestion in suggestions:
            assert 'category' in suggestion
            assert 'description' in suggestion
            assert 'impact' in suggestion


class TestMemoryProfiler:
    """Test suite for MemoryProfiler class."""

    @pytest.fixture
    def memory_profiler(self):
        """Create MemoryProfiler instance for testing."""
        return MemoryProfiler()

    def test_initialization(self, memory_profiler):
        """Test MemoryProfiler initialization."""
        assert memory_profiler.is_profiling is False
        assert memory_profiler._start_memory is None
        assert memory_profiler._peak_memory is None

    def test_start_stop_profiling(self, memory_profiler):
        """Test starting and stopping memory profiling."""
        # Start profiling
        memory_profiler.start_profiling()
        assert memory_profiler.is_profiling is True
        assert memory_profiler._start_memory is not None

        # Allocate memory
        large_data = [i for i in range(50000)]

        # Stop profiling
        profile_data = memory_profiler.stop_profiling()

        assert memory_profiler.is_profiling is False
        assert profile_data is not None
        assert 'peak_memory_mb' in profile_data
        assert 'memory_growth_mb' in profile_data
        assert profile_data['peak_memory_mb'] > 0

    def test_memory_snapshot(self, memory_profiler):
        """Test taking memory snapshots."""
        snapshot = memory_profiler.take_snapshot()

        assert 'timestamp' in snapshot
        assert 'memory_mb' in snapshot
        assert 'process_info' in snapshot
        assert snapshot['memory_mb'] > 0

    def test_memory_leak_detection(self, memory_profiler):
        """Test memory leak detection functionality."""
        memory_profiler.start_profiling()

        # Simulate memory leak by accumulating data
        leaked_data = []
        for i in range(10):
            leaked_data.extend([j for j in range(1000)])
            time.sleep(0.01)

        profile_data = memory_profiler.stop_profiling()

        # Check for memory growth
        assert profile_data['memory_growth_mb'] > 0

        # Test leak detection
        is_leak_detected = memory_profiler.detect_memory_leak(
            profile_data,
            growth_threshold_mb=1.0
        )

        assert isinstance(is_leak_detected, bool)

    def test_memory_optimization_recommendations(self, memory_profiler):
        """Test memory optimization recommendations."""
        memory_profiler.start_profiling()

        # Allocate and hold memory
        large_objects = []
        for i in range(100):
            large_objects.append([j for j in range(1000)])

        profile_data = memory_profiler.stop_profiling()

        recommendations = memory_profiler.get_optimization_recommendations(profile_data)

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

    def test_garbage_collection_analysis(self, memory_profiler):
        """Test garbage collection analysis."""
        import gc

        # Force garbage collection
        gc.collect()

        gc_stats = memory_profiler.analyze_garbage_collection()

        assert 'collections' in gc_stats
        assert 'collected_objects' in gc_stats
        assert isinstance(gc_stats['collections'], list)


class TestCPUProfiler:
    """Test suite for CPUProfiler class."""

    @pytest.fixture
    def cpu_profiler(self):
        """Create CPUProfiler instance for testing."""
        return CPUProfiler()

    def test_initialization(self, cpu_profiler):
        """Test CPUProfiler initialization."""
        assert cpu_profiler.is_profiling is False
        assert cpu_profiler._profiler is None

    def test_start_stop_profiling(self, cpu_profiler):
        """Test starting and stopping CPU profiling."""
        cpu_profiler.start_profiling()
        assert cpu_profiler.is_profiling is True

        # CPU intensive function
        def fibonacci(n):
            if n <= 1:
                return n
            return fibonacci(n-1) + fibonacci(n-2)

        result = fibonacci(20)

        profile_data = cpu_profiler.stop_profiling()

        assert cpu_profiler.is_profiling is False
        assert profile_data is not None
        assert 'total_time' in profile_data
        assert 'function_stats' in profile_data

    def test_profile_function_decorator(self, cpu_profiler):
        """Test function profiling decorator."""
        @cpu_profiler.profile_function
        def test_function(n):
            total = 0
            for i in range(n):
                total += i * i
            return total

        result = test_function(10000)

        # Check if profiling data was collected
        function_stats = cpu_profiler.get_function_stats()
        assert 'test_function' in str(function_stats)

    def test_hotspot_detection(self, cpu_profiler):
        """Test CPU hotspot detection."""
        cpu_profiler.start_profiling()

        # Create functions with different CPU usage
        def fast_function():
            return sum(range(100))

        def slow_function():
            total = 0
            for i in range(10000):
                total += i * i
            return total

        fast_function()
        slow_function()

        profile_data = cpu_profiler.stop_profiling()
        hotspots = cpu_profiler.identify_hotspots(profile_data)

        assert isinstance(hotspots, list)
        assert len(hotspots) > 0

    def test_performance_regression_detection(self, cpu_profiler):
        """Test performance regression detection."""
        # Profile baseline performance
        baseline_stats = cpu_profiler.profile_baseline_performance()

        # Simulate performance regression
        def regression_function():
            time.sleep(0.1)  # Artificial delay
            return sum(range(1000))

        current_stats = cpu_profiler.profile_current_performance(regression_function)

        # Detect regression
        regression_detected = cpu_profiler.detect_performance_regression(
            baseline_stats,
            current_stats,
            threshold_percent=10.0
        )

        assert isinstance(regression_detected, bool)


class TestPerformanceOptimizer:
    """Test suite for PerformanceOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create PerformanceOptimizer instance for testing."""
        return PerformanceOptimizer()

    def test_optimization_analysis(self, optimizer):
        """Test performance optimization analysis."""
        # Mock performance data
        performance_data = {
            'cpu_usage': [80, 85, 90, 75],
            'memory_usage': [60, 65, 70, 55],
            'response_times': [0.1, 0.15, 0.2, 0.12]
        }

        analysis = optimizer.analyze_performance_data(performance_data)

        assert 'bottlenecks' in analysis
        assert 'recommendations' in analysis
        assert 'priority_score' in analysis

    def test_auto_optimization(self, optimizer):
        """Test automatic optimization features."""
        # Mock system state
        system_state = {
            'high_cpu_processes': ['process1', 'process2'],
            'memory_leaks': ['component1'],
            'slow_queries': ['query1', 'query2']
        }

        optimizations = optimizer.suggest_auto_optimizations(system_state)

        assert isinstance(optimizations, list)
        assert len(optimizations) > 0

        for optimization in optimizations:
            assert 'type' in optimization
            assert 'action' in optimization
            assert 'estimated_impact' in optimization

    def test_resource_limit_optimization(self, optimizer):
        """Test resource limit optimization."""
        current_limits = {
            'max_memory_mb': 1024,
            'max_cpu_percent': 80,
            'max_threads': 10
        }

        usage_stats = {
            'avg_memory_mb': 800,
            'peak_memory_mb': 950,
            'avg_cpu_percent': 60,
            'peak_cpu_percent': 85,
            'thread_count': 8
        }

        optimized_limits = optimizer.optimize_resource_limits(current_limits, usage_stats)

        assert 'max_memory_mb' in optimized_limits
        assert 'max_cpu_percent' in optimized_limits
        assert 'max_threads' in optimized_limits

    def test_caching_optimization(self, optimizer):
        """Test caching strategy optimization."""
        cache_stats = {
            'hit_rate': 0.75,
            'miss_rate': 0.25,
            'cache_size_mb': 100,
            'eviction_rate': 0.1
        }

        cache_recommendations = optimizer.optimize_caching_strategy(cache_stats)

        assert isinstance(cache_recommendations, dict)
        assert 'cache_size_recommendation' in cache_recommendations
        assert 'eviction_policy_recommendation' in cache_recommendations


class TestPerformanceAlert:
    """Test suite for PerformanceAlert class."""

    def test_alert_creation(self):
        """Test creating performance alerts."""
        alert = PerformanceAlert(
            alert_type="CPU_HIGH",
            message="CPU usage exceeded threshold",
            threshold=80.0,
            current_value=85.0,
            severity="WARNING"
        )

        assert alert.alert_type == "CPU_HIGH"
        assert alert.message == "CPU usage exceeded threshold"
        assert alert.threshold == 80.0
        assert alert.current_value == 85.0
        assert alert.severity == "WARNING"
        assert alert.timestamp is not None

    def test_alert_serialization(self):
        """Test alert serialization and deserialization."""
        alert = PerformanceAlert(
            alert_type="MEMORY_HIGH",
            message="Memory usage critical",
            threshold=90.0,
            current_value=95.0,
            severity="CRITICAL"
        )

        serialized = alert.to_dict()
        assert isinstance(serialized, dict)
        assert serialized['alert_type'] == "MEMORY_HIGH"

        deserialized = PerformanceAlert.from_dict(serialized)
        assert deserialized.alert_type == alert.alert_type
        assert deserialized.current_value == alert.current_value


class TestSystemResourceMonitor:
    """Test suite for SystemResourceMonitor class."""

    @pytest.fixture
    def resource_monitor(self):
        """Create SystemResourceMonitor instance for testing."""
        return SystemResourceMonitor()

    def test_system_metrics_collection(self, resource_monitor):
        """Test collecting system metrics."""
        metrics = resource_monitor.collect_system_metrics()

        required_metrics = [
            'cpu_percent', 'memory_percent', 'disk_usage',
            'network_io', 'process_count', 'load_average'
        ]

        for metric in required_metrics:
            assert metric in metrics

    def test_process_monitoring(self, resource_monitor):
        """Test process-specific monitoring."""
        import os
        current_pid = os.getpid()

        process_metrics = resource_monitor.monitor_process(current_pid)

        assert 'pid' in process_metrics
        assert 'cpu_percent' in process_metrics
        assert 'memory_mb' in process_metrics
        assert 'status' in process_metrics

    def test_resource_threshold_monitoring(self, resource_monitor):
        """Test resource threshold monitoring."""
        thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 90.0,
            'disk_usage': 85.0
        }

        resource_monitor.set_thresholds(thresholds)

        # Check current status against thresholds
        violations = resource_monitor.check_threshold_violations()

        assert isinstance(violations, list)
        # Each violation should have type, current_value, threshold

    def test_historical_trending(self, resource_monitor):
        """Test historical resource trending."""
        # Collect metrics over time
        for i in range(5):
            resource_monitor.collect_system_metrics()
            time.sleep(0.1)

        trends = resource_monitor.analyze_resource_trends()

        assert 'cpu_trend' in trends
        assert 'memory_trend' in trends
        assert 'predictions' in trends

    @pytest.mark.performance
    def test_monitoring_performance(self, resource_monitor):
        """Test monitoring system performance impact."""
        start_time = time.time()

        # Collect metrics multiple times
        for i in range(10):
            resource_monitor.collect_system_metrics()

        end_time = time.time()
        total_time = end_time - start_time

        # Monitoring should be fast
        assert total_time < 1.0  # Should complete in under 1 second


if __name__ == "__main__":
    pytest.main([__file__, "-v"])