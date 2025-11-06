"""Advanced process management with search, filtering, and control capabilities."""

from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum
import psutil
import threading


class ProcessStatus(Enum):
    """Process status enumeration."""
    RUNNING = "running"
    SLEEPING = "sleeping"
    DISK_SLEEP = "disk-sleep"
    STOPPED = "stopped"
    TRACING_STOP = "tracing-stop"
    ZOMBIE = "zombie"
    DEAD = "dead"
    WAKE_KILL = "wake-kill"
    WAKING = "waking"
    IDLE = "idle"
    LOCKED = "locked"
    WAITING = "waiting"
    SUSPENDED = "suspended"


class ProcessPriority(Enum):
    """Process priority levels."""
    REALTIME = "realtime"
    HIGH = "high"
    ABOVE_NORMAL = "above_normal"
    NORMAL = "normal"
    BELOW_NORMAL = "below_normal"
    IDLE = "idle"


@dataclass
class ProcessInfo:
    """Comprehensive process information."""
    pid: int
    ppid: int
    name: str
    status: ProcessStatus
    cpu_percent: float
    memory_percent: float
    memory_rss: int  # bytes
    memory_vms: int  # bytes
    create_time: float
    priority: int
    nice: int
    num_threads: int
    num_handles: int
    cmdline: List[str]
    cwd: str
    username: str
    connections: int
    children_count: int
    is_system_process: bool
    executable: str
    environment: Dict[str, str]


class ProcessSearchFilter:
    """Advanced process search and filtering."""

    def __init__(self):
        self.name_filter: Optional[str] = None
        self.pid_filter: Optional[int] = None
        self.status_filter: Optional[ProcessStatus] = None
        self.cpu_threshold: Optional[float] = None
        self.memory_threshold: Optional[float] = None
        self.user_filter: Optional[str] = None
        self.parent_pid_filter: Optional[int] = None
        self.min_threads: Optional[int] = None
        self.system_processes: Optional[bool] = None
        self.search_cmdline: bool = False
        self.case_sensitive: bool = False

    def matches(self, process_info: ProcessInfo) -> bool:
        """Check if process matches all filter criteria."""
        # Name filter
        if self.name_filter:
            search_text = self.name_filter
            target_text = process_info.name
            if self.search_cmdline and process_info.cmdline:
                target_text += " " + " ".join(process_info.cmdline)

            if not self.case_sensitive:
                search_text = search_text.lower()
                target_text = target_text.lower()

            if search_text not in target_text:
                return False

        # PID filter
        if self.pid_filter is not None and process_info.pid != self.pid_filter:
            return False

        # Status filter
        if self.status_filter and process_info.status != self.status_filter:
            return False

        # CPU threshold
        if self.cpu_threshold is not None and process_info.cpu_percent < self.cpu_threshold:
            return False

        # Memory threshold
        if self.memory_threshold is not None and process_info.memory_percent < self.memory_threshold:
            return False

        # User filter
        if self.user_filter and self.user_filter.lower() not in process_info.username.lower():
            return False

        # Parent PID filter
        if self.parent_pid_filter is not None and process_info.ppid != self.parent_pid_filter:
            return False

        # Thread count filter
        if self.min_threads is not None and process_info.num_threads < self.min_threads:
            return False

        # System process filter
        if self.system_processes is not None and process_info.is_system_process != self.system_processes:
            return False

        return True


