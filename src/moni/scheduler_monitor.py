"""System scheduler and context switch monitoring with performance analysis."""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import threading
import subprocess
import psutil

try:
    import os
    if hasattr(os, 'sched_getaffinity'):
        SCHED_AVAILABLE = True
    else:
        SCHED_AVAILABLE = False
except ImportError:
    SCHED_AVAILABLE = False


@dataclass
class SchedulerMetrics:
    """System scheduler performance metrics."""
    timestamp: datetime
    context_switches_per_sec: float
    voluntary_context_switches: int
    involuntary_context_switches: int
    scheduler_latency_ms: float
    load_average_1min: float
    load_average_5min: float
    load_average_15min: float
    runnable_processes: int
    blocked_processes: int
    cpu_scheduler_efficiency: float  # 0-100
    interrupt_rate_per_sec: float
    softirq_rate_per_sec: float
    scheduler_policy_distribution: Dict[str, int]


@dataclass
class ProcessSchedulingInfo:
    """Detailed scheduling information for a process."""
    pid: int
    name: str
    priority: int
    nice_value: int
    scheduling_policy: str
    cpu_affinity: List[int]
    context_switches_voluntary: int
    context_switches_involuntary: int
    cpu_time_user: float
    cpu_time_system: float
    wait_time_total: float
    sleep_time_total: float
    run_delay_total: float
    timeslices_used: int
    preemptions: int
    migrations: int
    last_cpu: int
    state: str


@dataclass
class CPUSchedulingStats:
    """Per-CPU scheduling statistics."""
    cpu_id: int
    utilization_percent: float
    context_switches: int
    interrupts: int
    softirqs: int
    idle_time_percent: float
    iowait_time_percent: float
    steal_time_percent: float
    guest_time_percent: float
    load_balance_count: int
    migration_count: int
    runqueue_length: int
    average_latency_ms: float


