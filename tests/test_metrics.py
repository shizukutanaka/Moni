"""
Comprehensive test suite for the metrics module.
Tests metric collection, storage, and processing functionality.
"""

import pytest
import time
import threading
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from collections import deque

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from moni.metrics import (
    Metric, MetricPoint, MetricRegistry, MetricHistory,
    CPUMetric, MemoryMetric, NetworkMetric, DiskMetric,
    ProcessMetric, SystemMetric
)


class TestMetric:
    """Test the base Metric class."""

    def test_metric_initialization(self):
        """Test metric initialization with required parameters."""
        metric = Metric("test_metric", "Test Metric", "Test description")

        assert metric.identifier == "test_metric"
        assert metric.name == "Test Metric"
        assert metric.description == "Test description"
        assert metric.unit == ""
        assert metric.collection_interval == 1.0
        assert metric.enabled is True

    def test_metric_with_custom_parameters(self):
        """Test metric initialization with custom parameters."""
        metric = Metric(
            identifier="custom_metric",
            name="Custom Metric",
            description="Custom description",
            unit="MB",
            collection_interval=2.0,
            enabled=False
        )

        assert metric.unit == "MB"
        assert metric.collection_interval == 2.0
        assert metric.enabled is False

    def test_metric_collect_not_implemented(self):
        """Test that base metric collect method raises NotImplementedError."""
        metric = Metric("test", "Test", "Test")

        with pytest.raises(NotImplementedError):
            metric.collect()

    def test_metric_equality(self):
        """Test metric equality comparison."""
        metric1 = Metric("test", "Test", "Test")
        metric2 = Metric("test", "Test", "Test")
        metric3 = Metric("different", "Different", "Different")

        assert metric1 == metric2
        assert metric1 != metric3

    def test_metric_string_representation(self):
        """Test metric string representation."""
        metric = Metric("test_metric", "Test Metric", "Test description")
        str_repr = str(metric)

        assert "test_metric" in str_repr
        assert "Test Metric" in str_repr


class TestMetricPoint:
    """Test the MetricPoint data class."""

    def test_metric_point_creation(self):
        """Test MetricPoint creation with data."""
        timestamp = time.time()
        data = {"cpu": 45.0, "memory": 512}

        point = MetricPoint(timestamp=timestamp, data=data)

        assert point.timestamp == timestamp
        assert point.data == data

    def test_metric_point_default_timestamp(self):
        """Test MetricPoint with default timestamp."""
        data = {"value": 100}

        point = MetricPoint(data=data)

        assert point.timestamp > 0
        assert abs(point.timestamp - time.time()) < 1.0  # Within 1 second

    def test_metric_point_serialization(self):
        """Test MetricPoint serialization."""
        point = MetricPoint(timestamp=1234567890.0, data={"value": 42})

        serialized = point.to_dict()

        assert serialized["timestamp"] == 1234567890.0
        assert serialized["data"] == {"value": 42}


class TestCPUMetric:
    """Test CPU metric collection."""

    def test_cpu_metric_initialization(self):
        """Test CPU metric initialization."""
        cpu_metric = CPUMetric()

        assert cpu_metric.identifier == "cpu"
        assert "CPU" in cpu_metric.name
        assert cpu_metric.unit == "%"

    def test_cpu_metric_collection(self):
        """Test CPU metric data collection."""
        cpu_metric = CPUMetric()

        data = cpu_metric.collect()

        assert isinstance(data, dict)
        assert "overall" in data
        assert "per_core" in data
        assert isinstance(data["overall"], (int, float))
        assert isinstance(data["per_core"], list)
        assert 0 <= data["overall"] <= 100

    def test_cpu_metric_multiple_collections(self):
        """Test multiple CPU metric collections."""
        cpu_metric = CPUMetric()

        # Collect multiple times
        results = []
        for _ in range(3):
            data = cpu_metric.collect()
            results.append(data)
            time.sleep(0.1)

        # All collections should succeed
        assert len(results) == 3
        for result in results:
            assert "overall" in result
            assert "per_core" in result


