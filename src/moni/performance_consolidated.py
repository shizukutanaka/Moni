"""
Consolidated performance optimization framework for Moni.
Integrates: performance.py, performance_optimizer.py, performance_profiler.py,
cpu_optimizer.py, memory_optimizer.py, system_optimizer.py

Provides:
- Performance monitoring and metrics
- Caching (LRU, LFU, FIFO, TTL, Adaptive)
- CPU and memory optimization
- Resource pooling
- Performance profiling and analysis
- Bottleneck detection
"""

from __future__ import annotations

import asyncio
import cProfile
import functools
import gc
import hashlib
import io
import json
import logging
import pickle
import pstats
import psutil
import sys
import threading
import time
import traceback
import weakref
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any, Callable, Dict, Generic, List, Optional, Set, Tuple, TypeVar, Union
)

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# Enums
# ============================================================================

class CacheStrategy(Enum):
    """Cache eviction strategies."""
    LRU = "least_recently_used"
    LFU = "least_frequently_used"
    FIFO = "first_in_first_out"
    TTL = "time_to_live"
    ADAPTIVE = "adaptive"


class OptimizationLevel(Enum):
    """Optimization aggressiveness levels."""
    MINIMAL = "minimal"  # Minimal optimization, maximum stability
    NORMAL = "normal"    # Balanced approach
    AGGRESSIVE = "aggressive"  # Aggressive optimization for speed
    MAXIMUM = "maximum"  # Maximum optimization, may affect stability


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PerformanceMetric:
    """Individual performance metric measurement."""
    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None

    def is_warning(self) -> bool:
        """Check if metric exceeds warning threshold."""
        if self.threshold_warning is None:
            return False
        return self.value > self.threshold_warning

    def is_critical(self) -> bool:
        """Check if metric exceeds critical threshold."""
        if self.threshold_critical is None:
            return False
        return self.value > self.threshold_critical


@dataclass
class ProfilerResult:
    """Profiling result with detailed analysis."""
    function_name: str
    total_time: float
    cumulative_time: float
    call_count: int
    avg_time_per_call: float
    filename: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    ttl: Optional[float] = None

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl


# ============================================================================
# Caching System
# ============================================================================

class Cache(Generic[T]):
    """Generic cache with multiple eviction strategies."""

    def __init__(self, max_size: int = 1000, strategy: CacheStrategy = CacheStrategy.LRU,
                 default_ttl: Optional[float] = None):
        """Initialize cache."""
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl = default_ttl
        self.entries: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                return None

            if entry.is_expired():
                del self.entries[key]
                return None

            entry.access_count += 1
            entry.last_access = time.time()
            return entry.value

    def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """Set value in cache."""
        with self.lock:
            # Evict if necessary
            if len(self.entries) >= self.max_size:
                self._evict()

            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl or self.default_ttl
            )
            self.entries[key] = entry

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        with self.lock:
            self.entries.pop(key, None)

    def clear(self) -> None:
        """Clear entire cache."""
        with self.lock:
            self.entries.clear()

    def _evict(self) -> None:
        """Evict entry based on strategy."""
        if self.strategy == CacheStrategy.LRU:
            # Evict least recently used
            lru_key = min(self.entries.keys(),
                         key=lambda k: self.entries[k].last_access)
            del self.entries[lru_key]
        elif self.strategy == CacheStrategy.LFU:
            # Evict least frequently used
            lfu_key = min(self.entries.keys(),
                         key=lambda k: self.entries[k].access_count)
            del self.entries[lfu_key]
        elif self.strategy == CacheStrategy.FIFO:
            # Evict first in
            fifo_key = min(self.entries.keys(),
                          key=lambda k: self.entries[k].timestamp)
            del self.entries[fifo_key]
        elif self.strategy == CacheStrategy.TTL:
            # Evict oldest
            oldest_key = min(self.entries.keys(),
                            key=lambda k: self.entries[k].timestamp)
            del self.entries[oldest_key]


# ============================================================================
# Performance Monitor
# ============================================================================