class SchedulerMonitor:
    """Advanced system scheduler and context switch monitoring."""

    def __init__(self):
        self.metrics_history: deque = deque(maxlen=300)  # 5 minutes at 1-second intervals
        self.process_scheduling_cache: Dict[int, ProcessSchedulingInfo] = {}
        self.cpu_stats_cache: Dict[int, CPUSchedulingStats] = {}
        self.last_stats_time = 0
        self.baseline_measurements: Dict[str, float] = {}
        self.monitoring_active = False

    def get_scheduler_metrics(self) -> SchedulerMetrics:
        """Get comprehensive system scheduler metrics."""
        try:
            current_time = datetime.now()

            # Get context switch information
            context_switches = self._get_context_switches()

            # Get scheduler latency
            scheduler_latency = self._measure_scheduler_latency()

            # Get load averages
            load_avg = self._get_load_averages()

            # Get process counts by state
            runnable, blocked = self._count_processes_by_state()

            # Calculate scheduler efficiency
            efficiency = self._calculate_scheduler_efficiency()

            # Get interrupt rates
            interrupt_rate, softirq_rate = self._get_interrupt_rates()

            # Get scheduling policy distribution
            policy_distribution = self._get_scheduling_policy_distribution()

            metrics = SchedulerMetrics(
                timestamp=current_time,
                context_switches_per_sec=context_switches['rate'],
                voluntary_context_switches=context_switches['voluntary'],
                involuntary_context_switches=context_switches['involuntary'],
                scheduler_latency_ms=scheduler_latency,
                load_average_1min=load_avg[0],
                load_average_5min=load_avg[1],
                load_average_15min=load_avg[2],
                runnable_processes=runnable,
                blocked_processes=blocked,
                cpu_scheduler_efficiency=efficiency,
                interrupt_rate_per_sec=interrupt_rate,
                softirq_rate_per_sec=softirq_rate,
                scheduler_policy_distribution=policy_distribution
            )

            # Store in history
            self.metrics_history.append(metrics)

            return metrics

        except Exception as e:
            return SchedulerMetrics(
                timestamp=datetime.now(),
                context_switches_per_sec=0,
                voluntary_context_switches=0,
                involuntary_context_switches=0,
                scheduler_latency_ms=0,
                load_average_1min=0,
                load_average_5min=0,
                load_average_15min=0,
                runnable_processes=0,
                blocked_processes=0,
                cpu_scheduler_efficiency=0,
                interrupt_rate_per_sec=0,
                softirq_rate_per_sec=0,
                scheduler_policy_distribution={}
            )

    def _get_context_switches(self) -> Dict[str, int]:
        """Get context switch statistics."""
        try:
            import platform
            system = platform.system().lower()

            if system == 'linux':
                return self._get_context_switches_linux()
            elif system == 'windows':
                return self._get_context_switches_windows()
            elif system == 'darwin':
                return self._get_context_switches_macos()

        except Exception:
            pass

        return {'rate': 0, 'voluntary': 0, 'involuntary': 0}

    def _get_context_switches_linux(self) -> Dict[str, int]:
        """Get context switch statistics on Linux."""
        try:
            # Read from /proc/stat
            with open('/proc/stat', 'r') as f:
                stat_data = f.read()

            ctxt_line = None
            for line in stat_data.split('\n'):
                if line.startswith('ctxt'):
                    ctxt_line = line
                    break

            if ctxt_line:
                total_switches = int(ctxt_line.split()[1])

                # Calculate rate if we have previous measurement
                current_time = time.time()
                if hasattr(self, '_prev_ctxt_data'):
                    prev_switches, prev_time = self._prev_ctxt_data
                    rate = (total_switches - prev_switches) / (current_time - prev_time)
                else:
                    rate = 0

                self._prev_ctxt_data = (total_switches, current_time)

                # Get voluntary/involuntary breakdown from processes
                voluntary = 0
                involuntary = 0

                try:
                    for proc in psutil.process_iter(['pid']):
                        try:
                            pid = proc.info['pid']
                            with open(f'/proc/{pid}/status', 'r') as f:
                                status_data = f.read()

                            for line in status_data.split('\n'):
                                if line.startswith('voluntary_ctxt_switches:'):
                                    voluntary += int(line.split()[-1])
                                elif line.startswith('nonvoluntary_ctxt_switches:'):
                                    involuntary += int(line.split()[-1])

                        except (FileNotFoundError, ValueError, psutil.NoSuchProcess):
                            continue

                except Exception:
                    pass

                return {
                    'rate': rate,
                    'voluntary': voluntary,
                    'involuntary': involuntary
                }

        except Exception:
            pass

        return {'rate': 0, 'voluntary': 0, 'involuntary': 0}

    def _get_context_switches_windows(self) -> Dict[str, int]:
        """Get context switch statistics on Windows."""
        try:
            import subprocess
            result = subprocess.run(
                ['typeperf', '-sc', '1', '\\System\\Context Switches/sec'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Context Switches/sec' in line:
                        value = line.split(',')[-1].strip().replace('"', '')
                        try:
                            rate = float(value)
                            return {'rate': rate, 'voluntary': 0, 'involuntary': 0}
                        except ValueError:
                            pass

        except Exception:
            pass

        return {'rate': 0, 'voluntary': 0, 'involuntary': 0}

    def _get_context_switches_macos(self) -> Dict[str, int]:
        """Get context switch statistics on macOS."""
        try:
            import subprocess
            result = subprocess.run(
                ['sysctl', '-n', 'vm.stat'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Parse sysctl output for context switches
                # This is a simplified implementation
                return {'rate': 0, 'voluntary': 0, 'involuntary': 0}

        except Exception:
            pass

        return {'rate': 0, 'voluntary': 0, 'involuntary': 0}

    def _measure_scheduler_latency(self) -> float:
        """Measure scheduler latency by timing context switches."""
        try:
            import threading
            import time

            # Simple latency measurement using thread scheduling
            start_times = []
            end_times = []

            def worker():
                start_times.append(time.time())
                time.sleep(0.001)  # Minimal sleep to force context switch
                end_times.append(time.time())

            # Create several threads to measure average latency
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=worker)
                threads.append(thread)

            # Start all threads
            start_time = time.time()
            for thread in threads:
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join()

            if start_times and end_times:
                # Calculate average latency
                latencies = [(end - start) * 1000 for start, end in zip(start_times, end_times)]
                return sum(latencies) / len(latencies)

        except Exception:
            pass

        return 0.0

    def _get_load_averages(self) -> Tuple[float, float, float]:
        """Get system load averages."""
        try:
            if hasattr(os, 'getloadavg'):
                return os.getloadavg()
        except Exception:
            pass

        # Fallback for systems without getloadavg
        try:
            import platform
            if platform.system().lower() == 'linux':
                with open('/proc/loadavg', 'r') as f:
                    loadavg_data = f.read().strip()
                parts = loadavg_data.split()
                if len(parts) >= 3:
                    return (float(parts[0]), float(parts[1]), float(parts[2]))
        except Exception:
            pass

        return (0.0, 0.0, 0.0)

    def _count_processes_by_state(self) -> Tuple[int, int]:
        """Count processes by scheduling state."""
        try:
            runnable = 0
            blocked = 0

            for proc in psutil.process_iter(['status']):
                try:
                    status = proc.info['status']
                    if status in [psutil.STATUS_RUNNING, psutil.STATUS_WAKING]:
                        runnable += 1
                    elif status in [psutil.STATUS_SLEEPING, psutil.STATUS_DISK_SLEEP, psutil.STATUS_WAITING]:
                        blocked += 1
                except (psutil.NoSuchProcess, KeyError):
                    continue

            return runnable, blocked

        except Exception:
            return 0, 0

    def _calculate_scheduler_efficiency(self) -> float:
        """Calculate scheduler efficiency score."""
        try:
            # Get CPU utilization
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Get load average
            load_avg = self._get_load_averages()[0]  # 1-minute load average

            # Get number of CPUs
            cpu_count = psutil.cpu_count()

            # Calculate efficiency based on load vs. utilization
            if cpu_count > 0 and load_avg > 0:
                # Ideal efficiency: load average matches CPU count * utilization
                expected_load = (cpu_percent / 100) * cpu_count
                efficiency = min(100, (expected_load / load_avg) * 100)
                return max(0, efficiency)

            return 50.0  # Default neutral score

        except Exception:
            return 0.0

    def _get_interrupt_rates(self) -> Tuple[float, float]:
        """Get interrupt and softirq rates."""
        try:
            import platform
            system = platform.system().lower()

            if system == 'linux':
                return self._get_interrupt_rates_linux()

        except Exception:
            pass

        return 0.0, 0.0

    def _get_interrupt_rates_linux(self) -> Tuple[float, float]:
        """Get interrupt rates on Linux."""
        try:
            # Read interrupt counts
            with open('/proc/interrupts', 'r') as f:
                interrupts_data = f.read()

            # Count total interrupts
            total_interrupts = 0
            for line in interrupts_data.split('\n')[1:]:  # Skip header
                parts = line.split()
                if parts and parts[0].rstrip(':').isdigit():
                    # Sum interrupts across all CPUs
                    cpu_count = psutil.cpu_count()
                    for i in range(1, min(cpu_count + 1, len(parts))):
                        try:
                            total_interrupts += int(parts[i])
                        except ValueError:
                            break

            # Read softirq counts
            total_softirqs = 0
            try:
                with open('/proc/softirqs', 'r') as f:
                    softirqs_data = f.read()

                for line in softirqs_data.split('\n')[1:]:  # Skip header
                    parts = line.split()
                    if parts:
                        cpu_count = psutil.cpu_count()
                        for i in range(1, min(cpu_count + 1, len(parts))):
                            try:
                                total_softirqs += int(parts[i])
                            except ValueError:
                                break

            except FileNotFoundError:
                pass

            # Calculate rates
            current_time = time.time()
            if hasattr(self, '_prev_interrupt_data'):
                prev_interrupts, prev_softirqs, prev_time = self._prev_interrupt_data
                time_diff = current_time - prev_time

                interrupt_rate = (total_interrupts - prev_interrupts) / time_diff
                softirq_rate = (total_softirqs - prev_softirqs) / time_diff
            else:
                interrupt_rate = 0
                softirq_rate = 0

            self._prev_interrupt_data = (total_interrupts, total_softirqs, current_time)

            return interrupt_rate, softirq_rate

        except Exception:
            return 0.0, 0.0

    def _get_scheduling_policy_distribution(self) -> Dict[str, int]:
        """Get distribution of scheduling policies across processes."""
        distribution = defaultdict(int)

        try:
            for proc in psutil.process_iter(['pid']):
                try:
                    pid = proc.info['pid']

                    # Get scheduling policy (Linux)
                    try:
                        if SCHED_AVAILABLE:
                            policy = os.sched_getscheduler(pid)
                            policy_names = {
                                0: 'SCHED_OTHER',
                                1: 'SCHED_FIFO',
                                2: 'SCHED_RR',
                                3: 'SCHED_BATCH',
                                5: 'SCHED_IDLE',
                                6: 'SCHED_DEADLINE'
                            }
                            policy_name = policy_names.get(policy, f'UNKNOWN_{policy}')
                            distribution[policy_name] += 1
                        else:
                            # Fallback: categorize by nice value
                            nice = proc.nice()
                            if nice < 0:
                                distribution['HIGH_PRIORITY'] += 1
                            elif nice > 0:
                                distribution['LOW_PRIORITY'] += 1
                            else:
                                distribution['NORMAL_PRIORITY'] += 1

                    except (OSError, psutil.AccessDenied):
                        distribution['UNKNOWN'] += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception:
            pass

        return dict(distribution)

    def get_process_scheduling_info(self, pid: int) -> Optional[ProcessSchedulingInfo]:
        """Get detailed scheduling information for a specific process."""
        try:
            proc = psutil.Process(pid)

            # Get basic process info
            name = proc.name()
            priority = proc.nice()

            # Get CPU affinity
            try:
                cpu_affinity = proc.cpu_affinity()
            except (AttributeError, psutil.AccessDenied):
                cpu_affinity = []

            # Get CPU times
            cpu_times = proc.cpu_times()

            # Get process status
            status = proc.status()

            # Get scheduling policy and additional info (Linux)
            scheduling_policy = 'UNKNOWN'
            context_switches_vol = 0
            context_switches_invol = 0

            try:
                import platform
                if platform.system().lower() == 'linux':
                    # Read from /proc/PID/status
                    with open(f'/proc/{pid}/status', 'r') as f:
                        status_data = f.read()

                    for line in status_data.split('\n'):
                        if line.startswith('voluntary_ctxt_switches:'):
                            context_switches_vol = int(line.split()[-1])
                        elif line.startswith('nonvoluntary_ctxt_switches:'):
                            context_switches_invol = int(line.split()[-1])

                    # Get scheduling policy
                    if SCHED_AVAILABLE:
                        policy = os.sched_getscheduler(pid)
                        policy_names = {
                            0: 'SCHED_OTHER',
                            1: 'SCHED_FIFO',
                            2: 'SCHED_RR',
                            3: 'SCHED_BATCH',
                            5: 'SCHED_IDLE',
                            6: 'SCHED_DEADLINE'
                        }
                        scheduling_policy = policy_names.get(policy, f'UNKNOWN_{policy}')

            except (FileNotFoundError, ValueError, OSError):
                pass

            info = ProcessSchedulingInfo(
                pid=pid,
                name=name,
                priority=priority,
                nice_value=priority,
                scheduling_policy=scheduling_policy,
                cpu_affinity=cpu_affinity,
                context_switches_voluntary=context_switches_vol,
                context_switches_involuntary=context_switches_invol,
                cpu_time_user=cpu_times.user,
                cpu_time_system=cpu_times.system,
                wait_time_total=0,  # Would need more detailed tracking
                sleep_time_total=0,  # Would need more detailed tracking
                run_delay_total=0,  # Would need more detailed tracking
                timeslices_used=0,  # Would need kernel-level tracking
                preemptions=context_switches_invol,
                migrations=0,  # Would need more detailed tracking
                last_cpu=0,  # Would need more detailed tracking
                state=status
            )

            return info

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def get_cpu_scheduling_stats(self) -> List[CPUSchedulingStats]:
        """Get per-CPU scheduling statistics."""
        stats = []

        try:
            # Get per-CPU times
            cpu_times = psutil.cpu_times_percent(interval=0.1, percpu=True)
            cpu_count = len(cpu_times)

            for cpu_id, times in enumerate(cpu_times):
                # Calculate utilization
                utilization = 100 - times.idle

                # Get additional stats (Linux-specific)
                context_switches = 0
                interrupts = 0
                softirqs = 0

                try:
                    import platform
                    if platform.system().lower() == 'linux':
                        # Read per-CPU interrupt counts
                        with open('/proc/interrupts', 'r') as f:
                            interrupts_data = f.read()

                        for line in interrupts_data.split('\n')[1:]:
                            parts = line.split()
                            if parts and parts[0].rstrip(':').isdigit():
                                if cpu_id + 1 < len(parts):
                                    try:
                                        interrupts += int(parts[cpu_id + 1])
                                    except ValueError:
                                        pass

                        # Read per-CPU softirq counts
                        try:
                            with open('/proc/softirqs', 'r') as f:
                                softirqs_data = f.read()

                            for line in softirqs_data.split('\n')[1:]:
                                parts = line.split()
                                if parts and cpu_id + 1 < len(parts):
                                    try:
                                        softirqs += int(parts[cpu_id + 1])
                                    except ValueError:
                                        pass

                        except FileNotFoundError:
                            pass

                except Exception:
                    pass

                cpu_stat = CPUSchedulingStats(
                    cpu_id=cpu_id,
                    utilization_percent=utilization,
                    context_switches=context_switches,
                    interrupts=interrupts,
                    softirqs=softirqs,
                    idle_time_percent=times.idle,
                    iowait_time_percent=getattr(times, 'iowait', 0),
                    steal_time_percent=getattr(times, 'steal', 0),
                    guest_time_percent=getattr(times, 'guest', 0),
                    load_balance_count=0,  # Would need kernel-level tracking
                    migration_count=0,     # Would need kernel-level tracking
                    runqueue_length=0,     # Would need kernel-level tracking
                    average_latency_ms=0   # Would need kernel-level tracking
                )

                stats.append(cpu_stat)

        except Exception:
            pass

        return stats

    def analyze_scheduler_performance(self) -> Dict[str, Any]:
        """Analyze overall scheduler performance and provide insights."""
        try:
            if not self.metrics_history:
                return {"error": "No metrics history available"}

            recent_metrics = list(self.metrics_history)[-10:]  # Last 10 measurements

            # Calculate averages
            avg_context_switches = sum(m.context_switches_per_sec for m in recent_metrics) / len(recent_metrics)
            avg_latency = sum(m.scheduler_latency_ms for m in recent_metrics) / len(recent_metrics)
            avg_efficiency = sum(m.cpu_scheduler_efficiency for m in recent_metrics) / len(recent_metrics)
            avg_load = sum(m.load_average_1min for m in recent_metrics) / len(recent_metrics)

            # Get CPU count for analysis
            cpu_count = psutil.cpu_count()

            analysis = {
                'timestamp': datetime.now().isoformat(),
                'performance_summary': {
                    'average_context_switches_per_sec': avg_context_switches,
                    'average_scheduler_latency_ms': avg_latency,
                    'average_efficiency_score': avg_efficiency,
                    'average_load_1min': avg_load,
                    'cpu_count': cpu_count,
                    'load_per_cpu': avg_load / cpu_count if cpu_count > 0 else 0
                },
                'performance_assessment': self._assess_scheduler_performance(
                    avg_context_switches, avg_latency, avg_efficiency, avg_load, cpu_count
                ),
                'recent_metrics': [asdict(m) for m in recent_metrics],
                'cpu_scheduling_stats': [asdict(stat) for stat in self.get_cpu_scheduling_stats()],
                'recommendations': self._generate_scheduler_recommendations(
                    avg_context_switches, avg_latency, avg_efficiency, avg_load, cpu_count
                )
            }

            return analysis

        except Exception as e:
            return {"error": f"Scheduler analysis failed: {str(e)}"}

    def _assess_scheduler_performance(self, context_switches: float, latency: float,
                                    efficiency: float, load: float, cpu_count: int) -> Dict[str, str]:
        """Assess scheduler performance and categorize it."""
        assessment = {}

        # Context switch rate assessment
        if context_switches > 10000:
            assessment['context_switches'] = 'high'
        elif context_switches > 1000:
            assessment['context_switches'] = 'moderate'
        else:
            assessment['context_switches'] = 'low'

        # Latency assessment
        if latency > 10:
            assessment['latency'] = 'high'
        elif latency > 1:
            assessment['latency'] = 'moderate'
        else:
            assessment['latency'] = 'low'

        # Efficiency assessment
        if efficiency > 80:
            assessment['efficiency'] = 'excellent'
        elif efficiency > 60:
            assessment['efficiency'] = 'good'
        elif efficiency > 40:
            assessment['efficiency'] = 'fair'
        else:
            assessment['efficiency'] = 'poor'

        # Load assessment
        load_per_cpu = load / cpu_count if cpu_count > 0 else 0
        if load_per_cpu > 1.5:
            assessment['load'] = 'overloaded'
        elif load_per_cpu > 1.0:
            assessment['load'] = 'fully_loaded'
        elif load_per_cpu > 0.7:
            assessment['load'] = 'busy'
        else:
            assessment['load'] = 'light'

        # Overall assessment
        issues = sum(1 for v in assessment.values() if v in ['high', 'poor', 'overloaded'])
        if issues == 0:
            assessment['overall'] = 'excellent'
        elif issues <= 1:
            assessment['overall'] = 'good'
        elif issues <= 2:
            assessment['overall'] = 'fair'
        else:
            assessment['overall'] = 'poor'

        return assessment

    def _generate_scheduler_recommendations(self, context_switches: float, latency: float,
                                          efficiency: float, load: float, cpu_count: int) -> List[str]:
        """Generate recommendations for scheduler optimization."""
        recommendations = []

        # High context switch rate
        if context_switches > 10000:
            recommendations.append("High context switch rate detected - consider reducing thread count or optimizing thread synchronization")

        # High scheduler latency
        if latency > 10:
            recommendations.append("High scheduler latency detected - check for CPU-bound processes or system overload")

        # Low efficiency
        if efficiency < 40:
            recommendations.append("Low scheduler efficiency - investigate process priorities and CPU affinity settings")

        # High load
        load_per_cpu = load / cpu_count if cpu_count > 0 else 0
        if load_per_cpu > 1.5:
            recommendations.append("System overloaded - consider reducing workload or adding more CPU cores")
        elif load_per_cpu > 1.0:
            recommendations.append("System fully loaded - monitor for performance degradation")

        # General recommendations
        if not recommendations:
            recommendations.append("Scheduler performance appears optimal")

        return recommendations

    def export_scheduler_analysis(self, file_path: Path) -> bool:
        """Export comprehensive scheduler analysis report."""
        try:
            analysis = self.analyze_scheduler_performance()
            current_metrics = self.get_scheduler_metrics()

            export_data = {
                'timestamp': int(time.time() * 1000),
                'generated_at': datetime.now().isoformat(),
                'current_metrics': asdict(current_metrics),
                'performance_analysis': analysis,
                'metrics_history': [asdict(m) for m in list(self.metrics_history)],
                'metadata': {
                    'sched_available': SCHED_AVAILABLE,
                    'monitoring_duration_minutes': len(self.metrics_history),
                    'cpu_count': psutil.cpu_count(),
                    'report_version': '1.0'
                }
            }

            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

            return True

        except Exception:
            return False

    def start_monitoring(self, interval_seconds: int = 1):
        """Start continuous scheduler monitoring."""
        def monitor_loop():
            while self.monitoring_active:
                try:
                    self.get_scheduler_metrics()
                    time.sleep(interval_seconds)
                except Exception:
                    time.sleep(interval_seconds)

        if not self.monitoring_active:
            self.monitoring_active = True
            monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
            monitor_thread.start()

    def stop_monitoring(self):
        """Stop continuous scheduler monitoring."""
        self.monitoring_active = False