class ProcessManager:
    """Advanced process management with enhanced capabilities."""

    def __init__(self):
        self.process_cache: Dict[int, ProcessInfo] = {}
        self.last_update: float = 0
        self.cache_duration: float = 2.0  # seconds
        self.monitoring_pids: Set[int] = set()
        self.process_listeners: List[Callable[[ProcessInfo, str], None]] = []
        self.system_process_names = {
            'system', 'kernel_task', 'kthreadd', 'ksoftirqd', 'migration',
            'rcu_', 'watchdog', 'systemd', 'init', 'kworker', 'dbus',
            'NetworkManager', 'polkitd', 'rtkit-daemon', 'udisks2'
        }

    def get_process_list(self, filter_obj: Optional[ProcessSearchFilter] = None, force_refresh: bool = False) -> List[ProcessInfo]:
        """Get filtered process list with caching."""
        current_time = time.time()

        if force_refresh or (current_time - self.last_update) > self.cache_duration:
            self._update_process_cache()
            self.last_update = current_time

        processes = list(self.process_cache.values())

        if filter_obj:
            processes = [p for p in processes if filter_obj.matches(p)]

        return processes

    def _update_process_cache(self):
        """Update the internal process cache."""
        new_cache = {}

        for proc in psutil.process_iter():
            try:
                process_info = self._get_process_info(proc)
                new_cache[process_info.pid] = process_info
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Notify listeners of process changes
        self._notify_process_changes(self.process_cache, new_cache)
        self.process_cache = new_cache

    def _get_process_info(self, proc: psutil.Process) -> ProcessInfo:
        """Extract comprehensive process information."""
        with proc.oneshot():
            try:
                # Basic info
                pid = proc.pid
                ppid = proc.ppid()
                name = proc.name()
                status = ProcessStatus(proc.status())
                cpu_percent = proc.cpu_percent()
                memory_percent = proc.memory_percent()
                memory_info = proc.memory_info()
                create_time = proc.create_time()
                priority = getattr(proc, 'nice', lambda: 0)()
                nice = priority
                num_threads = proc.num_threads()

                # Extended info with fallbacks
                try:
                    cmdline = proc.cmdline()
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    cmdline = []

                try:
                    cwd = proc.cwd()
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    cwd = ""

                try:
                    username = proc.username()
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    username = ""

                try:
                    connections = len(proc.connections())
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    connections = 0

                try:
                    children = proc.children()
                    children_count = len(children)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    children_count = 0

                try:
                    num_handles = proc.num_handles() if hasattr(proc, 'num_handles') else 0
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    num_handles = 0

                try:
                    executable = proc.exe()
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    executable = ""

                try:
                    environment = proc.environ()
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    environment = {}

                # Determine if system process
                is_system_process = any(sys_name in name.lower() for sys_name in self.system_process_names)
                is_system_process = is_system_process or pid < 1000  # Common system PID range

                return ProcessInfo(
                    pid=pid,
                    ppid=ppid,
                    name=name,
                    status=status,
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    memory_rss=memory_info.rss,
                    memory_vms=memory_info.vms,
                    create_time=create_time,
                    priority=priority,
                    nice=nice,
                    num_threads=num_threads,
                    num_handles=num_handles,
                    cmdline=cmdline,
                    cwd=cwd,
                    username=username,
                    connections=connections,
                    children_count=children_count,
                    is_system_process=is_system_process,
                    executable=executable,
                    environment=environment
                )
            except Exception as e:
                # Fallback for processes that can't be fully accessed
                return ProcessInfo(
                    pid=proc.pid,
                    ppid=0,
                    name=proc.name() if hasattr(proc, 'name') else f"PID-{proc.pid}",
                    status=ProcessStatus.RUNNING,
                    cpu_percent=0.0,
                    memory_percent=0.0,
                    memory_rss=0,
                    memory_vms=0,
                    create_time=0,
                    priority=0,
                    nice=0,
                    num_threads=0,
                    num_handles=0,
                    cmdline=[],
                    cwd="",
                    username="",
                    connections=0,
                    children_count=0,
                    is_system_process=True,
                    executable="",
                    environment={}
                )

    def _notify_process_changes(self, old_cache: Dict[int, ProcessInfo], new_cache: Dict[int, ProcessInfo]):
        """Notify listeners about process changes."""
        # New processes
        for pid, process_info in new_cache.items():
            if pid not in old_cache:
                for listener in self.process_listeners:
                    listener(process_info, "started")

        # Terminated processes
        for pid, process_info in old_cache.items():
            if pid not in new_cache:
                for listener in self.process_listeners:
                    listener(process_info, "terminated")

    def kill_process(self, pid: int, force: bool = False) -> Dict[str, Any]:
        """Kill a process with optional force parameter."""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()

            if force:
                proc.kill()  # SIGKILL
                method = "SIGKILL (forced)"
            else:
                proc.terminate()  # SIGTERM
                method = "SIGTERM (graceful)"

            # Wait for termination
            try:
                proc.wait(timeout=5)
                status = "terminated"
            except psutil.TimeoutExpired:
                if not force:
                    # Try force kill if graceful failed
                    proc.kill()
                    try:
                        proc.wait(timeout=3)
                        status = "force_terminated"
                        method = "SIGKILL (after timeout)"
                    except psutil.TimeoutExpired:
                        status = "timeout"
                else:
                    status = "timeout"

            return {
                "success": True,
                "pid": pid,
                "name": proc_name,
                "method": method,
                "status": status
            }

        except psutil.NoSuchProcess:
            return {
                "success": False,
                "error": f"Process {pid} not found",
                "pid": pid
            }
        except psutil.AccessDenied:
            return {
                "success": False,
                "error": f"Access denied to process {pid}",
                "pid": pid
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to kill process {pid}: {str(e)}",
                "pid": pid
            }

    def set_process_priority(self, pid: int, priority: ProcessPriority) -> Dict[str, Any]:
        """Set process priority/nice value."""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            old_priority = proc.nice()

            # Map priority enum to nice values
            priority_map = {
                ProcessPriority.REALTIME: psutil.REALTIME_PRIORITY_CLASS if hasattr(psutil, 'REALTIME_PRIORITY_CLASS') else -20,
                ProcessPriority.HIGH: psutil.HIGH_PRIORITY_CLASS if hasattr(psutil, 'HIGH_PRIORITY_CLASS') else -10,
                ProcessPriority.ABOVE_NORMAL: psutil.ABOVE_NORMAL_PRIORITY_CLASS if hasattr(psutil, 'ABOVE_NORMAL_PRIORITY_CLASS') else -5,
                ProcessPriority.NORMAL: psutil.NORMAL_PRIORITY_CLASS if hasattr(psutil, 'NORMAL_PRIORITY_CLASS') else 0,
                ProcessPriority.BELOW_NORMAL: psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil, 'BELOW_NORMAL_PRIORITY_CLASS') else 5,
                ProcessPriority.IDLE: psutil.IDLE_PRIORITY_CLASS if hasattr(psutil, 'IDLE_PRIORITY_CLASS') else 19,
            }

            new_priority_value = priority_map[priority]
            proc.nice(new_priority_value)

            return {
                "success": True,
                "pid": pid,
                "name": proc_name,
                "old_priority": old_priority,
                "new_priority": proc.nice(),
                "priority_class": priority.value
            }

        except psutil.NoSuchProcess:
            return {
                "success": False,
                "error": f"Process {pid} not found",
                "pid": pid
            }
        except psutil.AccessDenied:
            return {
                "success": False,
                "error": f"Access denied to process {pid}",
                "pid": pid
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to set priority for process {pid}: {str(e)}",
                "pid": pid
            }

    def get_process_tree(self, root_pid: Optional[int] = None) -> Dict[int, List[int]]:
        """Get process tree structure."""
        tree = {}

        for process_info in self.process_cache.values():
            parent_pid = process_info.ppid
            child_pid = process_info.pid

            if parent_pid not in tree:
                tree[parent_pid] = []
            tree[parent_pid].append(child_pid)

        if root_pid is not None:
            # Return subtree starting from root_pid
            subtree = {}

            def collect_children(pid):
                if pid in tree:
                    subtree[pid] = tree[pid]
                    for child_pid in tree[pid]:
                        collect_children(child_pid)

            collect_children(root_pid)
            return subtree

        return tree

    def suspend_process(self, pid: int) -> Dict[str, Any]:
        """Suspend a process."""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc.suspend()

            return {
                "success": True,
                "pid": pid,
                "name": proc_name,
                "action": "suspended"
            }

        except psutil.NoSuchProcess:
            return {
                "success": False,
                "error": f"Process {pid} not found",
                "pid": pid
            }
        except psutil.AccessDenied:
            return {
                "success": False,
                "error": f"Access denied to process {pid}",
                "pid": pid
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to suspend process {pid}: {str(e)}",
                "pid": pid
            }

    def resume_process(self, pid: int) -> Dict[str, Any]:
        """Resume a suspended process."""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc.resume()

            return {
                "success": True,
                "pid": pid,
                "name": proc_name,
                "action": "resumed"
            }

        except psutil.NoSuchProcess:
            return {
                "success": False,
                "error": f"Process {pid} not found",
                "pid": pid
            }
        except psutil.AccessDenied:
            return {
                "success": False,
                "error": f"Access denied to process {pid}",
                "pid": pid
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to resume process {pid}: {str(e)}",
                "pid": pid
            }

    def add_process_listener(self, listener: Callable[[ProcessInfo, str], None]):
        """Add a listener for process events."""
        self.process_listeners.append(listener)

    def remove_process_listener(self, listener: Callable[[ProcessInfo, str], None]):
        """Remove a process event listener."""
        if listener in self.process_listeners:
            self.process_listeners.remove(listener)

    def get_statistics(self) -> Dict[str, Any]:
        """Get process statistics summary."""
        processes = list(self.process_cache.values())

        if not processes:
            return {"error": "No process data available"}

        total_processes = len(processes)
        running_processes = len([p for p in processes if p.status == ProcessStatus.RUNNING])
        sleeping_processes = len([p for p in processes if p.status == ProcessStatus.SLEEPING])
        zombie_processes = len([p for p in processes if p.status == ProcessStatus.ZOMBIE])

        total_memory = sum(p.memory_rss for p in processes)
        avg_cpu = sum(p.cpu_percent for p in processes) / total_processes

        top_cpu = sorted(processes, key=lambda x: x.cpu_percent, reverse=True)[:5]
        top_memory = sorted(processes, key=lambda x: x.memory_rss, reverse=True)[:5]

        return {
            "total_processes": total_processes,
            "running": running_processes,
            "sleeping": sleeping_processes,
            "zombie": zombie_processes,
            "total_memory_bytes": total_memory,
            "average_cpu_percent": avg_cpu,
            "top_cpu_processes": [{"pid": p.pid, "name": p.name, "cpu": p.cpu_percent} for p in top_cpu],
            "top_memory_processes": [{"pid": p.pid, "name": p.name, "memory": p.memory_rss} for p in top_memory],
            "cache_age_seconds": time.time() - self.last_update
        }