class TestMemoryMetric:
    """Test memory metric collection."""

    def test_memory_metric_initialization(self):
        """Test memory metric initialization."""
        memory_metric = MemoryMetric()

        assert memory_metric.identifier == "memory"
        assert "Memory" in memory_metric.name
        assert memory_metric.unit in ["MB", "GB", "bytes"]

    def test_memory_metric_collection(self):
        """Test memory metric data collection."""
        memory_metric = MemoryMetric()

        data = memory_metric.collect()

        assert isinstance(data, dict)
        assert "total" in data
        assert "available" in data
        assert "used" in data
        assert "percent" in data
        assert isinstance(data["total"], (int, float))
        assert isinstance(data["available"], (int, float))
        assert isinstance(data["used"], (int, float))
        assert isinstance(data["percent"], (int, float))
        assert 0 <= data["percent"] <= 100

    def test_memory_metric_consistency(self):
        """Test memory metric data consistency."""
        memory_metric = MemoryMetric()

        data = memory_metric.collect()

        # Basic consistency checks
        assert data["used"] <= data["total"]
        assert data["available"] <= data["total"]
        # Used + available should be approximately equal to total
        assert abs((data["used"] + data["available"]) - data["total"]) < data["total"] * 0.1


class TestNetworkMetric:
    """Test network metric collection."""

    def test_network_metric_initialization(self):
        """Test network metric initialization."""
        network_metric = NetworkMetric()

        assert network_metric.identifier == "network"
        assert "Network" in network_metric.name

    def test_network_metric_collection(self):
        """Test network metric data collection."""
        network_metric = NetworkMetric()

        data = network_metric.collect()

        assert isinstance(data, dict)
        # Should have interface data
        assert len(data) > 0

        # Check structure of first interface
        first_interface = next(iter(data.values()))
        assert "bytes_sent" in first_interface
        assert "bytes_recv" in first_interface
        assert "packets_sent" in first_interface
        assert "packets_recv" in first_interface

    def test_network_metric_rate_calculation(self):
        """Test network metric rate calculation."""
        network_metric = NetworkMetric()

        # First collection
        data1 = network_metric.collect()
        time.sleep(1.0)

        # Second collection
        data2 = network_metric.collect()

        # Both collections should succeed
        assert isinstance(data1, dict)
        assert isinstance(data2, dict)


class TestDiskMetric:
    """Test disk metric collection."""

    def test_disk_metric_initialization(self):
        """Test disk metric initialization."""
        disk_metric = DiskMetric()

        assert disk_metric.identifier == "disk"
        assert "Disk" in disk_metric.name

    def test_disk_metric_collection(self):
        """Test disk metric data collection."""
        disk_metric = DiskMetric()

        data = disk_metric.collect()

        assert isinstance(data, dict)
        assert len(data) > 0  # Should have at least one disk

        # Check structure of first disk
        first_disk = next(iter(data.values()))
        assert "total" in first_disk
        assert "used" in first_disk
        assert "free" in first_disk
        assert "percent" in first_disk

    def test_disk_metric_io_stats(self):
        """Test disk I/O statistics collection."""
        disk_metric = DiskMetric()

        data = disk_metric.collect()

        # Should include I/O statistics
        for disk_data in data.values():
            if "io_stats" in disk_data:
                io_stats = disk_data["io_stats"]
                assert "read_bytes" in io_stats
                assert "write_bytes" in io_stats
                assert "read_count" in io_stats
                assert "write_count" in io_stats


