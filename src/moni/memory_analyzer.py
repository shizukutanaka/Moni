"""Advanced memory analysis with pressure indicators, leak detection, and performance profiling."""

from __future__ import annotations

import gc
import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import threading
import psutil

try:
    import tracemalloc
    TRACEMALLOC_AVAILABLE = True
except ImportError:
    TRACEMALLOC_AVAILABLE = False

try:
    import pympler
    from pympler import muppy, summary, tracker
    PYMPLER_AVAILABLE = True
except ImportError:
    PYMPLER_AVAILABLE = False


@dataclass
class MemoryLeak:
    """Memory leak detection result."""
    process_id: int
    process_name: str
    leaked_mb: float
    leak_rate_mb_per_hour: float
    detection_confidence: float  # 0-100
    first_detected: datetime
    last_updated: datetime
    stack_trace: Optional[str] = None
    allocation_pattern: Optional[str] = None


@dataclass
class MemoryPressure:
    """Memory pressure indicators."""
    timestamp: datetime
    available_mb: float
    pressure_level: str  # low, medium, high, critical
    pressure_score: float  # 0-100
    swap_pressure: float  # 0-100
    page_fault_rate: float
    memory_reclaim_rate: float
    oom_kills: int
    low_memory_warnings: int
    fragmentation_index: float  # 0-100


@dataclass
class ProcessMemoryProfile:
    """Detailed memory profile for a process."""
    pid: int
    name: str
    rss_mb: float
    vms_mb: float
    shared_mb: float
    private_mb: float
    heap_mb: float
    stack_mb: float
    code_mb: float
    data_mb: float
    dirty_mb: float
    mapped_files: int
    memory_maps: List[Dict[str, Any]]
    allocation_patterns: Dict[str, int]
    memory_growth_trend: str  # stable, growing, shrinking
    potential_leak: bool


@dataclass
class MemoryAllocation:
    """Memory allocation tracking."""
    address: int
    size: int
    timestamp: float
    stack_trace: str
    allocator: str
    freed: bool = False
    free_timestamp: Optional[float] = None


