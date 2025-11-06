"""
Personal use enhancements for Moni system monitor.
Features optimized for individual users and home environments.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ProductivitySession:
    """Track user productivity sessions and focus time."""

    start_time: float
    end_time: Optional[float] = None
    active_time: float = 0.0
    idle_time: float = 0.0
    app_usage: Dict[str, float] = None

    def __post_init__(self):
        if self.app_usage is None:
            self.app_usage = {}

    @property
    def duration(self) -> float:
        """Total session duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def productivity_score(self) -> float:
        """Calculate productivity score (0-100)."""
        if self.duration == 0:
            return 0.0
        active_ratio = self.active_time / self.duration
        return min(100.0, active_ratio * 100.0)


class ProductivityTracker:
    """Track user productivity and computer usage patterns."""

    def __init__(self, idle_threshold_seconds: int = 300):
        self.idle_threshold = idle_threshold_seconds
        self.current_session: Optional[ProductivitySession] = None
        self.session_history: List[ProductivitySession] = []
        self.last_activity_time = time.time()

    def start_session(self) -> None:
        """Start a new productivity session."""
        if self.current_session and not self.current_session.end_time:
            self.end_session()

        self.current_session = ProductivitySession(start_time=time.time())
        self.last_activity_time = time.time()
        logger.info("Productivity session started")

    def end_session(self) -> None:
        """End the current productivity session."""
        if not self.current_session:
            return

        self.current_session.end_time = time.time()
        self.session_history.append(self.current_session)
        logger.info(
            "Productivity session ended",
            extra={
                "duration": self.current_session.duration,
                "score": self.current_session.productivity_score,
            }
        )
        self.current_session = None

    def update_activity(self, is_active: bool) -> None:
        """Update user activity status."""
        if not self.current_session:
            return

        now = time.time()
        delta = now - self.last_activity_time

        if is_active:
            self.current_session.active_time += delta
        else:
            self.current_session.idle_time += delta

        self.last_activity_time = now

    def get_today_stats(self) -> Dict[str, float]:
        """Get productivity statistics for today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_timestamp = today_start.timestamp()

        today_sessions = [
            s for s in self.session_history
            if s.start_time >= today_timestamp
        ]

        total_duration = sum(s.duration for s in today_sessions)
        total_active = sum(s.active_time for s in today_sessions)
        avg_score = sum(s.productivity_score for s in today_sessions) / max(1, len(today_sessions))

        return {
            "total_hours": total_duration / 3600,
            "active_hours": total_active / 3600,
            "session_count": len(today_sessions),
            "average_score": avg_score,
        }


class GameModeDetector:
    """Detect when user is gaming to optimize monitoring behavior."""

    # Common game process names and patterns
    GAME_PROCESSES = {
        # Steam games
        "steam.exe", "steamwebhelper.exe",
        # Epic Games
        "epicgameslauncher.exe",
        # Popular games
        "gta5.exe", "cyberpunk2077.exe", "minecraft.exe",
        "valorant.exe", "league of legends.exe",
        "dota2.exe", "csgo.exe", "cs2.exe",
        # Game engines
        "unrealengine.exe", "unity.exe",
    }

    def __init__(self):
        self._gaming_mode = False
        self._last_check = 0.0
        self._check_interval = 5.0  # Check every 5 seconds

    def is_gaming(self) -> bool:
        """Check if user is currently gaming."""
        now = time.time()
        if now - self._last_check < self._check_interval:
            return self._gaming_mode

        self._last_check = now
        self._gaming_mode = self._detect_gaming_activity()
        return self._gaming_mode

    def _detect_gaming_activity(self) -> bool:
        """Detect gaming activity through various signals."""
        # Check for fullscreen applications
        if self._is_fullscreen_app_active():
            return True

        # Check for game processes
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                proc_name = proc.info['name'].lower() if proc.info['name'] else ""
                if any(game in proc_name for game in self.GAME_PROCESSES):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return False

    def _is_fullscreen_app_active(self) -> bool:
        """Check if a fullscreen application is running."""
        # Platform-specific fullscreen detection
        system = platform.system()

        if system == "Windows":
            return self._is_fullscreen_windows()
        elif system == "Darwin":  # macOS
            return self._is_fullscreen_macos()
        elif system == "Linux":
            return self._is_fullscreen_linux()

        return False

    def _is_fullscreen_windows(self) -> bool:
        """Windows fullscreen detection."""
        try:
            import win32gui
            import win32api

            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]

                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)

                # Consider fullscreen if window covers >95% of screen
                return width >= screen_width * 0.95 and height >= screen_height * 0.95
        except ImportError:
            pass
        return False

    def _is_fullscreen_macos(self) -> bool:
        """macOS fullscreen detection."""
        # macOS fullscreen detection requires AppKit
        return False

    def _is_fullscreen_linux(self) -> bool:
        """Linux fullscreen detection."""
        # Linux fullscreen detection varies by window manager
        return False


class PersonalInsights:
    """Generate personal insights from system usage data."""

    def __init__(self):
        self.boot_time = psutil.boot_time()

    def get_daily_summary(self) -> Dict[str, any]:
        """Generate daily usage summary."""
        uptime = time.time() - self.boot_time

        cpu_history = self._get_cpu_history()
        mem_history = self._get_memory_history()

        return {
            "uptime_hours": uptime / 3600,
            "avg_cpu_usage": sum(cpu_history) / max(1, len(cpu_history)),
            "avg_memory_usage": sum(mem_history) / max(1, len(mem_history)),
            "peak_cpu": max(cpu_history) if cpu_history else 0,
            "peak_memory": max(mem_history) if mem_history else 0,
            "top_processes": self._get_top_processes(5),
        }

    def _get_cpu_history(self) -> List[float]:
        """Get recent CPU usage history."""
        # This would integrate with metrics.py history
        return []

    def _get_memory_history(self) -> List[float]:
        """Get recent memory usage history."""
        # This would integrate with metrics.py history
        return []

    def _get_top_processes(self, limit: int = 5) -> List[Tuple[str, float]]:
        """Get top processes by CPU or memory usage."""
        processes = []
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append((
                    proc.info['name'],
                    proc.info['cpu_percent'] or 0.0
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(key=lambda x: x[1], reverse=True)
        return processes[:limit]


class QuickActions:
    """Quick actions for common personal computing tasks."""

    @staticmethod
    def clear_temp_files() -> Tuple[int, int]:
        """Clear temporary files and return (files_removed, bytes_freed)."""
        files_removed = 0
        bytes_freed = 0

        temp_dirs = []
        system = platform.system()

        if system == "Windows":
            temp_dirs = [
                Path(os.environ.get("TEMP", "")),
                Path(os.environ.get("TMP", "")),
            ]
        elif system == "Darwin" or system == "Linux":
            temp_dirs = [Path("/tmp"), Path.home() / ".cache"]

        for temp_dir in temp_dirs:
            if not temp_dir.exists():
                continue

            for item in temp_dir.iterdir():
                try:
                    if item.is_file():
                        size = item.stat().st_size
                        item.unlink()
                        files_removed += 1
                        bytes_freed += size
                except (PermissionError, OSError):
                    continue

        logger.info(
            "Temp files cleared",
            extra={"files": files_removed, "bytes": bytes_freed}
        )
        return files_removed, bytes_freed

    @staticmethod
    def optimize_startup() -> List[str]:
        """Identify and disable unnecessary startup programs."""
        # Platform-specific startup program management
        disabled_programs = []

        system = platform.system()
        if system == "Windows":
            disabled_programs = QuickActions._optimize_startup_windows()
        elif system == "Darwin":
            disabled_programs = QuickActions._optimize_startup_macos()
        elif system == "Linux":
            disabled_programs = QuickActions._optimize_startup_linux()

        return disabled_programs

    @staticmethod
    def _optimize_startup_windows() -> List[str]:
        """Optimize Windows startup programs."""
        # Would use Windows Registry or Task Scheduler
        return []

    @staticmethod
    def _optimize_startup_macos() -> List[str]:
        """Optimize macOS login items."""
        # Would use launchctl
        return []

    @staticmethod
    def _optimize_startup_linux() -> List[str]:
        """Optimize Linux autostart applications."""
        autostart_dir = Path.home() / ".config" / "autostart"
        disabled = []

        if autostart_dir.exists():
            for desktop_file in autostart_dir.glob("*.desktop"):
                # Read and analyze .desktop files
                pass

        return disabled


# Global instances for easy access
_productivity_tracker: Optional[ProductivityTracker] = None
_game_mode_detector: Optional[GameModeDetector] = None
_personal_insights: Optional[PersonalInsights] = None


def get_productivity_tracker() -> ProductivityTracker:
    """Get the global productivity tracker instance."""
    global _productivity_tracker
    if _productivity_tracker is None:
        _productivity_tracker = ProductivityTracker()
    return _productivity_tracker


def get_game_mode_detector() -> GameModeDetector:
    """Get the global game mode detector instance."""
    global _game_mode_detector
    if _game_mode_detector is None:
        _game_mode_detector = GameModeDetector()
    return _game_mode_detector


def get_personal_insights() -> PersonalInsights:
    """Get the global personal insights instance."""
    global _personal_insights
    if _personal_insights is None:
        _personal_insights = PersonalInsights()
    return _personal_insights