class TestProcessMetric:
    """Test process metric collection."""

    def test_process_metric_initialization(self):
        """Test process metric initialization."""
        process_metric = ProcessMetric()

        assert process_metric.identifier == "processes"
        assert "Process" in process_metric.name

    def test_process_metric_collection(self):
        """Test process metric data collection."""
        process_metric = ProcessMetric()

        data = process_metric.collect()

        assert isinstance(data, dict)
        assert "process_count" in data
        assert "top_cpu_processes" in data
        assert "top_memory_processes" in data
        assert isinstance(data["process_count"], int)
        assert isinstance(data["top_cpu_processes"], list)
        assert isinstance(data["top_memory_processes"], list)

    def test_process_metric_top_processes(self):
        """Test top processes collection."""
        process_metric = ProcessMetric(top_count=5)

        data = process_metric.collect()

        # Should have at most 5 processes in each top list
        assert len(data["top_cpu_processes"]) <= 5
        assert len(data["top_memory_processes"]) <= 5

        # Each process should have required fields
        for process in data["top_cpu_processes"]:
            assert "name" in process
            assert "pid" in process
            assert "cpu_percent" in process

        for process in data["top_memory_processes"]:
            assert "name" in process
            assert "pid" in process
            assert "memory_percent" in process


class TestSystemMetric:
    """Test system metric collection."""

    def test_system_metric_initialization(self):
        """Test system metric initialization."""
        system_metric = SystemMetric()

        assert system_metric.identifier == "system"
        assert "System" in system_metric.name

    def test_system_metric_collection(self):
        """Test system metric data collection."""
        system_metric = SystemMetric()

        data = system_metric.collect()

        assert isinstance(data, dict)
        assert "uptime" in data
        assert "boot_time" in data
        assert "load_average" in data
        assert isinstance(data["uptime"], (int, float))
        assert isinstance(data["boot_time"], (int, float))


class TestMetricRegistry:
    """Test the MetricRegistry class."""

    def test_metric_registry_initialization(self):
        """Test metric registry initialization."""
        registry = MetricRegistry()

        assert isinstance(registry._metrics, dict)
        assert len(registry._metrics) == 0
        assert registry._collection_thread is None
        assert registry._stop_collection.is_set() is True

    def test_metric_registration(self):
        """Test metric registration."""
        registry = MetricRegistry()
        metric = CPUMetric()

        registry.register(metric)

        assert metric.identifier in registry._metrics
        assert registry._metrics[metric.identifier] is metric

    def test_metric_unregistration(self):
        """Test metric unregistration."""
        registry = MetricRegistry()
        metric = CPUMetric()

        registry.register(metric)
        assert metric.identifier in registry._metrics

        registry.unregister(metric.identifier)
        assert metric.identifier not in registry._metrics

    def test_metric_collection_single(self):
        """Test single metric collection."""
        registry = MetricRegistry()
        metric = CPUMetric()
        registry.register(metric)

        data = registry.collect_metric(metric.identifier)

        assert isinstance(data, dict)
        assert "overall" in data
        assert "per_core" in data

    def test_metric_collection_all(self):
        """Test collection of all metrics."""
        registry = MetricRegistry()

        # Register multiple metrics
        cpu_metric = CPUMetric()
        memory_metric = MemoryMetric()
        registry.register(cpu_metric)
        registry.register(memory_metric)

        all_data = registry.collect_all()

        assert isinstance(all_data, dict)
        assert cpu_metric.identifier in all_data
        assert memory_metric.identifier in all_data

    def test_metric_collection_thread_start_stop(self):
        """Test metric collection thread lifecycle."""
        registry = MetricRegistry()
        metric = CPUMetric()
        registry.register(metric)

        # Start collection
        registry.start_collection(interval=0.1)
        assert registry._collection_thread is not None
        assert registry._collection_thread.is_alive()
        assert registry._stop_collection.is_set() is False

        # Wait briefly for collection
        time.sleep(0.2)

        # Stop collection
        registry.stop_collection()
        assert registry._stop_collection.is_set() is True

        # Thread should stop
        registry._collection_thread.join(timeout=1.0)
        assert registry._collection_thread.is_alive() is False

    def test_metric_collection_with_history(self):
        """Test metric collection with history integration."""
        from moni.metrics import MetricHistory

        registry = MetricRegistry()
        history = MetricHistory()

        # Set up history in registry
        registry._history = history

        # Register metric
        metric = CPUMetric()
        registry.register(metric)

        # Collect metric
        data = registry.collect_metric(metric.identifier)

        # Verify collection succeeded
        assert isinstance(data, dict)

    def test_disabled_metric_collection(self):
        """Test that disabled metrics are not collected."""
        registry = MetricRegistry()

        # Create disabled metric
        metric = CPUMetric()
        metric.enabled = False
        registry.register(metric)

        # Collection should return None or empty for disabled metric
        data = registry.collect_metric(metric.identifier)
        assert data is None or data == {}

    def test_metric_collection_error_handling(self):
        """Test error handling during metric collection."""
        registry = MetricRegistry()

        # Create a mock metric that raises an exception
        failing_metric = Mock(spec=Metric)
        failing_metric.identifier = "failing_metric"
        failing_metric.enabled = True
        failing_metric.collect.side_effect = RuntimeError("Collection failed")

        registry.register_metric(failing_metric)

        # Collection should handle the error gracefully
        data = registry.collect_metric("failing_metric")
        assert data is None

    def test_concurrent_metric_access(self):
        """Test concurrent access to metrics."""
        registry = MetricRegistry()
        cpu_metric = CPUMetric()
        registry.register(cpu_metric)

        results = []
        errors = []

        def collect_worker():
            try:
                data = registry.collect_metric(cpu_metric.identifier)
                results.append(data)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=collect_worker)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All collections should succeed
        assert len(errors) == 0
        assert len(results) == 5

    def test_metric_registry_cleanup(self):
        """Test metric registry cleanup."""
        registry = MetricRegistry()
        metric = CPUMetric()
        registry.register(metric)

        # Start collection
        registry.start_collection(interval=0.1)

        # Cleanup
        registry.cleanup()

        # Should stop collection and clean up resources
        assert registry._stop_collection.is_set() is True
        if registry._collection_thread:
            assert registry._collection_thread.is_alive() is False