class MemoryAnalyzer:
    """Advanced memory analysis and leak detection system."""

    def __init__(self):
        self.process_memory_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.system_memory_history: deque = deque(maxlen=500)
        self.detected_leaks: Dict[int, MemoryLeak] = {}
        self.memory_tracker = None
        self.tracking_enabled = False
        self.pressure_thresholds = {
            'low': 20,      # <20% memory usage
            'medium': 60,   # 20-60% memory usage
            'high': 85,     # 60-85% memory usage
            'critical': 95  # >85% memory usage
        }

        if PYMPLER_AVAILABLE:
            self.memory_tracker = tracker.SummaryTracker()

        if TRACEMALLOC_AVAILABLE:
            tracemalloc.start()

    def get_memory_pressure(self) -> MemoryPressure:
        """Analyze current memory pressure indicators."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Calculate pressure score
            pressure_score = memory.percent
            pressure_level = self._calculate_pressure_level(pressure_score)

            # Calculate swap pressure
            swap_pressure = swap.percent if swap.total > 0 else 0

            # Get page fault rate (if available)
            page_fault_rate = self._get_page_fault_rate()

            # Get memory reclaim rate
            reclaim_rate = self._get_memory_reclaim_rate()

            # Count OOM kills (Linux)
            oom_kills = self._count_oom_kills()

            # Calculate fragmentation index
            fragmentation_index = self._calculate_fragmentation_index()

            pressure = MemoryPressure(
                timestamp=datetime.now(),
                available_mb=memory.available / (1024 * 1024),
                pressure_level=pressure_level,
                pressure_score=pressure_score,
                swap_pressure=swap_pressure,
                page_fault_rate=page_fault_rate,
                memory_reclaim_rate=reclaim_rate,
                oom_kills=oom_kills,
                low_memory_warnings=0,  # Would need kernel integration
                fragmentation_index=fragmentation_index
            )

            # Store in history
            self.system_memory_history.append(pressure)

            return pressure

        except Exception as e:
            return MemoryPressure(
                timestamp=datetime.now(),
                available_mb=0,
                pressure_level='unknown',
                pressure_score=0,
                swap_pressure=0,
                page_fault_rate=0,
                memory_reclaim_rate=0,
                oom_kills=0,
                low_memory_warnings=0,
                fragmentation_index=0
            )

    def _calculate_pressure_level(self, pressure_score: float) -> str:
        """Calculate pressure level based on usage percentage."""
        if pressure_score >= self.pressure_thresholds['critical']:
            return 'critical'
        elif pressure_score >= self.pressure_thresholds['high']:
            return 'high'
        elif pressure_score >= self.pressure_thresholds['medium']:
            return 'medium'
        else:
            return 'low'

    def _get_page_fault_rate(self) -> float:
        """Get page fault rate (platform-specific)."""
        try:
            import platform
            system = platform.system().lower()

            if system == 'linux':
                return self._get_page_fault_rate_linux()
            elif system == 'windows':
                return self._get_page_fault_rate_windows()
            elif system == 'darwin':
                return self._get_page_fault_rate_macos()

        except Exception:
            pass

        return 0.0

    def _get_page_fault_rate_linux(self) -> float:
        """Get page fault rate on Linux."""
        try:
            with open('/proc/vmstat', 'r') as f:
                vmstat = f.read()

            # Look for page fault counters
            major_faults = 0
            minor_faults = 0

            for line in vmstat.split('\n'):
                if line.startswith('pgmajfault'):
                    major_faults = int(line.split()[1])
                elif line.startswith('pgfault'):
                    minor_faults = int(line.split()[1])

            # Store previous values to calculate rate
            if not hasattr(self, '_prev_faults'):
                self._prev_faults = (major_faults + minor_faults, time.time())
                return 0.0

            prev_faults, prev_time = self._prev_faults
            current_faults = major_faults + minor_faults
            current_time = time.time()

            rate = (current_faults - prev_faults) / (current_time - prev_time)
            self._prev_faults = (current_faults, current_time)

            return rate

        except Exception:
            return 0.0

    def _get_page_fault_rate_windows(self) -> float:
        """Get page fault rate on Windows."""
        try:
            import subprocess
            result = subprocess.run(
                ['typeperf', '-sc', '1', '\\Memory\\Page Faults/sec'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Page Faults/sec' in line:
                        value = line.split(',')[-1].strip().replace('"', '')
                        try:
                            return float(value)
                        except ValueError:
                            pass

        except Exception:
            pass

        return 0.0

    def _get_page_fault_rate_macos(self) -> float:
        """Get page fault rate on macOS."""
        try:
            import subprocess
            result = subprocess.run(
                ['vm_stat'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'page ins:' in line:
                        # Extract page-in count
                        count = int(line.split(':')[1].strip().replace('.', ''))

                        # Calculate rate if we have previous data
                        if not hasattr(self, '_prev_page_ins'):
                            self._prev_page_ins = (count, time.time())
                            return 0.0

                        prev_count, prev_time = self._prev_page_ins
                        current_time = time.time()
                        rate = (count - prev_count) / (current_time - prev_time)
                        self._prev_page_ins = (count, current_time)
                        return rate

        except Exception:
            pass

        return 0.0

    def _get_memory_reclaim_rate(self) -> float:
        """Get memory reclaim rate."""
        try:
            import platform
            system = platform.system().lower()

            if system == 'linux':
                # Read from /proc/vmstat
                with open('/proc/vmstat', 'r') as f:
                    vmstat = f.read()

                reclaim_count = 0
                for line in vmstat.split('\n'):
                    if line.startswith('pgsteal_'):
                        reclaim_count += int(line.split()[1])

                # Calculate rate
                if not hasattr(self, '_prev_reclaim'):
                    self._prev_reclaim = (reclaim_count, time.time())
                    return 0.0

                prev_reclaim, prev_time = self._prev_reclaim
                current_time = time.time()
                rate = (reclaim_count - prev_reclaim) / (current_time - prev_time)
                self._prev_reclaim = (reclaim_count, current_time)
                return rate

        except Exception:
            pass

        return 0.0

    def _count_oom_kills(self) -> int:
        """Count OOM kills (Linux only)."""
        try:
            import platform
            if platform.system().lower() != 'linux':
                return 0

            # Check dmesg for OOM killer messages
            import subprocess
            result = subprocess.run(
                ['dmesg', '--time-format=iso'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                oom_count = 0
                current_time = datetime.now()
                one_hour_ago = current_time - timedelta(hours=1)

                for line in result.stdout.split('\n'):
                    if 'Out of memory: Kill process' in line or 'oom-kill' in line:
                        try:
                            # Extract timestamp
                            timestamp_str = line.split()[0]
                            timestamp = datetime.fromisoformat(timestamp_str.replace('T', ' ').replace('+', ''))

                            if timestamp >= one_hour_ago:
                                oom_count += 1
                        except Exception:
                            continue

                return oom_count

        except Exception:
            pass

        return 0

    def _calculate_fragmentation_index(self) -> float:
        """Calculate memory fragmentation index."""
        try:
            import platform
            system = platform.system().lower()

            if system == 'linux':
                # Read from /proc/buddyinfo
                try:
                    with open('/proc/buddyinfo', 'r') as f:
                        buddyinfo = f.read()

                    total_free_pages = 0
                    large_free_pages = 0

                    for line in buddyinfo.split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 11:  # Typical format has 11+ fields
                                # Count free pages by order
                                for i, count in enumerate(parts[4:]):
                                    try:
                                        pages = int(count)
                                        page_size = 2 ** i  # Pages of size 2^i
                                        total_free_pages += pages * page_size

                                        # Large pages (order 3+)
                                        if i >= 3:
                                            large_free_pages += pages * page_size
                                    except ValueError:
                                        continue

                    if total_free_pages > 0:
                        fragmentation = 100 - (large_free_pages / total_free_pages * 100)
                        return min(100, max(0, fragmentation))

                except FileNotFoundError:
                    pass

        except Exception:
            pass

        return 0.0

    def detect_memory_leaks(self, min_leak_mb: float = 10.0) -> List[MemoryLeak]:
        """Detect memory leaks in running processes."""
        detected_leaks = []

        try:
            current_time = datetime.now()

            # Analyze each process
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    pid = proc.info['pid']
                    name = proc.info['name']
                    memory_info = proc.info['memory_info']

                    if memory_info:
                        current_rss = memory_info.rss / (1024 * 1024)  # MB

                        # Store memory usage history
                        self.process_memory_history[pid].append({
                            'timestamp': current_time,
                            'rss_mb': current_rss,
                            'name': name
                        })

                        # Analyze for leaks if we have enough history
                        if len(self.process_memory_history[pid]) >= 10:
                            leak = self._analyze_process_for_leaks(pid, min_leak_mb)
                            if leak:
                                detected_leaks.append(leak)
                                self.detected_leaks[pid] = leak

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception:
            pass

        return detected_leaks

    def _analyze_process_for_leaks(self, pid: int, min_leak_mb: float) -> Optional[MemoryLeak]:
        """Analyze a specific process for memory leaks."""
        try:
            history = list(self.process_memory_history[pid])
            if len(history) < 10:
                return None

            # Calculate memory growth trend
            memory_values = [entry['rss_mb'] for entry in history]
            time_points = [(entry['timestamp'] - history[0]['timestamp']).total_seconds() / 3600
                          for entry in history]  # Hours

            # Linear regression to find growth rate
            growth_rate = self._calculate_growth_rate(time_points, memory_values)

            # Check if growth rate indicates a leak
            if growth_rate > min_leak_mb:  # MB per hour
                # Calculate confidence based on correlation and consistency
                confidence = self._calculate_leak_confidence(time_points, memory_values, growth_rate)

                if confidence > 50:  # Only report high-confidence leaks
                    first_detection = history[0]['timestamp']
                    process_name = history[-1]['name']

                    # Calculate total leaked memory
                    initial_memory = memory_values[0]
                    current_memory = memory_values[-1]
                    leaked_mb = current_memory - initial_memory

                    return MemoryLeak(
                        process_id=pid,
                        process_name=process_name,
                        leaked_mb=leaked_mb,
                        leak_rate_mb_per_hour=growth_rate,
                        detection_confidence=confidence,
                        first_detected=first_detection,
                        last_updated=history[-1]['timestamp']
                    )

        except Exception:
            pass

        return None

    def _calculate_growth_rate(self, time_points: List[float], memory_values: List[float]) -> float:
        """Calculate memory growth rate using linear regression."""
        try:
            n = len(time_points)
            if n < 2:
                return 0.0

            # Simple linear regression
            sum_x = sum(time_points)
            sum_y = sum(memory_values)
            sum_xy = sum(x * y for x, y in zip(time_points, memory_values))
            sum_x2 = sum(x * x for x in time_points)

            # Calculate slope (growth rate)
            denominator = n * sum_x2 - sum_x * sum_x
            if denominator == 0:
                return 0.0

            slope = (n * sum_xy - sum_x * sum_y) / denominator
            return max(0, slope)  # Only positive growth rates

        except Exception:
            return 0.0

    def _calculate_leak_confidence(self, time_points: List[float], memory_values: List[float],
                                 growth_rate: float) -> float:
        """Calculate confidence level for leak detection."""
        try:
            # Calculate correlation coefficient
            n = len(time_points)
            if n < 3:
                return 0.0

            mean_x = sum(time_points) / n
            mean_y = sum(memory_values) / n

            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(time_points, memory_values))
            sum_x_sq = sum((x - mean_x) ** 2 for x in time_points)
            sum_y_sq = sum((y - mean_y) ** 2 for y in memory_values)

            denominator = (sum_x_sq * sum_y_sq) ** 0.5
            if denominator == 0:
                return 0.0

            correlation = abs(numerator / denominator)

            # Calculate consistency (how steady the growth is)
            predicted_values = [memory_values[0] + growth_rate * t for t in time_points]
            variance = sum((actual - predicted) ** 2 for actual, predicted in zip(memory_values, predicted_values))
            consistency = max(0, 100 - variance / n)

            # Combine correlation and consistency for confidence
            confidence = (correlation * 50) + (consistency * 0.5)
            return min(100, max(0, confidence))

        except Exception:
            return 0.0

    def get_process_memory_profile(self, pid: int) -> Optional[ProcessMemoryProfile]:
        """Get detailed memory profile for a specific process."""
        try:
            proc = psutil.Process(pid)
            memory_info = proc.memory_info()
            memory_full_info = proc.memory_full_info() if hasattr(proc, 'memory_full_info') else memory_info

            # Get memory maps
            memory_maps = []
            try:
                for mmap in proc.memory_maps():
                    memory_maps.append({
                        'path': mmap.path,
                        'rss': mmap.rss,
                        'size': mmap.size,
                        'permissions': mmap.perms
                    })
            except (psutil.AccessDenied, AttributeError):
                pass

            # Analyze memory growth trend
            growth_trend = self._analyze_memory_trend(pid)

            # Check for potential leak
            potential_leak = pid in self.detected_leaks

            # Calculate allocation patterns (simplified)
            allocation_patterns = self._get_allocation_patterns(pid)

            profile = ProcessMemoryProfile(
                pid=pid,
                name=proc.name(),
                rss_mb=memory_info.rss / (1024 * 1024),
                vms_mb=memory_info.vms / (1024 * 1024),
                shared_mb=getattr(memory_full_info, 'shared', 0) / (1024 * 1024),
                private_mb=getattr(memory_full_info, 'private', memory_info.rss) / (1024 * 1024),
                heap_mb=getattr(memory_full_info, 'data', 0) / (1024 * 1024),
                stack_mb=getattr(memory_full_info, 'stack', 0) / (1024 * 1024),
                code_mb=getattr(memory_full_info, 'text', 0) / (1024 * 1024),
                data_mb=getattr(memory_full_info, 'data', 0) / (1024 * 1024),
                dirty_mb=getattr(memory_full_info, 'dirty', 0) / (1024 * 1024),
                mapped_files=len([m for m in memory_maps if m['path'] and not m['path'].startswith('[')]),
                memory_maps=memory_maps[:10],  # Limit to first 10 for brevity
                allocation_patterns=allocation_patterns,
                memory_growth_trend=growth_trend,
                potential_leak=potential_leak
            )

            return profile

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def _analyze_memory_trend(self, pid: int) -> str:
        """Analyze memory usage trend for a process."""
        if pid not in self.process_memory_history:
            return 'unknown'

        history = list(self.process_memory_history[pid])
        if len(history) < 5:
            return 'insufficient_data'

        # Look at recent vs older values
        recent_values = [entry['rss_mb'] for entry in history[-5:]]
        older_values = [entry['rss_mb'] for entry in history[:5]]

        recent_avg = sum(recent_values) / len(recent_values)
        older_avg = sum(older_values) / len(older_values)

        change_percent = ((recent_avg - older_avg) / older_avg) * 100

        if change_percent > 20:
            return 'growing'
        elif change_percent < -20:
            return 'shrinking'
        else:
            return 'stable'

    def _get_allocation_patterns(self, pid: int) -> Dict[str, int]:
        """Get memory allocation patterns for a process."""
        patterns = {}

        try:
            # This would require more advanced profiling tools
            # For now, return basic patterns based on available data
            proc = psutil.Process(pid)

            # Count different types of memory mappings
            try:
                for mmap in proc.memory_maps():
                    if '[heap]' in mmap.path:
                        patterns['heap_allocations'] = patterns.get('heap_allocations', 0) + 1
                    elif '[stack]' in mmap.path:
                        patterns['stack_allocations'] = patterns.get('stack_allocations', 0) + 1
                    elif mmap.path and not mmap.path.startswith('['):
                        patterns['file_mappings'] = patterns.get('file_mappings', 0) + 1
                    else:
                        patterns['anonymous_mappings'] = patterns.get('anonymous_mappings', 0) + 1
            except (psutil.AccessDenied, AttributeError):
                pass

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return patterns

    def analyze_system_memory_health(self) -> Dict[str, Any]:
        """Analyze overall system memory health."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            pressure = self.get_memory_pressure()

            # Calculate memory efficiency metrics
            active_memory = getattr(memory, 'active', memory.used)
            inactive_memory = getattr(memory, 'inactive', 0)
            cached_memory = getattr(memory, 'cached', 0)
            buffer_memory = getattr(memory, 'buffers', 0)

            efficiency_score = self._calculate_memory_efficiency(
                memory.total, active_memory, cached_memory, buffer_memory
            )

            # Count processes with high memory usage
            high_memory_processes = 0
            total_process_memory = 0

            for proc in psutil.process_iter(['memory_info']):
                try:
                    mem_info = proc.info['memory_info']
                    if mem_info:
                        process_memory_mb = mem_info.rss / (1024 * 1024)
                        total_process_memory += process_memory_mb

                        if process_memory_mb > 100:  # >100MB
                            high_memory_processes += 1
                except:
                    continue

            health_analysis = {
                'timestamp': datetime.now().isoformat(),
                'overall_health': self._calculate_overall_health_score(pressure, efficiency_score),
                'memory_pressure': asdict(pressure),
                'efficiency_score': efficiency_score,
                'memory_distribution': {
                    'used_percent': memory.percent,
                    'active_mb': active_memory / (1024 * 1024),
                    'inactive_mb': inactive_memory / (1024 * 1024),
                    'cached_mb': cached_memory / (1024 * 1024),
                    'buffer_mb': buffer_memory / (1024 * 1024),
                    'free_mb': memory.free / (1024 * 1024),
                    'available_mb': memory.available / (1024 * 1024)
                },
                'swap_analysis': {
                    'used_percent': swap.percent,
                    'used_mb': swap.used / (1024 * 1024),
                    'free_mb': swap.free / (1024 * 1024),
                    'total_mb': swap.total / (1024 * 1024)
                },
                'process_statistics': {
                    'high_memory_processes': high_memory_processes,
                    'total_process_memory_mb': total_process_memory,
                    'detected_leaks': len(self.detected_leaks)
                },
                'recommendations': self._generate_memory_recommendations(pressure, efficiency_score)
            }

            return health_analysis

        except Exception as e:
            return {
                'error': f"Memory health analysis failed: {str(e)}",
                'timestamp': datetime.now().isoformat()
            }

    def _calculate_memory_efficiency(self, total: int, active: int, cached: int, buffer: int) -> float:
        """Calculate memory efficiency score (0-100)."""
        try:
            # Efficient memory usage has good cache/buffer utilization
            cache_buffer_ratio = (cached + buffer) / total
            active_ratio = active / total

            # Good efficiency: moderate active usage, good cache utilization
            ideal_cache_ratio = 0.2  # 20% cached/buffered
            ideal_active_ratio = 0.6  # 60% active

            cache_score = 100 - abs(cache_buffer_ratio - ideal_cache_ratio) * 500
            active_score = 100 - abs(active_ratio - ideal_active_ratio) * 167

            return max(0, min(100, (cache_score + active_score) / 2))

        except Exception:
            return 50.0  # Default neutral score

    def _calculate_overall_health_score(self, pressure: MemoryPressure, efficiency: float) -> float:
        """Calculate overall memory health score."""
        try:
            # Start with base score
            health_score = 100.0

            # Reduce score based on pressure
            if pressure.pressure_level == 'critical':
                health_score -= 40
            elif pressure.pressure_level == 'high':
                health_score -= 25
            elif pressure.pressure_level == 'medium':
                health_score -= 10

            # Reduce score based on swap usage
            health_score -= pressure.swap_pressure * 0.5

            # Reduce score based on fragmentation
            health_score -= pressure.fragmentation_index * 0.3

            # Adjust for efficiency
            health_score = (health_score + efficiency) / 2

            # Reduce score for detected leaks
            health_score -= len(self.detected_leaks) * 5

            return max(0, min(100, health_score))

        except Exception:
            return 50.0

    def _generate_memory_recommendations(self, pressure: MemoryPressure, efficiency: float) -> List[str]:
        """Generate memory optimization recommendations."""
        recommendations = []

        try:
            if pressure.pressure_level in ['high', 'critical']:
                recommendations.append("System memory pressure is high - consider closing unnecessary applications")
                recommendations.append("Add more RAM if memory pressure persists")

            if pressure.swap_pressure > 50:
                recommendations.append("High swap usage detected - increase RAM or optimize memory-heavy applications")

            if pressure.fragmentation_index > 70:
                recommendations.append("High memory fragmentation detected - restart may help consolidate memory")

            if efficiency < 40:
                recommendations.append("Memory efficiency is low - check for memory leaks or inefficient applications")

            if len(self.detected_leaks) > 0:
                recommendations.append(f"{len(self.detected_leaks)} potential memory leaks detected - investigate high-growth processes")

            if pressure.oom_kills > 0:
                recommendations.append(f"{pressure.oom_kills} OOM kills in last hour - system critically low on memory")

            if not recommendations:
                recommendations.append("Memory system appears healthy - continue monitoring")

        except Exception:
            recommendations.append("Unable to generate recommendations due to analysis error")

        return recommendations

    def export_memory_analysis(self, file_path: Path) -> bool:
        """Export comprehensive memory analysis report."""
        try:
            # Get comprehensive data
            system_health = self.analyze_system_memory_health()
            detected_leaks = list(self.detected_leaks.values())
            current_pressure = self.get_memory_pressure()

            # Get process profiles for top memory consumers
            process_profiles = []
            for proc in psutil.process_iter(['pid', 'memory_info']):
                try:
                    mem_info = proc.info['memory_info']
                    if mem_info and mem_info.rss > 100 * 1024 * 1024:  # >100MB
                        profile = self.get_process_memory_profile(proc.info['pid'])
                        if profile:
                            process_profiles.append(asdict(profile))
                except:
                    continue

            # Sort by memory usage
            process_profiles.sort(key=lambda x: x['rss_mb'], reverse=True)

            export_data = {
                'timestamp': int(time.time() * 1000),
                'generated_at': datetime.now().isoformat(),
                'system_health': system_health,
                'current_pressure': asdict(current_pressure),
                'detected_leaks': [asdict(leak) for leak in detected_leaks],
                'top_memory_processes': process_profiles[:20],  # Top 20
                'memory_history': [asdict(entry) for entry in list(self.system_memory_history)[-50:]],  # Last 50 entries
                'analysis_metadata': {
                    'tracemalloc_available': TRACEMALLOC_AVAILABLE,
                    'pympler_available': PYMPLER_AVAILABLE,
                    'tracking_enabled': self.tracking_enabled,
                    'processes_monitored': len(self.process_memory_history),
                    'report_version': '1.0'
                }
            }

            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

            return True

        except Exception:
            return False

    def start_continuous_monitoring(self, interval_seconds: int = 60):
        """Start continuous memory monitoring in background."""
        def monitor_loop():
            while self.tracking_enabled:
                try:
                    self.get_memory_pressure()
                    self.detect_memory_leaks()
                    time.sleep(interval_seconds)
                except Exception:
                    time.sleep(interval_seconds)

        if not self.tracking_enabled:
            self.tracking_enabled = True
            monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
            monitor_thread.start()

    def stop_continuous_monitoring(self):
        """Stop continuous memory monitoring."""
        self.tracking_enabled = False