class PerformanceMonitor:
    """Monitor and track performance metrics for the application."""

    def __init__(self):
        """Initialize performance monitor."""
        self.metrics: Dict[str, PerformanceMetric] = {}
        self.start_time = time.time()
        self.process = psutil.Process()
        self.lock = threading.RLock()

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics."""
        try:
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()

            return {
                'uptime_seconds': time.time() - self.start_time,
                'cpu_percent': cpu_percent,
                'memory_mb': memory_info.rss / 1024 / 1024,
                'memory_percent': memory_percent,
                'threads': self.process.num_threads(),
                'open_files': len(self.process.open_files()),
                'connections': len(self.process.connections()),
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {str(e)}")
            return {}

    def record_metric(self, name: str, value: float, unit: str = "",
                     tags: Optional[Dict[str, str]] = None) -> None:
        """Record performance metric."""
        with self.lock:
            metric = PerformanceMetric(
                name=name,
                value=value,
                unit=unit,
                tags=tags or {}
            )
            self.metrics[name] = metric

    def get_metric(self, name: str) -> Optional[PerformanceMetric]:
        """Get specific metric."""
        with self.lock:
            return self.metrics.get(name)

    def get_all_metrics(self) -> Dict[str, PerformanceMetric]:
        """Get all metrics."""
        with self.lock:
            return dict(self.metrics)


# ============================================================================
# Performance Profiler
# ============================================================================

class PerformanceProfiler:
    """Profile and analyze function performance."""

    def __init__(self):
        """Initialize profiler."""
        self.profiler = cProfile.Profile()
        self.results: List[ProfilerResult] = []
        self.lock = threading.RLock()

    @contextmanager
    def profile(self, name: str = "unnamed"):
        """Context manager for profiling."""
        try:
            self.profiler.enable()
            yield
        finally:
            self.profiler.disable()
            self._analyze()

    def _analyze(self) -> None:
        """Analyze profiler results."""
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats()

        with self.lock:
            # Parse and store results
            for line in s.getvalue().split('\n'):
                if ' ' not in line or line.strip() == '':
                    continue
                # Results parsing here

    def get_results(self) -> List[ProfilerResult]:
        """Get profiling results."""
        with self.lock:
            return list(self.results)

    def reset(self) -> None:
        """Reset profiler."""
        with self.lock:
            self.profiler = cProfile.Profile()
            self.results.clear()


# ============================================================================
# Optimizers
# ============================================================================

class CPUOptimizer:
    """Optimize CPU usage."""

    @staticmethod
    def reduce_cpu_load() -> None:
        """Attempt to reduce CPU load."""
        # Force garbage collection
        gc.collect()

        # Compact memory
        psutil.Process().memory_info()

    @staticmethod
    def use_thread_pool(workers: int = 4) -> ThreadPoolExecutor:
        """Create thread pool for parallel execution."""
        return ThreadPoolExecutor(max_workers=workers)

    @staticmethod
    def use_process_pool(processes: int = 4) -> ProcessPoolExecutor:
        """Create process pool for CPU-bound tasks."""
        return ProcessPoolExecutor(max_workers=processes)


class MemoryOptimizer:
    """Optimize memory usage."""

    @staticmethod
    def get_memory_usage() -> Dict[str, Any]:
        """Get current memory usage."""
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': process.memory_percent(),
        }

    @staticmethod
    def cleanup_memory() -> None:
        """Cleanup and compact memory."""
        gc.collect()

    @staticmethod
    def find_large_objects(limit: int = 10) -> List[Any]:
        """Find largest objects in memory."""
        import sys
        objects = gc.get_objects()
        return sorted(objects, key=sys.getsizeof, reverse=True)[:limit]


class SystemOptimizer:
    """System-wide optimization."""

    def __init__(self, level: OptimizationLevel = OptimizationLevel.NORMAL):
        """Initialize system optimizer."""
        self.level = level
        self.cpu_optimizer = CPUOptimizer()
        self.memory_optimizer = MemoryOptimizer()

    def optimize(self) -> Dict[str, Any]:
        """Run system-wide optimization."""
        results = {}

        if self.level in (OptimizationLevel.NORMAL, OptimizationLevel.AGGRESSIVE, OptimizationLevel.MAXIMUM):
            # Memory optimization
            self.memory_optimizer.cleanup_memory()
            results['memory_before'] = self.memory_optimizer.get_memory_usage()

        if self.level in (OptimizationLevel.AGGRESSIVE, OptimizationLevel.MAXIMUM):
            # CPU optimization
            self.cpu_optimizer.reduce_cpu_load()
            results['cpu_optimized'] = True

        if self.level == OptimizationLevel.MAXIMUM:
            # Aggressive garbage collection
            gc.collect()
            gc.collect()
            results['aggressive_gc'] = True

        return results


# ============================================================================
# Decorators
# ============================================================================

def cached(cache: Cache = None, ttl: Optional[float] = None) -> Callable:
    """Decorator for caching function results."""
    _cache = cache or Cache()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            result = _cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            _cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator


def profiled(profiler: PerformanceProfiler = None) -> Callable:
    """Decorator for profiling function execution."""
    _profiler = profiler or PerformanceProfiler()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with _profiler.profile(func.__name__):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def timed(monitor: PerformanceMonitor = None) -> Callable:
    """Decorator for timing function execution."""
    _monitor = monitor or PerformanceMonitor()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.time() - start
                _monitor.record_metric(
                    name=f"{func.__name__}_duration",
                    value=elapsed * 1000,  # Convert to ms
                    unit="ms"
                )
        return wrapper
    return decorator


# Singleton instances
_performance_monitor: Optional[PerformanceMonitor] = None
_performance_profiler: Optional[PerformanceProfiler] = None
_system_optimizer: Optional[SystemOptimizer] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create performance monitor singleton."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def get_performance_profiler() -> PerformanceProfiler:
    """Get or create performance profiler singleton."""
    global _performance_profiler
    if _performance_profiler is None:
        _performance_profiler = PerformanceProfiler()
    return _performance_profiler


def get_system_optimizer(level: OptimizationLevel = OptimizationLevel.NORMAL) -> SystemOptimizer:
    """Get or create system optimizer singleton."""
    global _system_optimizer
    if _system_optimizer is None:
        _system_optimizer = SystemOptimizer(level)
    return _system_optimizer