class TestMetricHistory:
    """Test the MetricHistory class."""

    def test_metric_history_initialization(self):
        """Test metric history initialization."""
        history = MetricHistory()

        assert isinstance(history._data, dict)
        assert history._max_points > 0
        assert isinstance(history._lock, type(threading.RLock()))

    def test_add_metric_point(self):
        """Test adding metric points to history."""
        history = MetricHistory()

        point = MetricPoint(
            timestamp=time.time(),
            data={"cpu": 45.0}
        )

        history.add_point("cpu", point)

        # Verify point was added
        cpu_data = history.get_metric_data("cpu")
        assert len(cpu_data["timestamps"]) == 1
        assert len(cpu_data["values"]) == 1
        assert cpu_data["values"][0] == {"cpu": 45.0}

    def test_metric_history_max_points(self):
        """Test metric history respects max points limit."""
        history = MetricHistory(max_points=5)

        # Add more points than max
        for i in range(10):
            point = MetricPoint(
                timestamp=time.time() + i,
                data={"value": i}
            )
            history.add_point("test", point)

        # Should only keep last 5 points
        test_data = history.get_metric_data("test")
        assert len(test_data["timestamps"]) == 5
        assert len(test_data["values"]) == 5

        # Should be the last 5 values
        values = [point["value"] for point in test_data["values"]]
        assert values == [5, 6, 7, 8, 9]

    def test_get_data_range(self):
        """Test getting data within a time range."""
        history = MetricHistory()

        base_time = time.time()

        # Add points across time range
        for i in range(10):
            point = MetricPoint(
                timestamp=base_time + i,
                data={"value": i}
            )
            history.add_point("test", point)

        # Get data for middle range
        start_time = base_time + 3
        end_time = base_time + 7

        range_data = history.get_data_range(start_time, end_time)

        assert "test" in range_data
        test_data = range_data["test"]

        # Should have points 3, 4, 5, 6, 7
        assert len(test_data["values"]) == 5
        values = [point["value"] for point in test_data["values"]]
        assert values == [3, 4, 5, 6, 7]

    def test_metric_history_concurrent_access(self):
        """Test concurrent access to metric history."""
        history = MetricHistory()

        def add_points_worker(worker_id):
            for i in range(10):
                point = MetricPoint(
                    timestamp=time.time(),
                    data={"worker": worker_id, "value": i}
                )
                history.add_point(f"worker_{worker_id}", point)

        # Start multiple workers
        threads = []
        for worker_id in range(3):
            thread = threading.Thread(target=add_points_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify all data was added
        for worker_id in range(3):
            metric_name = f"worker_{worker_id}"
            data = history.get_metric_data(metric_name)
            assert len(data["values"]) == 10

    def test_metric_history_cleanup(self):
        """Test metric history cleanup."""
        history = MetricHistory()

        # Add some data
        for i in range(5):
            point = MetricPoint(
                timestamp=time.time(),
                data={"value": i}
            )
            history.add_point("test", point)

        # Cleanup
        history.cleanup()

        # Data should be cleared
        assert len(history._data) == 0

    def test_metric_history_serialization(self):
        """Test metric history serialization."""
        history = MetricHistory()

        # Add test data
        base_time = time.time()
        for i in range(3):
            point = MetricPoint(
                timestamp=base_time + i,
                data={"value": i}
            )
            history.add_point("test", point)

        # Export data
        exported_data = history.export_data()

        assert isinstance(exported_data, dict)
        assert "test" in exported_data
        assert len(exported_data["test"]["values"]) == 3


class TestMetricIntegration:
    """Integration tests for the complete metrics system."""

    def test_full_metrics_pipeline(self):
        """Test the complete metrics collection pipeline."""
        # Create components
        registry = MetricRegistry()
        history = MetricHistory()

        # Connect registry to history
        registry._history = history

        # Register metrics
        cpu_metric = CPUMetric()
        memory_metric = MemoryMetric()
        registry.register(cpu_metric)
        registry.register(memory_metric)

        # Start collection
        registry.start_collection(interval=0.1)

        # Wait for some data
        time.sleep(0.5)

        # Stop collection
        registry.stop_collection()

        # Verify data was collected
        cpu_data = history.get_metric_data("cpu")
        memory_data = history.get_metric_data("memory")

        assert len(cpu_data["values"]) > 0
        assert len(memory_data["values"]) > 0

    @pytest.mark.performance
    def test_metrics_performance(self):
        """Test metrics collection performance."""
        registry = MetricRegistry()

        # Register multiple metrics
        metrics = [CPUMetric(), MemoryMetric(), NetworkMetric(), DiskMetric()]
        for metric in metrics:
            registry.register(metric)

        # Measure collection time
        start_time = time.time()
        all_data = registry.collect_all()
        collection_time = time.time() - start_time

        # Collection should be fast
        assert collection_time < 1.0, f"Collection took {collection_time:.3f}s, should be < 1s"

        # Should have collected all metrics
        assert len(all_data) == len(metrics)

    @pytest.mark.memory
    def test_metrics_memory_usage(self):
        """Test metrics memory usage."""
        import psutil
        import gc

        process = psutil.Process()

        # Measure initial memory
        gc.collect()
        initial_memory = process.memory_info().rss

        # Create and run metrics system
        registry = MetricRegistry()
        history = MetricHistory(max_points=1000)

        # Register metrics
        metrics = [CPUMetric(), MemoryMetric(), NetworkMetric()]
        for metric in metrics:
            registry.register(metric)

        # Collect data
        for _ in range(100):
            all_data = registry.collect_all()
            for metric_id, data in all_data.items():
                point = MetricPoint(timestamp=time.time(), data=data)
                history.add_point(metric_id, point)

        # Measure final memory
        gc.collect()
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 50 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.1f}MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])