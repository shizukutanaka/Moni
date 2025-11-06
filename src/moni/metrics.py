from __future__ import annotations

import atexit
import json
import logging
import platform
import subprocess
import threading
import time
from collections import defaultdict, deque
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple

import re

import psutil

from .enhanced_security import AdvancedInputValidator, EnhancedValidationError

try:
    from .timeseries_db import write_metric_to_timeseries
    HAS_TIMESERIES = True
except ImportError:
    HAS_TIMESERIES = False

try:
    import pynvml  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pynvml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_cpu_sample_lock = threading.Lock()
_last_cpu_sample_time: float = 0.0
_last_cpu_percent: Optional[float] = None

with suppress(Exception):
    psutil.cpu_percent(interval=None)

_nvml_lock = threading.Lock()
_nvml_initialized = False


def _get_cpu_percent_efficient() -> Optional[float]:
    """CPU使用率を効率的に取得（キャッシュを使用）"""
    global _last_cpu_sample_time, _last_cpu_percent

    current_time = time.time()

    # 前回のサンプルから1秒以上経過していない場合はキャッシュを使用
    if _last_cpu_percent is not None and (current_time - _last_cpu_sample_time) < 1.0:
        return _last_cpu_percent

    try:
        # 非ブロッキングモードでCPU使用率を取得
        percent = psutil.cpu_percent(interval=0.1)  # 短いインターバルで効率化
        _last_cpu_percent = percent
        _last_cpu_sample_time = current_time
        return percent
    except Exception:
        return None


def _ensure_nvml_initialized() -> bool:
    """NVMLの初期化を効率化"""
    global _nvml_initialized

    if pynvml is None:
        return False

    with _nvml_lock:
        if _nvml_initialized:
            return True

        try:
            # タイムアウト付きで初期化（CPU使用量削減）
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("NVML initialization timeout")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)  # 5秒タイムアウト

            try:
                pynvml.nvmlInit()
                _nvml_initialized = True
                return True
            finally:
                signal.alarm(0)  # タイムアウト解除

        except (TimeoutError, Exception):
            logger.debug("NVML initialization failed or timed out", exc_info=True)
            return False


def _shutdown_nvml() -> None:
    """Shutdown NVML on interpreter exit to release resources."""

    global _nvml_initialized

    if pynvml is None:
        return
    with _nvml_lock:
        if not _nvml_initialized:
            return
        with suppress(Exception):
            pynvml.nvmlShutdown()
        _nvml_initialized = False


atexit.register(_shutdown_nvml)


def _iter_nvml_devices() -> Iterator[Tuple[int, Any]]:
    """Yield available NVML device handles without repeated init/shutdown."""

    if not _ensure_nvml_initialized():
        return

    try:
        device_count = pynvml.nvmlDeviceGetCount()  # type: ignore[call-arg]
    except Exception:  # pragma: no cover - depends on GPU environment
        logger.debug("Failed to query NVML device count", exc_info=True)
        return

    for index in range(device_count):
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - depends on GPU environment
            logger.debug("Failed to acquire NVML handle for device %s", index, exc_info=True)
            continue
        yield index, handle

# Global metric history storage for trend analysis
_metric_history_cache: Dict[str, deque] = {}
_history_lock = threading.Lock()

try:
    from .external_integrations import external_integration_collector
except ImportError:
    external_integration_collector = lambda: {"Error": "External integrations module not available"}

_disk_health_monitor: Optional[DiskHealthMonitor] = None
_disk_health_lock = threading.Lock()

try:
    from .network_monitor import NetworkMonitor
except Exception:  # pragma: no cover - optional dependency chain
    NetworkMonitor = None  # type: ignore[assignment]

_network_monitor: Optional[NetworkMonitor] = None
_network_monitor_lock = threading.Lock()
_network_bandwidth_overrides: Dict[str, str] = {}
_network_bandwidth_enabled: bool = False
_network_bandwidth_continuous: bool = False
_network_bandwidth_cooldown: int = 900

_network_quality_settings: Dict[str, Any] = {
    "enabled": False,
    "hosts": [],
    "attempts": 3,
    "timeout_ms": 800,
    "cooldown_seconds": 120,
}
_network_quality_last_run: Optional[float] = None
_MAX_NETWORK_QUALITY_HOSTS = 10

_HOSTNAME_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+$")

_interface_stats_cache: Dict[str, Tuple[int, int, float]] = {}
_interface_stats_lock = threading.Lock()

_battery_history: Deque[Tuple[float, float]] = deque(maxlen=120)  # Reduced from 180 for memory efficiency
_battery_history_lock = threading.Lock()
_BATTERY_HISTORY_WINDOW_SECONDS = 10 * 60  # Reduced from 15 minutes to 10 minutes

_temperature_history: Dict[str, Deque[Tuple[float, float]]] = defaultdict(lambda: deque(maxlen=100))  # Reduced from 120
_temperature_history_lock = threading.Lock()
_TEMPERATURE_HISTORY_WINDOW_SECONDS = 8 * 60  # Reduced from 10 minutes to 8 minutes

_fan_history: Dict[str, Deque[Tuple[float, float]]] = defaultdict(lambda: deque(maxlen=100))  # Reduced from 120
_fan_history_lock = threading.Lock()
_FAN_HISTORY_WINDOW_SECONDS = 8 * 60  # Reduced from 10 minutes to 8 minutes

_disk_latency_cache: Dict[str, Tuple[float, int, int, float, float, float]] = {}
_disk_latency_history: Dict[str, Deque[Tuple[float, float]]] = defaultdict(lambda: deque(maxlen=120))  # Reduced from 180 for memory efficiency
_disk_latency_lock = threading.Lock()
_DISK_LATENCY_WINDOW_SECONDS = 15 * 60


def configure_network_monitor_bandwidth(settings: Mapping[str, Any]) -> None:
    """Configure global network monitor bandwidth endpoints."""

    global _network_bandwidth_overrides
    global _network_bandwidth_enabled
    global _network_bandwidth_continuous
    global _network_bandwidth_cooldown
    global _network_monitor

    overrides: Dict[str, str] = {}
    enabled = False
    continuous = False
    cooldown_seconds = 900

    endpoint_candidates = {
        "download": settings.get("download_endpoint") or settings.get("download"),
        "upload": settings.get("upload_endpoint") or settings.get("upload"),
    }

    raw_enabled = settings.get("enabled")
    if isinstance(raw_enabled, str):
        enabled = raw_enabled.strip().lower() in {"1", "true", "yes", "on"}
    elif isinstance(raw_enabled, bool):
        enabled = raw_enabled

    raw_continuous = settings.get("continuous_monitoring")
    if isinstance(raw_continuous, str):
        continuous = raw_continuous.strip().lower() in {"1", "true", "yes", "on"}
    elif isinstance(raw_continuous, bool):
        continuous = raw_continuous

    raw_cooldown = settings.get("cooldown_seconds")
    try:
        cooldown_seconds = int(raw_cooldown)
    except (TypeError, ValueError):
        cooldown_seconds = 900
    cooldown_seconds = max(60, min(cooldown_seconds, 86_400))

    for key, candidate in endpoint_candidates.items():
        if not isinstance(candidate, str):
            continue
        try:
            sanitized = InputValidator.validate_https_url(candidate)
        except SecurityValidationError as exc:
            logger.warning(
                "Rejected bandwidth endpoint override",
                extra={"endpoint_type": key, "value": candidate, "error": str(exc)},
            )
            continue

        overrides[key] = sanitized

    with _network_monitor_lock:
        _network_bandwidth_enabled = enabled and bool(overrides)
        _network_bandwidth_continuous = _network_bandwidth_enabled and continuous
        _network_bandwidth_cooldown = cooldown_seconds

        if not _network_bandwidth_enabled:
            _network_bandwidth_overrides.clear()
            if _network_monitor is not None:
                _network_monitor.configure_bandwidth_endpoints(
                    {},
                    enabled=False,
                    continuous=False,
                    cooldown=cooldown_seconds,
                )
            return

        _network_bandwidth_overrides.update(overrides)
        if _network_monitor is not None:
            _network_monitor.configure_bandwidth_endpoints(
                dict(_network_bandwidth_overrides),
                enabled=True,
                continuous=_network_bandwidth_continuous,
                cooldown=_network_bandwidth_cooldown,
            )


def configure_network_quality(settings: Mapping[str, Any]) -> None:
    """Configure network quality probe behaviour."""

    global _network_quality_settings, _network_quality_last_run

    enabled = False
    hosts: List[str] = []
    attempts = 3
    timeout_ms = 800
    cooldown_seconds = 120

    raw_enabled = settings.get("enabled")
    if isinstance(raw_enabled, str):
        enabled = raw_enabled.strip().lower() in {"1", "true", "yes", "on"}
    elif isinstance(raw_enabled, bool):
        enabled = raw_enabled

    raw_hosts = settings.get("hosts")
    if isinstance(raw_hosts, str):
        candidate_hosts = [item.strip() for item in raw_hosts.split(",") if item.strip()]
    elif isinstance(raw_hosts, (list, tuple)):
        candidate_hosts = [str(item).strip() for item in raw_hosts if str(item).strip()]
    else:
        candidate_hosts = []

    for entry in candidate_hosts:
        try:
            hosts.append(InputValidator.validate_ip_address(entry))
            continue
        except SecurityValidationError:
            pass

        try:
            sanitized_host = InputValidator.validate_hostname(entry.lower())
        except SecurityValidationError as error:
            logger.warning(
                "Rejected network quality host",
                extra={"value": entry, "error": str(error)},
            )
            continue

        hosts.append(sanitized_host)

    if hosts:
        # Preserve insertion order but remove duplicates
        hosts = list(dict.fromkeys(hosts))
        if len(hosts) > _MAX_NETWORK_QUALITY_HOSTS:
            logger.warning(
                "Trimming network quality hosts to limit",
                extra={"requested": len(hosts), "limit": _MAX_NETWORK_QUALITY_HOSTS},
            )
            hosts = hosts[:_MAX_NETWORK_QUALITY_HOSTS]

    raw_attempts = settings.get("attempts")
    try:
        attempts = int(raw_attempts)
    except (TypeError, ValueError):
        attempts = 3
    attempts = max(1, min(attempts, 10))

    raw_timeout = settings.get("timeout_ms") or settings.get("timeout")
    try:
        timeout_ms = int(raw_timeout)
    except (TypeError, ValueError):
        timeout_ms = 800
    timeout_ms = max(100, min(timeout_ms, 5000))

    raw_cooldown = settings.get("cooldown_seconds")
    try:
        cooldown_seconds = int(raw_cooldown)
    except (TypeError, ValueError):
        cooldown_seconds = 120
    cooldown_seconds = max(10, min(cooldown_seconds, 3600))

    effective_hosts = hosts if hosts else []

    if enabled and not effective_hosts:
        logger.warning("Disabling network quality probe due to lack of valid hosts")
        enabled = False

    _network_quality_settings = {
        "enabled": bool(enabled),
        "hosts": effective_hosts,
        "attempts": attempts,
        "timeout_ms": timeout_ms,
        "cooldown_seconds": cooldown_seconds,
    }

    if not _network_quality_settings["enabled"]:
        _network_quality_last_run = None


def generate_sparkline(data: List[float], length: int = 10) -> str:
    """Generate a text-based sparkline from numerical data."""
    if not data or len(data) < 2:
        return "Collecting..."
    # Sample data to desired length
    if len(data) > length:
        step = max(1, len(data) // length)
        sampled_data = [data[i] for i in range(0, len(data), step)][-length:]
    else:
        sampled_data = data

    # Normalize data to sparkline range
    min_val = min(sampled_data)
    max_val = max(sampled_data)
    val_range = max_val - min_val if max_val > min_val else 1

    # Unicode block characters for sparklines
    spark_chars = "▁▂▃▄▅▆▇█"
    sparkline = ""

    for val in sampled_data:
        normalized = (val - min_val) / val_range
        char_idx = min(len(spark_chars) - 1, int(normalized * len(spark_chars)))
        sparkline += spark_chars[char_idx]

    return sparkline


def add_to_history(metric_name: str, value: float, max_entries: int = 300) -> None:
    """Add a value to the global metric history cache."""
    with _history_lock:
        if metric_name not in _metric_history_cache:
            _metric_history_cache[metric_name] = deque(maxlen=max_entries)
        _metric_history_cache[metric_name].append((time.time(), value))

def get_history(metric_name: str, max_age_seconds: int = 300) -> List[float]:
    """Get historical values for a metric within the specified age."""
    with _history_lock:
        if metric_name not in _metric_history_cache:
            return []

        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Filter by age and extract values
        recent_data = [
            value for timestamp, value in _metric_history_cache[metric_name]
            if timestamp >= cutoff_time
        ]

        return recent_data

def calculate_trend(values: List[float], window_size: int = 10) -> Tuple[str, float]:
    """Calculate trend direction and magnitude from historical values."""
    if len(values) < window_size:
        return "Monitoring", 0.0

    # Compare first half vs second half of recent window
    recent = values[-window_size:]
    mid_point = len(recent) // 2
    first_half = recent[:mid_point]
    second_half = recent[mid_point:]

    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)
    trend_delta = second_avg - first_avg

    # Categorize trend
    if abs(trend_delta) < 1.0:
        return "Stable", trend_delta
    if trend_delta > 5.0:
        return "Rising", trend_delta
    if trend_delta > 0:
        return "Trending Up", trend_delta
    if trend_delta < -5.0:
        return "Falling", trend_delta
    return "Trending Down", trend_delta

# Alert management system
class AlertManager:
    """メモリ効率の良いアラート管理システム"""

    def __init__(self, max_history: int = 100, cleanup_interval_minutes: int = 60):
        self.active_alerts: Dict[str, Dict] = {}
        self.alert_history: deque = deque(maxlen=max_history)
        self.last_notification_times: Dict[str, float] = {}
        self.notification_cooldown = 60  # seconds
        self.max_history = max_history
        self._lock = threading.Lock()
        self._cleanup_timer = threading.Timer(cleanup_interval_minutes * 60, self._periodic_cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def __del__(self):
        """デストラクタ - タイマーを停止"""
        if hasattr(self, '_cleanup_timer'):
            self._cleanup_timer.cancel()

    def check_threshold(self, metric_name: str, current_value: float, threshold: float,
                       severity: str = "warning", unit: str = "") -> bool:
        """メモリ効率的に閾値をチェック"""
        alert_key = f"{metric_name}_{severity}"
        current_time = time.time()

        # メモリ使用量チェック（定期的に）
        if len(self.alert_history) >= self.max_history * 0.9:  # 90%に達したら
            self._cleanup_old_alerts()

        is_exceeded = current_value >= threshold

        if is_exceeded:
            alert_data = {
                "metric": metric_name,
                "value": current_value,
                "threshold": threshold,
                "severity": severity,
                "unit": unit,
                "timestamp": current_time,
                "message": f"{metric_name} is {current_value}{unit} (threshold: {threshold}{unit})"
            }

            self.active_alerts[alert_key] = alert_data

            # 通知クールダウンチェック
            last_notification = self.last_notification_times.get(alert_key, 0)
            if current_time - last_notification > self.notification_cooldown:
                self._send_notification(alert_data)
                self.last_notification_times[alert_key] = current_time

            self.alert_history.append(alert_data.copy())

        else:
            if alert_key in self.active_alerts:
                resolved_alert = self.active_alerts[alert_key].copy()
                resolved_alert["resolved_at"] = current_time
                resolved_alert["resolved"] = True
                self.alert_history.append(resolved_alert)
                del self.active_alerts[alert_key]

        return is_exceeded

    def _cleanup_old_alerts(self, max_age_hours: int = 24) -> None:
        """古いアラートをクリーンアップ"""
        try:
            with self._lock:
                cutoff_time = time.time() - (max_age_hours * 3600)

                # アクティブアラートのうち古いものを削除
                expired_active = [
                    key for key, alert in self.active_alerts.items()
                    if alert.get("timestamp", 0) < cutoff_time
                ]

                for key in expired_active:
                    del self.active_alerts[key]
                    self.last_notification_times.pop(key, None)

                # 履歴から古いものを削除（メモリ節約）
                if len(self.alert_history) > self.max_history // 2:
                    # 最新の半分のみ保持
                    temp_history = list(self.alert_history)[-self.max_history // 2:]
                    self.alert_history.clear()
                    self.alert_history.extend(temp_history)

        except Exception as e:
            logger.warning(f"アラートクリーンアップ中にエラー: {e}")

    def _periodic_cleanup(self) -> None:
        """定期的なクリーンアップ"""
        try:
            self._cleanup_old_alerts()
            # 次のクリーンアップをスケジュール
            self._cleanup_timer = threading.Timer(3600, self._periodic_cleanup)  # 1時間後
            self._cleanup_timer.daemon = True
            self._cleanup_timer.start()
        except Exception as e:
            logger.warning(f"定期クリーンアップ中にエラー: {e}")

    def get_alert_summary(self) -> Dict[str, str]:
        """メモリ効率の良いアラートサマリを取得"""
        with self._lock:
            if not self.active_alerts:
                return {"Alert Status": "All systems normal"}

            # 統計を計算
            critical_count = sum(1 for alert in self.active_alerts.values() if alert["severity"] == "critical")
            warning_count = len(self.active_alerts) - critical_count

            result = {}
            if critical_count > 0:
                result["Critical Alerts"] = f"{critical_count} active"
            if warning_count > 0:
                result["Warning Alerts"] = f"{warning_count} active"

            return result

    def clear_active_alerts(self) -> int:
        """アクティブアラートをクリア"""
        with self._lock:
            cleared = len(self.active_alerts)
            if cleared == 0:
                return 0

            current_time = time.time()
            for alert_key, alert_data in list(self.active_alerts.items()):
                resolved_alert = alert_data.copy()
                resolved_alert["resolved_at"] = current_time
                resolved_alert["resolved"] = True
                resolved_alert["cleared_manually"] = True
                self.alert_history.append(resolved_alert)
                self.active_alerts.pop(alert_key, None)
                self.last_notification_times.pop(alert_key, None)

            return cleared

    def _send_notification(self, alert_data: Dict) -> None:
        """Send desktop notification for alert (placeholder implementation)."""
        try:
            # This would integrate with system notifications
            # For now, emit a structured log entry for the alert intent
            logger.warning(
                "Alert notification queued",
                extra={
                    "metric": alert_data.get("metric"),
                    "severity": alert_data.get("severity"),
                    "value": alert_data.get("value"),
                    "threshold": alert_data.get("threshold"),
                },
            )
        except Exception as error:
            logger.error("Failed to queue alert notification", exc_info=True, extra={"error": str(error)})

    def get_active_alerts(self) -> List[Dict]:
        """Get list of currently active alerts."""
        return list(self.active_alerts.values())

    def get_alert_summary(self) -> Dict[str, str]:
        """Generate a summary of current alert status."""
        if not self.active_alerts:
            return {"Alert Status": "All systems normal"}

        critical_count = sum(1 for alert in self.active_alerts.values() if alert["severity"] == "critical")
        warning_count = sum(1 for alert in self.active_alerts.values() if alert["severity"] == "warning")

        result = {}
        if critical_count > 0:
            result["Critical Alerts"] = f"{critical_count} active"
        if warning_count > 0:
            result["Warning Alerts"] = f"{warning_count} active"

        return result

    def clear_active_alerts(self) -> int:
        """Clear all active alerts and record their resolution."""
        cleared = len(self.active_alerts)
        if cleared == 0:
            return 0

        current_time = time.time()
        for alert_key, alert_data in list(self.active_alerts.items()):
            resolved_alert = alert_data.copy()
            resolved_alert["resolved_at"] = current_time
            resolved_alert["resolved"] = True
            resolved_alert["cleared_manually"] = True
            self.alert_history.append(resolved_alert)
            self.active_alerts.pop(alert_key, None)
            self.last_notification_times.pop(alert_key, None)

        return cleared

# Global alert manager instance
_alert_manager = AlertManager()

def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    return _alert_manager

def alert_monitor_collector() -> MetricData:
    """Monitor system metrics against configurable thresholds and generate alerts."""
    try:
        alert_manager = get_alert_manager()
        result: Dict[str, str] = {}

        thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "gpu_usage_percent": 90.0,
            "gpu_temperature": 83.0,
            "cpu_temperature": 75.0,
        }

        cpu_percent = _get_cpu_percent()
        if cpu_percent is not None:
            alert_manager.check_threshold(
                "CPU Usage", cpu_percent, thresholds["cpu_percent"], "warning", "%"
            )
            if cpu_percent > 95.0:
                alert_manager.check_threshold(
                    "CPU Usage", cpu_percent, 95.0, "critical", "%"
                )

        with suppress(Exception):
            memory = psutil.virtual_memory()
            alert_manager.check_threshold(
                "Memory Usage", memory.percent, thresholds["memory_percent"], "warning", "%"
            )
            if memory.percent > 95.0:
                alert_manager.check_threshold(
                    "Memory Usage", memory.percent, 95.0, "critical", "%"
                )

        with suppress(Exception):
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        temp = entry.current
                        if "cpu" in name.lower() or "core" in name.lower():
                            alert_manager.check_threshold(
                                f"CPU Temperature ({name})", temp, thresholds["cpu_temperature"], "warning", "°C"
                            )
                            if temp > 85.0:
                                alert_manager.check_threshold(
                                    f"CPU Temperature ({name})", temp, 85.0, "critical", "°C"
                                )

        if pynvml is not None:
            for index, handle in _iter_nvml_devices():
                with suppress(Exception):
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    alert_manager.check_threshold(
                        f"GPU {index} Usage", float(util.gpu), thresholds["gpu_usage_percent"], "warning", "%"
                    )
                with suppress(Exception):
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    alert_manager.check_threshold(
                        f"GPU {index} Temperature", float(temp), thresholds["gpu_temperature"], "warning", "°C"
                    )
                    if temp > 90.0:
                        alert_manager.check_threshold(
                            f"GPU {index} Temperature", float(temp), 90.0, "critical", "°C"
                        )

        alert_summary = alert_manager.get_alert_summary()
        result.update(alert_summary)

        active_alerts = alert_manager.get_active_alerts()
        for position, alert in enumerate(active_alerts[:3], start=1):
            result[f"Alert {position}"] = f"{alert['metric']}: {alert['value']}{alert['unit']}"

        if len(active_alerts) > 3:
            result["Additional Alerts"] = f"+{len(active_alerts) - 3} entries"

        recent_alerts = len([a for a in alert_manager.alert_history if time.time() - a["timestamp"] < 3600])
        if recent_alerts > 0:
            result["Recent Alerts (1h)"] = f"{recent_alerts} events"

        if not result:
            return {"Alert Monitor": "All systems within thresholds"}
        return result

    except Exception as e:
        return {"Error": f"Alert monitoring failed: {str(e)}"}

class MetricHistory:
    """メモリ効率の良いメトリクス履歴管理クラス"""

    def __init__(self, max_entries: int = 1000, memory_limit_mb: float = 50.0):
        self.max_entries = max_entries
        self.memory_limit_mb = memory_limit_mb  # メモリ使用量制限
        self._data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_entries))
        self._timestamps: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._memory_monitor = threading.Timer(300.0, self._cleanup_memory)  # 5分ごとにメモリチェック
        self._memory_monitor.daemon = True
        self._memory_monitor.start()

    def __del__(self):
        """デストラクタ - タイマーを停止"""
        if hasattr(self, '_memory_monitor'):
            self._memory_monitor.cancel()

    def add_sample(self, timestamp: int, metrics: Dict[str, Dict[str, str]]) -> None:
        """メモリ効率的に新しいサンプルを追加"""
        with self._lock:
            # メモリ使用量チェック
            if self._check_memory_usage():
                self._cleanup_memory()

            self._timestamps.append(timestamp)
            total_samples = len(self._timestamps)

            # 新しいメトリクスをバックフィル
            for metric_id in metrics.keys():
                if metric_id not in self._data:
                    buffer = self._data[metric_id]
                    if total_samples > 1:
                        # メモリ効率のために空のdictではなくNoneを使用
                        buffer.extend([None] * (total_samples - 1))

            # 既存のメトリクスに値を追加
            for metric_id in list(self._data.keys()):
                buffer = self._data[metric_id]
                if metric_id in metrics:
                    buffer.append(metrics[metric_id])
                else:
                    buffer.append(None)

    def _check_memory_usage(self) -> bool:
        """メモリ使用量が制限を超えているかチェック"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            return memory_mb > self.memory_limit_mb
        except Exception:
            return False

    def _cleanup_memory(self) -> None:
        """メモリクリーンアップを実行"""
        try:
            with self._lock:
                # 古いデータを削除（最大エントリの半分まで）
                if len(self._timestamps) > self.max_entries // 2:
                    keep_entries = self.max_entries // 2

                    # タイムスタンプを削減
                    self._timestamps.clear()
                    if hasattr(self, '_timestamps_backup') and self._timestamps_backup:
                        self._timestamps.extend(list(self._timestamps_backup)[-keep_entries:])
                    else:
                        # 最新のエントリを保持するための仮定
                        pass

                    # 各メトリクスのデータを削減
                    for metric_id, data_queue in self._data.items():
                        if len(data_queue) > keep_entries:
                            # 最新のデータを保持
                            temp_data = list(data_queue)[-keep_entries:]
                            data_queue.clear()
                            data_queue.extend(temp_data)

                # ガベージコレクションを実行
                import gc
                collected = gc.collect()
                logger.debug(f"メモリクリーンアップ: {collected}オブジェクト回収")

        except Exception as e:
            logger.warning(f"メモリクリーンアップ中にエラー: {e}")

    def get_data_range(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> Dict[str, List]:
        """メモリ効率的に指定範囲のデータを取得"""
        with self._lock:
            if not self._timestamps:
                return {}

            timestamps = list(self._timestamps)
            start_idx = 0
            end_idx = len(timestamps)

            if start_time is not None:
                start_idx = next((i for i, ts in enumerate(timestamps) if ts >= start_time), 0)

            if end_time is not None:
                end_idx = next((i for i, ts in enumerate(timestamps) if ts > end_time), len(timestamps))
                end_idx = min(end_idx, len(timestamps))

            result = {}
            requested_range = timestamps[start_idx:end_idx]

            for metric_id, values in self._data.items():
                metric_values = list(values)[start_idx:end_idx]
                # None値を除去してメモリ効率を向上
                valid_data = [(ts, val) for ts, val in zip(requested_range, metric_values) if val is not None]

                if valid_data:
                    result[metric_id] = {
                        "timestamps": [ts for ts, _ in valid_data],
                        "values": [val for _, val in valid_data]
                    }

            return result

    def clear_old_data(self, max_age_seconds: int = 3600) -> int:
        """指定年齢以上の古いデータをクリア"""
        with self._lock:
            if not self._timestamps:
                return 0

            cutoff_time = time.time() * 1000 - (max_age_seconds * 1000)  # ミリ秒に変換
            original_count = len(self._timestamps)

            # 古いデータを削除
            while self._timestamps and self._timestamps[0] < cutoff_time:
                self._timestamps.popleft()

            removed_count = original_count - len(self._timestamps)

            # 各メトリクスデータも同期して削除
            for metric_id, data_queue in self._data.items():
                for _ in range(removed_count):
                    if data_queue:
                        data_queue.popleft()

            # 空のメトリクスデータを削除
            empty_metrics = [mid for mid, data in self._data.items() if not data]
            for mid in empty_metrics:
                del self._data[mid]

            if removed_count > 0:
                logger.info(f"古いデータをクリア: {removed_count}エントリ削除")

            return removed_count

    def sample_count(self) -> int:
        with self._lock:
            return len(self._timestamps)

    def last_timestamp(self) -> Optional[int]:
        with self._lock:
            if not self._timestamps:
                return None
            return self._timestamps[-1]

    def first_timestamp(self) -> Optional[int]:
        with self._lock:
            if not self._timestamps:
                return None
            return self._timestamps[0]

    def retention_seconds(self) -> Optional[int]:
        with self._lock:
            if not self._timestamps:
                return None
            start = self._timestamps[0]
            end = self._timestamps[-1]
            if start is None or end is None:
                return None
            return max(0, (end - start) // 1000)

    def get_data_range(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> Dict[str, List]:
        """Get historical data within the specified time range with optimized performance."""
        with self._lock:
            if not self._timestamps:
                return {}

            # Find the range indices efficiently
            timestamps = list(self._timestamps)
            start_idx = 0
            end_idx = len(timestamps)

            if start_time is not None:
                start_idx = next((i for i, ts in enumerate(timestamps) if ts >= start_time), 0)

            if end_time is not None:
                end_idx = next((i for i, ts in enumerate(timestamps) if ts > end_time), len(timestamps))
                end_idx = min(end_idx, len(timestamps))

            result = {}
            for metric_id, values in self._data.items():
                metric_timestamps = timestamps[start_idx:end_idx]
                metric_values = list(values)[start_idx:end_idx]
                if metric_timestamps:
                    result[metric_id] = {
                        "timestamps": metric_timestamps,
                        "values": metric_values
                    }

            return result

    def export_to_json(self, file_path: Path, metric_filter: Optional[List[str]] = None) -> None:
        """Export historical data to a JSON file with optimized performance."""
        file_path.parent.mkdir(parents=True, exist_ok=True)

        snapshot = self.get_data_range()
        if not snapshot:
            export_payload = {
                "max_entries": self.max_entries,
                "total_samples": 0,
                "timestamps": [],
                "metrics": {},
            }
        else:
            if metric_filter:
                snapshot = {k: v for k, v in snapshot.items() if k in metric_filter}

            if not snapshot:
                export_payload = {
                    "max_entries": self.max_entries,
                    "total_samples": 0,
                    "timestamps": [],
                    "metrics": {},
                }
            else:
                example_metric = next(iter(snapshot.values()))
                timeline = example_metric.get("timestamps", [])
                export_payload = {
                    "max_entries": self.max_entries,
                    "total_samples": len(timeline),
                    "timestamps": timeline,
                    "metrics": snapshot,
                }

        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(export_payload, handle, ensure_ascii=False, indent=2)
        except Exception:
            # Could log error here if logging is available
            pass

    @classmethod
    def load_from_file(cls, file_path: Path) -> "MetricHistory":
        """Load historical data from a JSON file with optimized performance."""
        if not file_path.exists():
            return cls()

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)

            metrics_section = data.get("metrics") or data.get("data") or {}
            timeline = data.get("timestamps")

            if not timeline and metrics_section:
                example_metric = next(iter(metrics_section.values()))
                timeline = example_metric.get("timestamps", [])

            timeline = timeline or []
            samples = len(timeline)

            history = cls(max_entries=data.get("max_entries", 1000))

            if samples == 0:
                return history

            maxlen = history._timestamps.maxlen or samples
            start_idx = max(0, samples - maxlen)
            trimmed_timeline = timeline[start_idx:]

            history._timestamps.extend(trimmed_timeline)

            for metric_id, metric_data in metrics_section.items():
                values = list(metric_data.get("values", []))

                if len(values) < samples:
                    # Left-pad missing entries with empty dicts to maintain alignment
                    pad_length = samples - len(values)
                    values = [{}] * pad_length + values

                trimmed_values = values[start_idx:]
                history._data[metric_id].extend(trimmed_values[: len(trimmed_timeline)])

            return history
        except Exception:
            # Could log error here if logging is available
            return cls()

    def clear(self) -> None:
        """Clear all historical data efficiently."""
        self._data.clear()
        self._timestamps.clear()
        # Force garbage collection for large datasets
        import gc
        gc.collect()


MetricData = Mapping[str, str]
MetricCollector = Callable[[], MetricData]


@dataclass(frozen=True)
class Metric:
    identifier: str
    name: str
    description: str
    collect: MetricCollector


class MetricRegistry:
    """Enhanced metric registry with improved performance and extensibility."""
    def __init__(self, metrics: Iterable[Metric]) -> None:
        self._metrics: Dict[str, Metric] = {metric.identifier: metric for metric in metrics}
        self._collectors: Dict[str, MetricCollector] = {metric.identifier: metric.collect for metric in metrics}

    def __contains__(self, metric_id: str) -> bool:
        return metric_id in self._metrics

    def __len__(self) -> int:
        return len(self._metrics)

    def get(self, metric_id: str) -> Metric:
        try:
            return self._metrics[metric_id]
        except KeyError as exc:
            raise KeyError(f"Metric '{metric_id}' is not registered") from exc

    def get_collector(self, metric_id: str) -> MetricCollector:
        """Get a metric collector function directly."""
        try:
            return self._collectors[metric_id]
        except KeyError as exc:
            raise KeyError(f"Collector for metric '{metric_id}' is not registered") from exc

    def available_metrics(self) -> Iterator[Metric]:
        return iter(self._metrics.values())

    def collect_metric(self, metric_id: str) -> MetricData:
        """Collect data for a specific metric."""
        collector = self.get_collector(metric_id)
        return collector()

    def collect_all(self) -> Dict[str, MetricData]:
        """Collect data for all registered metrics efficiently."""
        return {metric_id: collector() for metric_id, collector in self._collectors.items()}


def top_cpu_processes_collector(limit: int = 5) -> MetricData:
    """Collect top CPU consuming processes with real-time CPU percentage and memory info."""
    try:
        processes = []
        # Get all processes with required attributes
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = proc.info
                pid = info.get("pid")
                name = info.get("name", "Unknown")
                cpu_percent = info.get("cpu_percent", 0.0)
                memory_percent = info.get("memory_percent", 0.0)
                status = info.get("status", "unknown")

                # Only include processes with measurable CPU usage
                if cpu_percent > 0.1:  # Filter out idle processes
                    processes.append((cpu_percent, memory_percent, pid, name, status))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort by CPU percentage (descending)
        processes.sort(reverse=True, key=lambda x: x[0])
        top = processes[:limit]

        result: Dict[str, str] = {}
        for index, (cpu_pct, mem_pct, pid, name, status) in enumerate(top, start=1):
            # Truncate long process names
            display_name = name[:12] + "..." if len(name) > 15 else name
            label = f"{index}. {display_name} (PID {pid})"
            value = f"CPU: {cpu_pct:.1f}% | MEM: {mem_pct:.1f}%"
            result[label] = value

        return result if result else {"No active processes": "All processes idle"}
    except Exception as e:
        return {"Error": f"Unable to collect CPU process data: {str(e)}"}


def gpu_usage_collector() -> MetricData:
    """Collect enhanced GPU information with detailed metrics, trends, and health monitoring."""
    try:
        # Try NVML first for detailed GPU information
        try:
            from pynvml import (
                nvmlInit, nvmlShutdown, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex,
                nvmlDeviceGetUtilizationRates, nvmlDeviceGetMemoryInfo, nvmlDeviceGetTemperature,
                nvmlDeviceGetPowerUsage, nvmlDeviceGetClockInfo, nvmlDeviceGetName,
                nvmlDeviceGetFanSpeed, nvmlDeviceGetPerformanceState,
                NVML_TEMPERATURE_GPU, NVML_CLOCK_GRAPHICS, NVML_CLOCK_MEM
            )

            nvmlInit()
            device_count = nvmlDeviceGetCount()

            result: Dict[str, str] = {}
            total_power = 0
            max_temp = 0
            total_memory_used = 0
            total_memory_capacity = 0

            for i in range(device_count):
                handle = nvmlDeviceGetHandleByIndex(i)
                gpu_prefix = f"GPU {i}"

                # Get GPU name
                try:
                    gpu_name = nvmlDeviceGetName(handle).decode('utf-8')
                    # Shorten long GPU names
                    if len(gpu_name) > 20:
                        gpu_name = gpu_name[:17] + "..."
                    gpu_prefix = f"GPU {i} ({gpu_name})"
                except:
                    pass

                # GPU Utilization with history tracking
                try:
                    util = nvmlDeviceGetUtilizationRates(handle)
                    gpu_usage = util.gpu

                    # Add to history for trending
                    add_to_history(f"gpu_{i}_usage", gpu_usage)
                    gpu_history = get_history(f"gpu_{i}_usage", max_age_seconds=180)
                    gpu_sparkline = generate_sparkline(gpu_history, length=8)

                    # Usage status indicator
                    if gpu_usage > 90:
                        usage_icon = "🔥"
                    elif gpu_usage > 70:
                        usage_icon = "⚡"
                    elif gpu_usage > 30:
                        usage_icon = "📊"
                    else:
                        usage_icon = "💤"

                    result[f"{usage_icon} {gpu_prefix}"] = f"{gpu_usage}% {gpu_sparkline}"
                except:
                    result[f"❓ {gpu_prefix}"] = "Usage unavailable"

                # Enhanced Memory Information
                try:
                    mem_info = nvmlDeviceGetMemoryInfo(handle)
                    used_gb = mem_info.used / (1024 ** 3)
                    total_gb = mem_info.total / (1024 ** 3)
                    percent = (mem_info.used / mem_info.total) * 100

                    total_memory_used += used_gb
                    total_memory_capacity += total_gb

                    # Memory status indicator
                    if percent > 90:
                        mem_icon = "🚨"
                    elif percent > 70:
                        mem_icon = "⚠️"
                    elif percent > 30:
                        mem_icon = "📊"
                    else:
                        mem_icon = "✅"

                    result[f"{mem_icon} Memory {i}"] = f"{used_gb:.1f}GB / {total_gb:.1f}GB ({percent:.1f}%)"
                except:
                    pass

                # Enhanced Temperature Monitoring
                try:
                    temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                    max_temp = max(max_temp, temp)

                    # Add temperature to history
                    add_to_history(f"gpu_{i}_temp", temp)
                    temp_history = get_history(f"gpu_{i}_temp", max_age_seconds=300)
                    temp_sparkline = generate_sparkline(temp_history, length=6)

                    # Temperature status
                    if temp > 85:
                        temp_icon = "🔥"
                    elif temp > 75:
                        temp_icon = "🟡"
                    elif temp > 60:
                        temp_icon = "🟠"
                    else:
                        temp_icon = "🟢"

                    result[f"{temp_icon} Temp {i}"] = f"{temp}°C {temp_sparkline}"
                except:
                    pass

                # Power Usage
                try:
                    power_mw = nvmlDeviceGetPowerUsage(handle)
                    power_w = power_mw / 1000
                    total_power += power_w

                    # Power status
                    if power_w > 250:
                        power_icon = "⚡"
                    elif power_w > 150:
                        power_icon = "🔋"
                    else:
                        power_icon = "💚"

                    result[f"{power_icon} Power {i}"] = f"{power_w:.1f}W"
                except:
                    pass

                # Clock Speeds
                try:
                    gpu_clock = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_GRAPHICS)
                    mem_clock = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_MEM)
                    result[f"🔄 Clocks {i}"] = f"GPU: {gpu_clock}MHz | MEM: {mem_clock}MHz"
                except:
                    pass

                # Fan Speed
                try:
                    fan_speed = nvmlDeviceGetFanSpeed(handle)
                    if fan_speed > 80:
                        fan_icon = "🌪️"
                    elif fan_speed > 50:
                        fan_icon = "💨"
                    else:
                        fan_icon = "🔄"
                    result[f"{fan_icon} Fan {i}"] = f"{fan_speed}%"
                except:
                    pass

                # Performance State
                try:
                    perf_state = nvmlDeviceGetPerformanceState(handle)
                    perf_levels = {0: "Max", 1: "High", 2: "Med", 3: "Low"}
                    perf_desc = perf_levels.get(perf_state, f"P{perf_state}")

                    if perf_state <= 1:
                        perf_icon = "🚀"
                    elif perf_state <= 2:
                        perf_icon = "⚡"
                    else:
                        perf_icon = "🐌"

                    result[f"{perf_icon} Perf {i}"] = f"P{perf_state} ({perf_desc})"
                except:
                    pass

            # Add summary statistics
            if device_count > 0:
                result["📊 GPU Summary"] = f"{device_count} device(s) detected"

                if max_temp > 0:
                    if max_temp > 85:
                        temp_status = "🔥 Hot"
                    elif max_temp > 75:
                        temp_status = "🟡 Warm"
                    else:
                        temp_status = "✅ Cool"
                    result[f"🌡️ Max Temp {temp_status}"] = f"{max_temp}°C"

                if total_power > 0:
                    result["⚡ Total Power"] = f"{total_power:.1f}W"

                if total_memory_capacity > 0:
                    total_mem_percent = (total_memory_used / total_memory_capacity) * 100
                    result["💾 Total VRAM"] = f"{total_memory_used:.1f}GB / {total_memory_capacity:.1f}GB ({total_mem_percent:.1f}%)"

            nvmlShutdown()
            return result if result else {"No NVML Data": "No GPU data available"}
        except ImportError:
            # Fallback to basic GPU information
            return {
                "Status": "NVML not available",
                "Note": "Install pynvml for detailed GPU metrics",
                "Basic GPU": "Limited GPU monitoring available"
            }
        except Exception as e:
            # NVML error, fallback to basic information
            return {
                "NVML Error": f"Unable to read NVML data: {str(e)}",
                "Basic GPU": "Limited GPU monitoring available"
            }
    except Exception as e:
        return {"Error": f"Unable to collect GPU data: {str(e)}"}


def system_temperatures_collector() -> MetricData:
    """Collect system temperature sensor data with enhanced warnings and status indicators."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return {"No sensors": "Temperature sensors not available"}

        result = {}
        max_temp = 0
        critical_count = 0
        warning_count = 0
        hottest_sensor: Optional[Tuple[str, float]] = None
        fastest_risers: List[Tuple[str, float]] = []
        now = time.time()

        for name, entries in temps.items():
            for entry in entries:
                current_temp = entry.current
                max_temp = max(max_temp, current_temp)

                # Determine temperature status
                temp_status = "🟢"  # Normal (green)
                if entry.critical and current_temp >= entry.critical:
                    temp_status = "🔴"  # Critical (red)
                    critical_count += 1
                elif entry.high and current_temp >= entry.high:
                    temp_status = "🟡"  # Warning (yellow)
                    warning_count += 1
                elif current_temp >= 70:  # General high temperature threshold
                    temp_status = "🟠"  # Elevated (orange)
                    warning_count += 1

                # Format sensor label
                sensor_name = f"{name}: {entry.label}" if entry.label else name
                sensor_name = sensor_name.replace("_", " ").title()

                history_values: List[float] = []
                delta_per_min: Optional[float] = None
                with _temperature_history_lock:
                    history = _temperature_history[sensor_name]
                    history.append((now, current_temp))
                    cutoff = now - _TEMPERATURE_HISTORY_WINDOW_SECONDS
                    while history and history[0][0] < cutoff:
                        history.popleft()
                    history_values = [value for _, value in history]

                if len(history_values) >= 2:
                    first_time, first_temp = history[0]
                    last_time, last_temp = history[-1]
                    elapsed_minutes = max((last_time - first_time) / 60.0, 1e-3)
                    delta_per_min = (last_temp - first_temp) / elapsed_minutes

                if not hottest_sensor or current_temp > hottest_sensor[1]:
                    hottest_sensor = (sensor_name, current_temp)

                if delta_per_min is not None and delta_per_min > 0.5:
                    fastest_risers.append((sensor_name, delta_per_min))

                # Create display value with status
                temp_value = f"{temp_status} {current_temp:.1f}°C"

                # Add threshold info if available
                thresholds = []
                if entry.high:
                    thresholds.append(f"H:{entry.high:.0f}°C")
                if entry.critical:
                    thresholds.append(f"C:{entry.critical:.0f}°C")
                if thresholds:
                    temp_value += f" ({'/'.join(thresholds)})"

                trend_parts: List[str] = []
                if delta_per_min is not None:
                    trend_parts.append(f"Δ {delta_per_min:+.1f}°C/min")
                if len(history_values) >= 4:
                    sparkline = generate_sparkline(history_values[-10:])
                    trend_parts.append(f"Trend {sparkline}")
                if trend_parts:
                    temp_value += " | " + " ".join(trend_parts)

                result[sensor_name] = temp_value

        # Add summary information
        if critical_count > 0:
            result["🚨 Status"] = f"{critical_count} sensors critical!"
        elif warning_count > 0:
            result["⚠️ Status"] = f"{warning_count} sensors elevated"
        else:
            result["✅ Status"] = "All sensors normal"

        result["📊 Max Temp"] = f"{max_temp:.1f}°C"

        if hottest_sensor:
            result["🔥 Hottest"] = f"{hottest_sensor[0]} {hottest_sensor[1]:.1f}°C"

        if fastest_risers:
            fastest_risers.sort(key=lambda item: item[1], reverse=True)
            top_risers = ", ".join(
                f"{name} +{rate:.1f}°C/min" for name, rate in fastest_risers[:3]
            )
            result["♨️ Fast Risers"] = top_risers

        return result
    except Exception as e:
        return {"Error": f"Unable to read temperature sensors: {str(e)}"}


def fan_speeds_collector() -> MetricData:
    """Collect system fan speed information with enhanced status indicators and analysis."""
    try:
        fans = psutil.sensors_fans()
        if not fans:
            return {"No fans": "Fan sensors not available"}

        result = {}
        total_fans = 0
        active_fans = 0
        max_rpm = 0
        min_rpm = float('inf')
        now = time.time()
        restarts: List[str] = []
        fastest_spinners: List[Tuple[str, float]] = []

        for name, entries in fans.items():
            for entry in entries:
                total_fans += 1
                current_rpm = entry.current
                max_rpm = max(max_rpm, current_rpm)
                if current_rpm > 0:
                    active_fans += 1
                    min_rpm = min(min_rpm, current_rpm)

                # Determine fan status
                fan_status = "🟢"  # Normal (green)
                if current_rpm == 0:
                    fan_status = "⚫"  # Stopped (black)
                elif current_rpm > 3000:
                    fan_status = "🔴"  # High speed (red)
                elif current_rpm > 2000:
                    fan_status = "🟡"  # Medium-high speed (yellow)
                elif current_rpm > 1000:
                    fan_status = "🟠"  # Medium speed (orange)

                # Format fan label
                fan_name = f"{name}: {entry.label}" if entry.label else name
                fan_name = fan_name.replace("_", " ").title()

                history_values: List[float] = []
                delta_per_min: Optional[float] = None
                with _fan_history_lock:
                    history = _fan_history[fan_name]
                    previous_rpm = history[-1][1] if history else None
                    history.append((now, float(current_rpm)))
                    cutoff = now - _FAN_HISTORY_WINDOW_SECONDS
                    while history and history[0][0] < cutoff:
                        history.popleft()
                    history_values = [value for _, value in history]

                if len(history_values) >= 2:
                    first_time, first_rpm = history[0]
                    last_time, last_rpm = history[-1]
                    elapsed_minutes = max((last_time - first_time) / 60.0, 1e-3)
                    delta_per_min = (last_rpm - first_rpm) / elapsed_minutes

                if previous_rpm is not None and previous_rpm <= 100 and current_rpm > 0:
                    restarts.append(fan_name)

                if current_rpm > 0:
                    fastest_spinners.append((fan_name, current_rpm))

                result[f"{fan_status} {fan_name}"] = f"{current_rpm:.0f} RPM"

                trend_parts: List[str] = []
                if delta_per_min is not None and current_rpm > 0:
                    trend_parts.append(f"Δ {delta_per_min:+.0f} RPM/min")
                if len(history_values) >= 4:
                    sparkline = generate_sparkline(history_values[-10:])
                    trend_parts.append(f"Trend {sparkline}")
                if trend_parts:
                    result[f"{fan_name} Trend"] = " ".join(trend_parts)

        # Add summary information
        if min_rpm == float('inf'):
            min_rpm = 0

        summary_status = "✅" if active_fans == total_fans else "⚠️" if active_fans > 0 else "🚨"
        result[f"{summary_status} Fan Summary"] = f"{active_fans}/{total_fans} active"

        if max_rpm > 0:
            result["📊 RPM Range"] = f"{min_rpm:.0f} - {max_rpm:.0f}"

        if restarts:
            result["🔁 Fan Restarts"] = ", ".join(sorted(set(restarts)))

        if fastest_spinners:
            fastest_spinners.sort(key=lambda item: item[1], reverse=True)
            top_spinners = ", ".join(
                f"{name} {rpm:.0f} RPM" for name, rpm in fastest_spinners[:3]
            )
            result["🚀 Top Spinners"] = top_spinners

        return result
    except Exception as e:
        return {"Error": f"Unable to read fan sensors: {str(e)}"}


def format_bytes(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EiB"]:
        if abs(num) < 1024.0:
            return f"{num:0.2f} {unit}"
        num /= 1024.0
    return f"{num:0.2f} EiB"


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or parts:
        parts.append(f"{hours}h")
    if minutes or parts:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def per_core_sparkline_collector() -> MetricData:
    """Collect per-core CPU usage data for sparkline visualization with error handling."""
    try:
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        return {
            f"Core {idx}": f"{value:.1f}%"
            for idx, value in enumerate(per_core)
        }
    except Exception as e:
        return {"Error": f"Unable to collect per-core CPU data: {str(e)}"}


def cpu_usage_collector() -> MetricData:
    """最適化されたCPU使用率データを収集"""
    try:
        # CPU最適化システムを使用
        from .cpu_optimizer import cpu_optimizer

        profile = cpu_optimizer.get_optimized_cpu_usage()
        efficiency = cpu_optimizer.calculate_cpu_efficiency_score()

        # Get current CPU usage with optimized measurement
        cpu_percent = profile.total_percent
        per_core = profile.per_core

        # Add to history for trend analysis (simplified)
        add_to_history("cpu_total", cpu_percent)

        # Generate sparkline for overall CPU
        cpu_history = get_history("cpu_total", max_age_seconds=300)  # 5 minutes
        trend_icon, trend_delta = calculate_trend(cpu_history)
        cpu_sparkline = generate_sparkline(cpu_history, length=12)

        result: Dict[str, str] = {
            f"{trend_icon}": f"{cpu_percent:.1f}%",
            "📈 Trend": cpu_sparkline,
            "⚡ Efficiency": f"{efficiency['efficiency']:.1f}/100",
        }

        # Add CPU breakdown with optimization
        cpu_times = psutil.cpu_times_percent(interval=0.0)  # Non-blocking
        if hasattr(cpu_times, 'user') and hasattr(cpu_times, 'system'):
            result["User/System"] = f"{cpu_times.user:.1f}% / {cpu_times.system:.1f}%"
            if hasattr(cpu_times, 'idle'):
                result["Idle"] = f"{cpu_times.idle:.1f}%"

        # Add per-core usage with mini sparklines (optimized)
        core_limit = min(len(per_core), cpu_optimizer.core_limit)
        for i in range(core_limit):
            core_usage = per_core[i]

            # Simplified history tracking for cores
            core_history = get_history(f"cpu_core_{i}", max_age_seconds=60) or [core_usage]
            core_sparkline = generate_sparkline(core_history, length=6)

            # Core status indicator
            if core_usage > 80:
                core_icon = "🔥"
            elif core_usage > 50:
                core_icon = "⚡"
            elif core_usage < 10:
                core_icon = "💤"
            else:
                core_icon = "📊"

            result[f"Core {i+1} {core_icon}"] = f"{core_usage:.1f}% {core_sparkline}"

        # Core utilisation distribution summaries (optimized)
        total_cores = len(per_core) or 1
        crit_cores = sum(1 for value in per_core if value >= 90.0)
        high_cores = sum(1 for value in per_core if 70.0 <= value < 90.0)
        moderate_cores = sum(1 for value in per_core if 40.0 <= value < 70.0)
        low_cores = total_cores - (crit_cores + high_cores + moderate_cores)

        result["Core Load Bands"] = (
            f"Critical {crit_cores}/{total_cores} | High {high_cores}/{total_cores} | "
            f"Moderate {moderate_cores}/{total_cores} | Low {low_cores}/{total_cores}"
        )

        # CPU frequency information (optimized)
        if profile.frequency:
            cpu_count = psutil.cpu_count() or 1
            result["🔄 Frequency"] = f"{profile.frequency:.0f}MHz"

        # Load average with interpretation (optimized)
        if profile.load_average and profile.load_average != (0, 0, 0):
            load_1m = profile.load_average[0]
            cpu_count = psutil.cpu_count() or 1
            load_per_core = load_1m / cpu_count

            if load_per_core > 1.5:
                load_icon = "🚨 High"
            elif load_per_core > 1.0:
                load_icon = "⚠️ Med"
            else:
                load_icon = "✅ Low"

            result["Load Avg"] = f"{load_icon} {load_1m:.2f}"

        # Performance optimization suggestions
        if efficiency['efficiency'] < 40:
            result["💡 Suggestion"] = "Consider CPU optimization"
        elif efficiency['utilization'] > 85:
            result["⚠️ Alert"] = "High CPU usage detected"

        return result
    except Exception as e:
        return {"Error": f"Unable to collect CPU data: {str(e)}"}


def cpu_trend_collector(history_length: int = 60) -> MetricData:
    """Collect detailed CPU usage trend data for advanced graphing with stable readings."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        per_core = psutil.cpu_percent(interval=0.1, percpu=True)

        avg_cpu = sum(per_core) / len(per_core) if per_core else cpu_percent
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count()
        cpu_count_logical = psutil.cpu_count(logical=True)

        result = {
            "Current": f"{avg_cpu:.1f}%",
            "History": [],
            "PerCore": {f"Core {i}": f"{usage:.1f}%" for i, usage in enumerate(per_core)},
            "Frequency": f"{cpu_freq.current:.0f}MHz" if cpu_freq else "N/A",
            "Cores": str(cpu_count),
            "Logical": str(cpu_count_logical),
        }

        try:
            load_avg = psutil.getloadavg()
            result["LoadAvg"] = {
                "1min": f"{load_avg[0]:.2f}",
                "5min": f"{load_avg[1]:.2f}",
                "15min": f"{load_avg[2]:.2f}",
            }
        except (AttributeError, OSError):
            pass

        return result
    except Exception as e:
        return {"Error": f"Unable to collect CPU trend data: {str(e)}"}


def memory_usage_collector() -> MetricData:
    """Collect detailed memory usage data with enhanced statistics and segmentation."""
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        result = {
            "Used": format_bytes(memory.used),
            "Free": format_bytes(memory.available),
            "Utilization": f"{memory.percent:.1f}%",
            "Total": format_bytes(memory.total),
        }

        if hasattr(memory, "active"):
            result["Active"] = format_bytes(memory.active)
        if hasattr(memory, "inactive"):
            result["Inactive"] = format_bytes(memory.inactive)
        if hasattr(memory, "buffers"):
            result["Buffers"] = format_bytes(memory.buffers)
        if hasattr(memory, "cached"):
            result["Cached"] = format_bytes(memory.cached)
        if hasattr(memory, "shared"):
            result["Shared"] = format_bytes(memory.shared)
        if hasattr(memory, "slab"):
            result["Slab"] = format_bytes(memory.slab)

        result["Swap Used"] = format_bytes(swap.used)
        result["Swap Free"] = format_bytes(swap.free)
        result["Swap Utilization"] = f"{swap.percent:.1f}%"
        result["Swap Total"] = format_bytes(swap.total)

        try:
            swap_io = psutil.swap_memory()
            if hasattr(swap_io, "sin"):
                result["Swap In"] = format_bytes(swap_io.sin)
            if hasattr(swap_io, "sout"):
                result["Swap Out"] = format_bytes(swap_io.sout)
        except (AttributeError, OSError):
            pass

        return result
    except Exception as e:
        return {"Error": f"Unable to collect memory data: {str(e)}"}


def memory_pressure_collector() -> MetricData:
    """Summarise memory pressure combining RAM, swap, cache, and process usage indicators."""

    try:
        virtual = psutil.virtual_memory()
        swap = psutil.swap_memory()

        pressure_score = 0.0
        pressure_score += min(virtual.percent, 100.0) * 0.6
        pressure_score += (swap.percent if swap.total > 0 else 0.0) * 0.2
        pressure_score += (virtual.shared / max(virtual.total, 1)) * 100 * 0.1 if hasattr(virtual, "shared") else 0.0
        pressure_score += (virtual.cached / max(virtual.total, 1)) * 100 * 0.1 if hasattr(virtual, "cached") else 0.0

        if virtual.percent >= 90.0:
            pressure_label = "Critical"
            pressure_icon = "🚨"
        elif virtual.percent >= 75.0:
            pressure_label = "High"
            pressure_icon = "⚠️"
        elif virtual.percent >= 60.0:
            pressure_label = "Moderate"
            pressure_icon = "🟡"
        else:
            pressure_label = "Normal"
            pressure_icon = "✅"

        result: Dict[str, str] = {
            f"{pressure_icon} Pressure": f"{pressure_label} ({pressure_score:.1f})",
            "RAM Usage": f"{virtual.percent:.1f}%",
            "Available": format_bytes(getattr(virtual, "available", 0)),
            "Active": format_bytes(getattr(virtual, "active", 0)) if hasattr(virtual, "active") else "N/A",
            "Cached": format_bytes(getattr(virtual, "cached", 0)) if hasattr(virtual, "cached") else "N/A",
            "Buffers": format_bytes(getattr(virtual, "buffers", 0)) if hasattr(virtual, "buffers") else "N/A",
        }

        if swap.total > 0:
            result["Swap Usage"] = f"{swap.percent:.1f}% ({format_bytes(swap.used)})"
        else:
            result["Swap Usage"] = "Disabled"

        # Soft/hard page fault rates if available
        if hasattr(virtual, "pageins") and hasattr(virtual, "pageouts"):
            result["Page Ins/Outs"] = f"{virtual.pageins} / {virtual.pageouts}"

        # Process memory offenders (top 3)
        try:
            processes: List[Tuple[int | None, str | None, int]] = []
            total_processes = 0
            total_threads = 0
            for proc in psutil.process_iter(["pid", "name", "memory_info"]):
                with suppress(psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    total_processes += 1
                    mem_info = proc.info.get("memory_info")
                    if mem_info:
                        processes.append((proc.info.get("pid"), proc.info.get("name"), mem_info.rss))
                    with suppress(psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        total_threads += proc.num_threads()

            processes.sort(key=lambda item: item[2], reverse=True)
            top_processes = processes[:3]
            if top_processes:
                offenders = ", ".join(
                    f"{name or pid}:{format_bytes(rss)}" for pid, name, rss in top_processes
                )
                result["Top Memory Processes"] = offenders
            result["Processes Observed"] = str(total_processes)
            result["Threads Observed"] = str(total_threads)
        except Exception:
            pass

        return result
    except Exception as e:
        return {"Error": f"Unable to compute memory pressure: {str(e)}"}


def disk_health_summary_collector(force_refresh: bool = False) -> MetricData:
    """Provide a commercial-grade disk health overview leveraging SMART analytics."""

    if DiskHealthMonitor is None:
        return {"Disk Health": "Disk health monitoring not available"}

    try:
        global _disk_health_monitor
        with _disk_health_lock:
            if _disk_health_monitor is None:
                _disk_health_monitor = DiskHealthMonitor()
            monitor = _disk_health_monitor

        summaries = monitor.get_disk_health_summary(force_refresh=force_refresh)
        if not summaries:
            return {"Disk Health": "No disks detected"}

        result: Dict[str, str] = {}
        critical_disks = []
        warning_disks = []

        for disk in summaries:
            health_label = "OK"
            status_icon = "✅"

            if disk.smart_status and disk.smart_status.upper() not in {"PASSED", "OK"}:
                health_label = disk.smart_status.upper()
                status_icon = "🚨"
                critical_disks.append(disk.device)

            elif disk.errors:
                health_label = "Errors"
                status_icon = "🚨"
                critical_disks.append(disk.device)

            elif disk.warnings:
                health_label = "Warnings"
                status_icon = "⚠️"
                warning_disks.append(disk.device)

            elif disk.health_percentage is not None and disk.health_percentage < 80:
                health_label = f"{disk.health_percentage}%"
                status_icon = "🟡"
                warning_disks.append(disk.device)

            capacity = getattr(disk, "capacity_bytes", 0)
            capacity_str = format_bytes(capacity) if capacity else "Unknown"
            temperature = (
                f" | Temp {disk.temperature_celsius}°C" if disk.temperature_celsius is not None else ""
            )
            result[f"{status_icon} {disk.device}"] = (
                f"{health_label} | {disk.model or 'Unknown Model'} | {capacity_str}{temperature}"
            )

            if disk.reallocated_sectors:
                result[f"{disk.device} Reallocated"] = str(disk.reallocated_sectors)
            if disk.pending_sectors:
                result[f"{disk.device} Pending"] = str(disk.pending_sectors)
            if disk.uncorrectable_sectors:
                result[f"{disk.device} Uncorrectable"] = str(disk.uncorrectable_sectors)

        result["Critical Disks"] = (
            ", ".join(critical_disks) if critical_disks else "None"
        )
        result["Warning Disks"] = (
            ", ".join(warning_disks) if warning_disks else "None"
        )

        return result
    except Exception as e:
        return {"Error": f"Unable to collect disk health data: {str(e)}"}


def network_connection_summary_collector(include_localhost: bool = False, max_entries: int = 5) -> MetricData:
    """Summarise active network connections with security indicators."""

    if NetworkMonitor is None:
        return {"Network Connections": "Network monitoring dependencies unavailable"}

    try:
        global _network_monitor
        with _network_monitor_lock:
            if _network_monitor is None:
                _network_monitor = NetworkMonitor()
            monitor = _network_monitor

        connections = monitor.get_network_connections(include_localhost=include_localhost)
        if not connections:
            return {"Network Connections": "No active remote connections"}

        total_connections = len(connections)
        external_connections = sum(1 for conn in connections if not getattr(conn, "is_private", False))
        suspicious_connections = sum(1 for conn in connections if getattr(conn, "is_suspicious", False))
        unique_remotes = len({f"{conn.remote_address}:{conn.remote_port}" for conn in connections})

        result: Dict[str, str] = {
            "Total Connections": str(total_connections),
            "External Connections": str(external_connections),
            "Suspicious Flagged": str(suspicious_connections),
            "Unique Remote Endpoints": str(unique_remotes),
        }

        sort_key = lambda conn: (
            not getattr(conn, "is_suspicious", False),
            -int(getattr(conn, "bytes_sent", 0) + getattr(conn, "bytes_recv", 0)),
        )

        top_connections = sorted(connections, key=sort_key)[: max_entries]

        for index, conn in enumerate(top_connections, start=1):
            if getattr(conn, "is_suspicious", False):
                icon = "🚨"
            elif not getattr(conn, "is_private", False):
                icon = "🌐"
            else:
                icon = "🔒"

            country = getattr(conn, "country", None)
            location = f" | {country}" if country else ""
            process_name = getattr(conn, "process_name", "Unknown") or "Unknown"
            pid = getattr(conn, "pid", None)
            pid_repr = str(pid) if pid is not None else "N/A"
            bytes_total = getattr(conn, "bytes_sent", 0) + getattr(conn, "bytes_recv", 0)

            result[f"Connection {index} {icon}"] = (
                f"{conn.remote_address}:{conn.remote_port} via {process_name} (PID {pid_repr}, {conn.type}/{conn.family})"
                f" | Bytes {bytes_total}{location}"
            )

        return result
    except Exception as e:
        return {"Error": f"Unable to collect network connections: {str(e)}"}


def network_interface_summary_collector(max_entries: int = 5) -> MetricData:
    """Summarise network interface health, throughput, and wireless characteristics."""

    if NetworkMonitor is None:
        return {"Network Interfaces": "Network monitoring dependencies unavailable"}

    try:
        global _network_monitor
        with _network_monitor_lock:
            if _network_monitor is None:
                _network_monitor = NetworkMonitor()
            monitor = _network_monitor

        interfaces = monitor.get_network_interfaces()
        if not interfaces:
            return {"Network Interfaces": "No interfaces detected"}

        total_interfaces = len(interfaces)
        up_interfaces = sum(1 for iface in interfaces if iface.is_up)
        down_interfaces = total_interfaces - up_interfaces
        wifi_interfaces = [iface for iface in interfaces if iface.signal_strength is not None]

        now = time.monotonic()

        result: Dict[str, str] = {
            "Interfaces Detected": str(total_interfaces),
            "Interfaces Up": str(up_interfaces),
            "Interfaces Down": str(down_interfaces),
            "WiFi Interfaces": str(len(wifi_interfaces)),
        }

        high_error_ifaces = [
            iface.name
            for iface in interfaces
            if getattr(iface, "errors_in", 0) + getattr(iface, "errors_out", 0) > 0
        ]
        if high_error_ifaces:
            result["Interfaces With Errors"] = ", ".join(high_error_ifaces[:5])

        sorted_by_bytes = sorted(
            interfaces,
            key=lambda iface: iface.bytes_sent + iface.bytes_recv,
            reverse=True,
        )

        instantaneous_rates: List[Tuple[float, str]] = []

        for index, iface in enumerate(sorted_by_bytes[: max_entries], start=1):
            status_icon = "✅" if iface.is_up else "⚠️"
            link_type = "WiFi" if iface in wifi_interfaces else "Wired"
            throughput = format_bytes(iface.bytes_sent + iface.bytes_recv)
            speed = f"{iface.speed} Mb/s" if iface.speed else "Unknown"
            signal = (
                f" | Signal {iface.signal_strength}%"
                if iface.signal_strength is not None else ""
            )
            frequency = (
                f" @ {iface.frequency}GHz"
                if iface.frequency is not None else ""
            )

            ip_summary = ", ".join(iface.ip_addresses[:2])
            if len(iface.ip_addresses) > 2:
                ip_summary += " +..."

            tx_rate = "N/A"
            rx_rate = "N/A"
            with _interface_stats_lock:
                previous = _interface_stats_cache.get(iface.name)
                _interface_stats_cache[iface.name] = (iface.bytes_sent, iface.bytes_recv, now)

            if previous:
                prev_sent, prev_recv, prev_time = previous
                elapsed = max(now - prev_time, 0.001)
                delta_sent = max(iface.bytes_sent - prev_sent, 0)
                delta_recv = max(iface.bytes_recv - prev_recv, 0)
                tx_rate = f"{format_bytes(delta_sent / elapsed)}/s"
                rx_rate = f"{format_bytes(delta_recv / elapsed)}/s"
                instantaneous_rates.append(((delta_sent + delta_recv) / elapsed, iface.name))

            result[f"Interface {index} {status_icon}"] = (
                f"{iface.name} ({link_type}) | Speed {speed} | MTU {iface.mtu} | "
                f"Traffic {throughput}{signal}{frequency} | TX {tx_rate} RX {rx_rate} | IPs {ip_summary}"
            )

        if wifi_interfaces:
            strongest_wifi = max(wifi_interfaces, key=lambda iface: iface.signal_strength or -100)
            result["Strongest WiFi"] = (
                f"{strongest_wifi.name} {strongest_wifi.signal_strength}%"
            )

        if instantaneous_rates:
            peak_rate, peak_iface = max(instantaneous_rates, key=lambda item: item[0])
            result["Peak Live Throughput"] = f"{peak_iface} {format_bytes(peak_rate)}/s"

        return result
    except Exception as e:
        return {"Error": f"Unable to collect network interface data: {str(e)}"}


def swap_usage_collector() -> MetricData:
    """Collect detailed swap usage data with comprehensive error handling."""
    try:
        swap = psutil.swap_memory()
        result = {
            "Used": format_bytes(swap.used),
            "Free": format_bytes(swap.free),
            "Utilization": f"{swap.percent:.1f}%",
            "Total": format_bytes(swap.total),
        }

        # Swap activity (if available)
        try:
            if hasattr(swap, 'sin'):
                result["Swap In"] = format_bytes(swap.sin)
            if hasattr(swap, 'sout'):
                result["Swap Out"] = format_bytes(swap.sout)
        except (AttributeError, OSError):
            pass

        return result
    except Exception as e:
        return {"Error": f"Unable to collect swap data: {str(e)}"}


def network_io_collector() -> MetricData:
    """Collect comprehensive network IO data with quality indicators."""
    try:
        io = psutil.net_io_counters()
        result = {
            "Sent": format_bytes(io.bytes_sent),
            "Received": format_bytes(io.bytes_recv),
            "Packets Sent": str(io.packets_sent),
            "Packets Received": str(io.packets_recv),
            "Total Bytes": format_bytes(io.bytes_sent + io.bytes_recv),
        }

        # Network quality indicators
        if hasattr(io, 'errin'):
            result["Errors In"] = str(io.errin)
        if hasattr(io, 'errout'):
            result["Errors Out"] = str(io.errout)
        if hasattr(io, 'dropin'):
            result["Dropped In"] = str(io.dropin)
        if hasattr(io, 'dropout'):
            result["Dropped Out"] = str(io.dropout)

        # Network interface information
        try:
            net_interfaces = psutil.net_if_addrs()
            net_stats = psutil.net_if_stats()

            active_interfaces = []
            for interface, addresses in net_interfaces.items():
                if interface in net_stats:
                    stats = net_stats[interface]
                    if stats.isup:
                        active_interfaces.append(interface)

            result["Active Interfaces"] = str(len(active_interfaces))
            result["Interface Names"] = ", ".join(active_interfaces)

            # Get detailed interface stats for primary interface
            if active_interfaces:
                primary_if = active_interfaces[0]
                if primary_if in net_stats:
                    if_stats = net_stats[primary_if]
                    result["Primary Interface"] = primary_if
                    result["MTU"] = str(if_stats.mtu)
                    result["Speed"] = f"{if_stats.speed} Mb/s" if if_stats.speed else "Unknown"

        except (AttributeError, OSError):
            pass

        return result
    except Exception as e:
        return {"Error": f"Unable to collect network data: {str(e)}"}


def network_latency_collector(hosts: Optional[List[str]] = None, attempts: int = 3, timeout: float = 1.0) -> MetricData:
    """Collect network latency metrics by pinging common hosts with fallbacks."""
    try:
        import statistics
        import subprocess
        import platform

        default_hosts = [
            "8.8.8.8",
            "1.1.1.1",
            "www.google.com",
            "www.cloudflare.com",
        ]

        target_hosts = hosts or default_hosts
        result: Dict[str, str] = {}

        # Detect ping command based on platform
        system = platform.system().lower()
        ping_args = ["ping"]
        if system == "windows":
            ping_args.extend(["-n", str(attempts), "-w", str(int(timeout * 1000))])
        else:
            ping_args.extend(["-c", str(attempts), "-W", str(int(timeout))])

        for host in target_hosts:
            try:
                completed = subprocess.run(
                    ping_args + [host],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if completed.returncode != 0:
                    result[host] = "Timeout"
                    continue

                latencies: List[float] = []
                for line in completed.stdout.splitlines():
                    if "time=" in line:
                        try:
                            segment = line.split("time=")[-1]
                            value = segment.split()[0]
                            if value.endswith("ms"):
                                value = value[:-2]
                            latencies.append(float(value))
                        except ValueError:
                            continue

                if latencies:
                    avg = statistics.mean(latencies)
                    result[host] = f"{avg:.2f} ms"
                else:
                    result[host] = "No samples"
            except FileNotFoundError:
                result[host] = "Ping unavailable"
            except Exception:
                result[host] = "Error"

        return result if result else {"Latency": "No hosts tested"}
    except Exception as e:
        return {"Error": f"Unable to collect network latency: {str(e)}"}


def _run_ping_probe(host: str, attempts: int, timeout: float) -> Tuple[List[float], float]:
    """Execute a ping probe and return collected latencies plus packet loss percentage."""

    import platform
    import re
    import subprocess

    latencies: List[float] = []
    system = platform.system().lower()

    ping_args = ["ping"]
    if system == "windows":
        ping_args.extend(["-n", str(max(1, attempts)), "-w", str(int(max(timeout, 0.2) * 1000))])
    else:
        ping_args.extend(["-c", str(max(1, attempts)), "-W", str(int(max(timeout, 1.0)))])

    completed = subprocess.run(
        ping_args + [host],
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = completed.stdout or ""
    for line in stdout.splitlines():
        if "time=" not in line:
            continue
        try:
            segment = line.split("time=")[-1]
            value = segment.split()[0]
            if value.endswith("ms"):
                value = value[:-2]
            latencies.append(float(value))
        except (ValueError, IndexError):
            continue

    packet_loss: Optional[float] = None

    # Windows statistics format
    windows_stats = re.search(r"Sent = (\d+), Received = (\d+), Lost = (\d+)", stdout)
    if windows_stats:
        sent = int(windows_stats.group(1))
        received = int(windows_stats.group(2))
        packet_loss = 100.0 * (sent - received) / sent if sent > 0 else 100.0

    # POSIX statistics format
    if packet_loss is None:
        posix_stats = re.search(
            r"(\d+)\s+packets transmitted,\s+(\d+)\s+(?:packets )?received,.*?(\d+(?:\.\d+)?)% packet loss",
            stdout,
        )
        if posix_stats:
            sent = int(posix_stats.group(1))
            received = int(posix_stats.group(2))
            packet_loss = float(posix_stats.group(3))
        else:
            # Busybox / macOS alternative summary
            alt_stats = re.search(
                r"(\d+)\s+packets received,\s+(\d+)\s+packets transmitted", stdout
            )
            if alt_stats:
                received = int(alt_stats.group(1))
                sent = int(alt_stats.group(2))
                packet_loss = 100.0 * (sent - received) / sent if sent > 0 else 100.0

    if packet_loss is None:
        effective_attempts = max(1, attempts)
        packet_loss = 100.0 * max(effective_attempts - len(latencies), 0) / effective_attempts

    return latencies, float(min(max(packet_loss, 0.0), 100.0))


def network_quality_collector(hosts: Optional[List[str]] = None, attempts: int = 5, timeout: float = 1.0) -> MetricData:
    """Assess network quality including latency, jitter, and packet loss for target hosts."""

    try:
        from statistics import mean, pstdev

        default_hosts = [
            "8.8.8.8",
            "1.1.1.1",
            "www.google.com",
        ]

        target_hosts = hosts or default_hosts
        host_summaries: List[Dict[str, Any]] = []

        for host in target_hosts:
            try:
                latencies, packet_loss = _run_ping_probe(host, attempts, timeout)
            except FileNotFoundError:
                host_summaries.append(
                    {
                        "host": host,
                        "status": "Ping command unavailable",
                        "latencies": [],
                        "packet_loss": 100.0,
                    }
                )
                continue
            except Exception as exc:  # pragma: no cover - defensive
                host_summaries.append(
                    {
                        "host": host,
                        "status": f"Probe error: {exc}",
                        "latencies": [],
                        "packet_loss": 100.0,
                    }
                )
                continue

            status = "OK" if latencies else "Unreachable"
            jitter = pstdev(latencies) if len(latencies) > 1 else 0.0
            summary = {
                "host": host,
                "status": status,
                "latencies": latencies,
                "packet_loss": packet_loss,
                "average": mean(latencies) if latencies else None,
                "minimum": min(latencies) if latencies else None,
                "maximum": max(latencies) if latencies else None,
                "jitter": jitter,
            }
            host_summaries.append(summary)

        reachable_hosts = [item for item in host_summaries if item["latencies"]]

        result: Dict[str, str] = {}

        if reachable_hosts:
            primary = min(reachable_hosts, key=lambda item: item["average"] or float("inf"))
            result["Primary Host"] = primary["host"]
            result["Average Latency"] = f"{primary['average']:.2f} ms"
            result["Latency Range"] = (
                f"{primary['minimum']:.2f}-{primary['maximum']:.2f} ms" if primary["minimum"] is not None else "N/A"
            )
            result["Jitter"] = f"{primary['jitter']:.2f} ms"
            result["Packet Loss"] = f"{primary['packet_loss']:.1f}%"

            best_host = primary
            worst_host = max(reachable_hosts, key=lambda item: item["average"] or -1)
            result["Best Host"] = f"{best_host['host']} ({best_host['average']:.2f} ms)"
            result["Worst Host"] = f"{worst_host['host']} ({worst_host['average']:.2f} ms)"

            overall_loss = mean(item["packet_loss"] for item in reachable_hosts)
            result["Average Packet Loss"] = f"{overall_loss:.1f}%"
        else:
            result["Network Quality"] = "No hosts reachable"

        for index, summary in enumerate(host_summaries, start=1):
            host_label = f"Host {index}: {summary['host']}"
            if summary["latencies"]:
                result[host_label] = (
                    f"{summary['average']:.2f} ms avg, {summary['packet_loss']:.1f}% loss, jitter {summary['jitter']:.2f} ms"
                )
            else:
                result[host_label] = summary.get("status", "Unreachable")

        return result

    except Exception as e:
        return {"Error": f"Unable to assess network quality: {str(e)}"}


def disk_io_collector() -> MetricData:
    """Collect disk IO counters with performance indicators."""
    try:
        io = psutil.disk_io_counters()
        result = {
            "Read Bytes": format_bytes(io.read_bytes),
            "Write Bytes": format_bytes(io.write_bytes),
            "Read Ops": str(io.read_count),
            "Write Ops": str(io.write_count),
            "Busy Time": f"{io.busy_time / 1000:.2f}s" if hasattr(io, "busy_time") else "N/A",
        }

        if hasattr(io, "read_time"):
            result["Read Time"] = f"{io.read_time / 1000:.2f}s"
        if hasattr(io, "write_time"):
            result["Write Time"] = f"{io.write_time / 1000:.2f}s"

        return result
    except Exception as e:
        return {"Error": f"Unable to collect disk IO data: {str(e)}"}


def disk_latency_collector(max_devices: int = 6) -> MetricData:
    """Analyse disk latency, utilisation, and trend data using rolling history."""

    try:
        per_disk = psutil.disk_io_counters(perdisk=True)
        if not per_disk:
            return {"Disk Latency": "Per-disk counters not available"}

        now = time.time()
        devices: List[Tuple[str, Optional[Dict[str, Any]]]] = []

        with _disk_latency_lock:
            for device, counters in per_disk.items():
                current_snapshot = (
                    now,
                    counters.read_count,
                    counters.write_count,
                    float(getattr(counters, "read_time", 0.0)),
                    float(getattr(counters, "write_time", 0.0)),
                    float(getattr(counters, "busy_time", 0.0)),
                )

                previous = _disk_latency_cache.get(device)
                _disk_latency_cache[device] = current_snapshot

                if previous is None:
                    devices.append((device, None))
                    continue

                prev_time, prev_rc, prev_wc, prev_rt, prev_wt, prev_bt = previous
                elapsed = max(now - prev_time, 1e-3)

                delta_rc = counters.read_count - prev_rc
                delta_wc = counters.write_count - prev_wc
                delta_rt = float(getattr(counters, "read_time", 0.0)) - prev_rt
                delta_wt = float(getattr(counters, "write_time", 0.0)) - prev_wt
                delta_bt = float(getattr(counters, "busy_time", 0.0)) - prev_bt

                if elapsed <= 0 or (delta_rc < 0 or delta_wc < 0):
                    devices.append((device, None))
                    continue

                read_latency = delta_rt / max(delta_rc, 1) if delta_rc > 0 else 0.0
                write_latency = delta_wt / max(delta_wc, 1) if delta_wc > 0 else 0.0
                total_ops = max(delta_rc + delta_wc, 0)
                iops = total_ops / elapsed
                busy_pct = 0.0
                if delta_bt > 0:
                    busy_pct = max(0.0, min((delta_bt / (elapsed * 1000.0)) * 100.0, 100.0))

                history = _disk_latency_history[device]
                history.append((now, busy_pct))
                cutoff = now - _DISK_LATENCY_WINDOW_SECONDS
                while history and history[0][0] < cutoff:
                    history.popleft()
                history_values = [value for _, value in history]

                devices.append(
                    (
                        device,
                        {
                            "util": busy_pct,
                            "read_latency": read_latency,
                            "write_latency": write_latency,
                            "iops": iops,
                            "history": history_values,
                            "delta_rc": delta_rc,
                            "delta_wc": delta_wc,
                            "delta_rt": delta_rt,
                            "delta_wt": delta_wt,
                        },
                    )
                )

        if not devices:
            return {"Disk Latency": "No disk samples"}

        result: Dict[str, str] = {}
        latency_alerts = []
        busy_ranking: List[Tuple[str, float]] = []

        for device, data in devices:
            friendly_name = device.replace("_", " ")
            if data is None:
                result[friendly_name] = "Collecting samples..."
                continue

            busy_ranking.append((friendly_name, data["util"]))

            read_ms = data["read_latency"]
            write_ms = data["write_latency"]
            util = data["util"]
            iops = data["iops"]

            detail = (
                f"{util:.1f}% util | R {read_ms:.2f} ms | W {write_ms:.2f} ms | "
                f"IOPS {iops:.1f}"
            )

            history_values = data["history"]
            if len(history_values) >= 4:
                detail += f" | Trend {generate_sparkline(history_values[-12:])}"
                delta_util = history_values[-1] - history_values[0]
                if delta_util > 5:
                    detail += " ↑"
                elif delta_util < -5:
                    detail += " ↓"

            result[friendly_name] = detail

            if read_ms > 25 or write_ms > 30:
                latency_alerts.append(
                    f"{friendly_name} R {read_ms:.1f} ms W {write_ms:.1f} ms"
                )

        busy_ranking.sort(key=lambda item: item[1], reverse=True)
        if busy_ranking:
            top_busy = ", ".join(
                f"{name} {util:.1f}%" for name, util in busy_ranking[:max_devices]
            )
            result["🔥 Busiest Disks"] = top_busy

        if latency_alerts:
            result["⚠️ High Latency"] = "; ".join(latency_alerts[:max_devices])

        return result
    except Exception as e:
        return {"Error": f"Unable to analyse disk latency: {str(e)}"}


def disk_usage_collector() -> MetricData:
    """Collect disk usage details with health indicators and capacity forecasting."""
    try:
        partitions = psutil.disk_partitions()
        result: Dict[str, str] = {}

        total_usage = 0
        total_space = 0
        partition_count = 0

        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                device_name = partition.device.split('/')[-1] if '/' in partition.device else partition.device

                result[f"{device_name} Used"] = format_bytes(usage.used)
                result[f"{device_name} Free"] = format_bytes(usage.free)
                result[f"{device_name} Total"] = format_bytes(usage.total)
                result[f"{device_name} Utilization"] = f"{usage.percent:.1f}%"

                partition_count += 1
                total_usage += usage.used
                total_space += usage.total

                # Estimate days until full based on current utilization trend (naive projection)
                if usage.percent > 0:
                    remaining = max(100 - usage.percent, 0.01)
                    daily_growth = usage.percent / 30  # assume last month trend
                    days_until_full = remaining / daily_growth if daily_growth > 0 else float("inf")
                    if days_until_full == float("inf"):
                        result[f"{device_name} Days Until Full"] = ">365"
                    else:
                        result[f"{device_name} Days Until Full"] = f"{days_until_full:.0f}"

            except (PermissionError, OSError):
                continue

        if partition_count > 0 and total_space > 0:
            overall_percent = (total_usage / total_space) * 100
            result["Overall Usage"] = f"{overall_percent:.1f}%"
            result["Total Partitions"] = str(partition_count)

        return result if result else {"No disks": "No accessible disk partitions found"}
    except Exception as e:
        return {"Error": f"Unable to collect disk usage data: {str(e)}"}


def system_uptime_collector() -> MetricData:
    """Collect system uptime data with comprehensive error handling."""
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = (datetime.now() - boot_time).total_seconds()
        return {
            "Boot": boot_time.strftime("%Y-%m-%d %H:%M:%S"),
            "Uptime": format_duration(uptime_seconds),
        }
    except Exception as e:
        return {"Error": f"Unable to collect uptime data: {str(e)}"}


def battery_health_collector() -> MetricData:
    """Collect battery status and health indicators."""
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return {"Battery": "No battery detected"}

        result: Dict[str, str] = {
            "Charge": f"{battery.percent:.1f}%",
            "Power Plugged": "Yes" if battery.power_plugged else "No",
        }

        # Estimate time remaining or time to full charge
        if battery.secsleft not in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED):
            direction = "until empty" if not battery.power_plugged else "until full"
            result[f"Time {direction}"] = format_duration(battery.secsleft)

        # Provide basic health indicator based on charge trends if available
        if hasattr(battery, "voltage") and battery.voltage:
            result["Voltage"] = f"{battery.voltage:.2f} V"
        if hasattr(battery, "current") and battery.current:
            result["Current"] = f"{battery.current:.2f} A"

        # Enrich with OS-specific health metrics
        system = platform.system().lower()

        if system == "windows":
            try:
                from win32com.client import Dispatch  # type: ignore

                wmi = Dispatch("WbemScripting.SWbemLocator")
                service = wmi.ConnectServer(".", "root\\WMI")
                for item in service.ExecQuery("SELECT * FROM BatteryStatus"):
                    if hasattr(item, "RemainingCapacity") and getattr(item, "FullChargeCapacity", 0):
                        full_capacity = float(item.FullChargeCapacity)
                        remaining_capacity = float(item.RemainingCapacity)
                        if full_capacity > 0:
                            wear = 100 - (full_capacity / max(item.DesignCapacity or full_capacity, 1) * 100)
                            result["Design Capacity"] = f"{item.DesignCapacity} mWh"
                            result["Full Charge Capacity"] = f"{full_capacity} mWh"
                            result["Remaining Capacity"] = f"{remaining_capacity} mWh"
                            result["Health"] = f"{max(0.0, 100 - wear):.1f}%"
                            break
            except Exception:
                pass

        elif system == "darwin":
            try:
                output = subprocess.check_output(
                    [
                        "/usr/sbin/system_profiler",
                        "SPPowerDataType",
                        "-xml",
                    ],
                    timeout=5,
                )
                if output:
                    import plistlib

                    data = plistlib.loads(output)
                    batteries = data[0]["_items"]
                    if batteries:
                        battery_data = batteries[0]
                        design_capacity = battery_data.get("max_capacity")
                        current_capacity = battery_data.get("current_capacity")
                        cycle_count = battery_data.get("cycle_count")
                        condition = battery_data.get("condition")
                        if design_capacity:
                            result["Design Capacity"] = f"{design_capacity} mAh"
                        if current_capacity:
                            result["Full Charge Capacity"] = f"{current_capacity} mAh"
                        if cycle_count is not None:
                            result["Cycle Count"] = str(cycle_count)
                        if condition:
                            result["Condition"] = condition
            except Exception:
                pass

        elif system == "linux":
            try:
                capacity_path = Path("/sys/class/power_supply")
                for supply in capacity_path.glob("BAT*/"):
                    design_cap_file = supply / "energy_full_design"
                    energy_full_file = supply / "energy_full"
                    if design_cap_file.exists() and energy_full_file.exists():
                        design = float(design_cap_file.read_text().strip())
                        full = float(energy_full_file.read_text().strip())
                        if design > 0:
                            health_percent = (full / design) * 100
                            result["Design Capacity"] = f"{design:.0f} mWh"
                            result["Full Charge Capacity"] = f"{full:.0f} mWh"
                            result["Health"] = f"{health_percent:.1f}%"
                            break
            except Exception:
                pass

        # Integrate short-term history for trend alerts
        now = time.monotonic()
        with _battery_history_lock:
            _battery_history.append((now, float(battery.percent)))
            cutoff = now - _BATTERY_HISTORY_WINDOW_SECONDS
            while _battery_history and _battery_history[0][0] < cutoff:
                _battery_history.popleft()

            if len(_battery_history) >= 2:
                first_time, first_pct = _battery_history[0]
                last_time, last_pct = _battery_history[-1]
                elapsed_hours = max((last_time - first_time) / 3600, 0.0001)
                delta_pct = last_pct - first_pct

                if not battery.power_plugged and delta_pct < -10:
                    result["Alert"] = "Steep discharge in last 15m"
                if battery.power_plugged and delta_pct < 0:
                    result["Warning"] = "Charge level dropping while plugged in"

        return result
    except Exception as e:
        return {"Error": f"Unable to collect battery data: {str(e)}"}


def power_draw_collector() -> MetricData:
    """Collect system power draw information with graceful fallbacks."""
    try:
        result: Dict[str, str] = {}

        now = time.monotonic()
        # Use battery stats if available
        battery = psutil.sensors_battery()
        if battery is not None:
            if hasattr(battery, "power") and battery.power:
                result["Battery Power"] = f"{battery.power:.2f} W"
            elif battery.percent is not None and battery.secsleft not in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED):
                # Rough estimate: energy change per second multiplied by battery capacity baseline (assume 50Wh typical laptop battery)
                estimated_watts = max((battery.percent / 100) * 50 / max(battery.secsleft / 3600, 0.01), 0)
                result["Estimated Power"] = f"{estimated_watts:.2f} W"

            result["Charging"] = "Yes" if battery.power_plugged else "No"
            result["Battery Level"] = f"{battery.percent:.1f}%"

            with _battery_history_lock:
                _battery_history.append((now, float(battery.percent)))
                cutoff = now - _BATTERY_HISTORY_WINDOW_SECONDS
                while _battery_history and _battery_history[0][0] < cutoff:
                    _battery_history.popleft()

                if len(_battery_history) >= 2:
                    first_time, first_pct = _battery_history[0]
                    last_time, last_pct = _battery_history[-1]
                    elapsed_hours = max((last_time - first_time) / 3600, 0.0001)
                    delta_pct = last_pct - first_pct
                    drain_rate = -delta_pct / elapsed_hours

                    if drain_rate > 0:
                        result["Projected Runtime"] = f"{last_pct / drain_rate:.1f} h"
                    elif delta_pct > 0 and battery.power_plugged:
                        result["Projected Full"] = f"{(100 - last_pct) / (delta_pct / elapsed_hours):.1f} h"

                    if drain_rate > 20:
                        result["Alert"] = "Rapid discharge detected"

        # Try psutil sensors for AC line or other power info if available
        try:
            if hasattr(psutil, "sensors_power"):
                power_info = psutil.sensors_power()
                if power_info:
                    for sensor in power_info:
                        label = (sensor.label or "Power Sensor").strip()
                        if label.lower().startswith("gpu"):
                            label = label.replace("GPU", "GPU", 1)
                        result[f"{label} Power"] = f"{sensor.power:.2f} W"
        except (AttributeError, NotImplementedError):
            pass

        if not result:
            with _battery_history_lock:
                if len(_battery_history) >= 2:
                    first_time, first_pct = _battery_history[0]
                    last_time, last_pct = _battery_history[-1]
                    elapsed_hours = max((last_time - first_time) / 3600, 0.0001)
                    delta_pct = last_pct - first_pct
                    drain_rate = -delta_pct / elapsed_hours
                    if drain_rate > 0:
                        estimated_watts = drain_rate * 50
                        result["Estimated Power (History)"] = f"{estimated_watts:.2f} W"

        return result if result else {"Power": "No power sensors available"}
    except Exception as e:
        return {"Error": f"Unable to collect power data: {str(e)}"}


def detailed_processes_collector(limit: int = 8) -> MetricData:
    """詳細なプロセス情報を効率的に収集"""
    try:
        processes = []

        # プロセス情報を効率的に収集（必要な属性のみ）
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info", "status", "create_time"]):
            try:
                # 基本的なCPU使用率を取得（非ブロッキング）
                cpu_percent = proc.cpu_percent(interval=0.0) or 0.0

                # CPU使用率が低いプロセスはスキップ（CPU最適化）
                if cpu_percent < 0.1:
                    continue

                info = proc.info
                memory_info = info.get("memory_info")

                # メモリ情報が取得できない場合はスキップ
                if memory_info is None:
                    continue

                memory_mb = memory_info.rss / (1024 * 1024)  # 計算結果をキャッシュ
                create_time = info.get("create_time", 0)
                uptime_hours = (datetime.now().timestamp() - create_time) / 3600

                processes.append((cpu_percent + info.get("memory_percent", 0.0), cpu_percent, info.get("memory_percent", 0.0), memory_mb, uptime_hours, info.get("pid"), info.get("name", "Unknown"), info.get("status", "unknown")))

                # 収集数を制限してCPU使用量を削減
                if len(processes) >= limit * 2:  # 2倍収集してソート後に制限
                    break

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # 効率的なソート（事前に計算されたスコアを使用）
        processes.sort(reverse=True, key=lambda x: x[0])
        top = processes[:limit]

        result: Dict[str, str] = {}
        for index, (_, cpu_pct, mem_pct, mem_mb, uptime, pid, name, status) in enumerate(top, start=1):
            display_name = name[:10] + "..." if len(name) > 13 else name
            label = f"{index}. {display_name} ({pid})"

            # uptimeの効率的なフォーマット
            if uptime < 1:
                uptime_str = f"{uptime * 60:.0f}m"
            elif uptime < 24:
                uptime_str = f"{uptime:.1f}h"
            else:
                uptime_str = f"{uptime / 24:.1f}d"

            value = f"CPU:{cpu_pct:.1f}% MEM:{mem_pct:.1f}%({mem_mb:.0f}MB) UP:{uptime_str}"
            result[label] = value

        return result if result else {"No processes found": "System access restricted"}

    except Exception as e:
        return {"Error": f"Process collection failed: {str(e)}"}

def top_memory_processes_collector(limit: int = 3) -> MetricData:
    """Collect top memory consuming processes with optimized performance."""
    try:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = proc.info
                memory = info.get("memory_info")
                if memory is None:
                    continue
                processes.append((memory.rss, info.get("pid"), info.get("name", "")))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        processes.sort(reverse=True)
        top = processes[:limit]
        result: Dict[str, str] = {}
        for index, (rss, pid, name) in enumerate(top, start=1):
            label = f"{index}. PID {pid}"
            if name:
                label = f"{label} {name}"
            result[label] = format_bytes(float(rss))
        return result if result else {"No data": "Access restricted"}
    except Exception as e:
        return {"Error": f"Unable to collect memory process data: {str(e)}"}


def process_cpu_table_collector(limit: int = 5) -> MetricData:
    """Collect process-level CPU usage table with current percentages."""
    try:
        samples = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                cpu_percent = proc.cpu_percent(interval=0.0)
                if cpu_percent is None:
                    cpu_percent = 0.0
                samples.append((cpu_percent, proc.pid, proc.info.get("name", "")))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        samples.sort(reverse=True)
        top = [sample for sample in samples if sample[0] > 0][:limit]
        if not top:
            top = samples[:limit]

        result: Dict[str, str] = {}
        for index, (cpu_percent, pid, name) in enumerate(top, start=1):
            label = f"{index}. PID {pid}"
            if name:
                label = f"{label} {name}"
            result[label] = f"{cpu_percent:.1f}%"

        return result if result else {"No data": "CPU usage not available"}
    except Exception as e:
        return {"Error": f"Unable to collect process CPU data: {str(e)}"}


def process_details_collector(pid: int) -> MetricData:
    """Collect detailed information for a specific process."""
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            name = proc.name()
            status = proc.status()
            create_time = proc.create_time()
            cpu_times = proc.cpu_times()
            cpu_percent = proc.cpu_percent(interval=0.1)
            memory_info = proc.memory_info()
            memory_percent = proc.memory_percent()

        result: Dict[str, str] = {
            "Process Name": name,
            "Status": status,
            "CPU Usage": f"{cpu_percent:.1f}%",
            "Memory Usage": format_bytes(memory_info.rss),
            "Memory Percent": f"{memory_percent:.1f}%",
            "User Time": f"{cpu_times.user:.2f}s",
            "System Time": f"{cpu_times.system:.2f}s",
            "Created": datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S"),
        }

        try:
            result["Working Directory"] = str(proc.cwd())
        except (psutil.AccessDenied, FileNotFoundError):
            pass

        try:
            cmdline = proc.cmdline()
            if cmdline:
                result["Command Line"] = " ".join(cmdline)
        except (psutil.AccessDenied, FileNotFoundError):
            pass

        return result
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"Error": f"Process {pid} not found or access denied"}
    except Exception as e:
        return {"Error": f"Unable to gather process details: {str(e)}"}


def process_kill_collector(pid: int) -> MetricData:
    """Kill a process by PID with comprehensive error handling."""
    try:
        proc = psutil.Process(pid)
        proc_name = proc.name()
        proc.terminate()

        # Wait a moment for graceful termination
        try:
            proc.wait(timeout=3)
            return {
                "Status": "Terminated",
                "Process Name": proc_name,
                "PID": str(pid),
                "Method": "SIGTERM"
            }
        except psutil.TimeoutExpired:
            # Force kill if graceful termination fails
            proc.kill()
            return {
                "Status": "Killed",
                "Process Name": proc_name,
                "PID": str(pid),
                "Method": "SIGKILL"
            }

    except psutil.NoSuchProcess:
        return {"Error": f"Process {pid} not found"}
    except psutil.AccessDenied:
        return {"Error": f"Access denied to process {pid}"}
    except Exception as e:
        return {"Error": f"Unable to kill process {pid}: {str(e)}"}


def process_priority_collector(pid: int, priority: str) -> MetricData:
    """Change process priority with comprehensive error handling."""
    try:
        proc = psutil.Process(pid)
        proc_name = proc.name()

        # Map priority string to psutil constants
        priority_map = {
            "realtime": psutil.REALTIME_PRIORITY_CLASS,
            "high": psutil.HIGH_PRIORITY_CLASS,
            "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
            "normal": psutil.NORMAL_PRIORITY_CLASS,
            "below_normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
            "idle": psutil.IDLE_PRIORITY_CLASS,
        }

        if priority not in priority_map:
            return {"Error": f"Invalid priority: {priority}. Use: {', '.join(priority_map.keys())}"}

        old_priority = proc.nice()
        proc.nice(priority_map[priority])
        new_priority = proc.nice()

        return {
            "Process Name": proc_name,
            "PID": str(pid),
            "Old Priority": str(old_priority),
            "New Priority": str(new_priority),
            "Priority Class": priority,
            "Status": "Changed"
        }

    except psutil.NoSuchProcess:
        return {"Error": f"Process {pid} not found"}
    except psutil.AccessDenied:
        return {"Error": f"Access denied to process {pid}"}
    except Exception as e:
        return {"Error": f"Unable to change priority for process {pid}: {str(e)}"}


DEFAULT_REGISTRY = MetricRegistry(
    metrics=[
        Metric(
            identifier="per_core_sparkline",
            name="Per-Core CPU Sparklines",
            description="Individual CPU core utilization for sparkline display",
            collect=per_core_sparkline_collector,
        ),
        Metric(
            identifier="cpu_trend",
            name="CPU Trend Data",
            description="CPU usage trend data for historical graphing",
            collect=cpu_trend_collector,
        ),
        Metric(
            identifier="memory_usage",
            name="Memory Usage",
            description="System RAM usage",
            collect=memory_usage_collector,
        ),
        Metric(
            identifier="memory_pressure",
            name="Memory Pressure",
            description="Composite memory pressure indicator for RAM and swap",
            collect=memory_pressure_collector,
        ),
        Metric(
            identifier="disk_health_summary",
            name="Disk Health Summary",
            description="SMART-driven disk health overview",
            collect=disk_health_summary_collector,
        ),
        Metric(
            identifier="swap_usage",
            name="Swap Usage",
            description="Swap memory utilization",
            collect=swap_usage_collector,
        ),
        Metric(
            identifier="network_io",
            name="Network IO",
            description="Network input/output counters",
            collect=network_io_collector,
        ),
        Metric(
            identifier="network_latency",
            name="Network Latency",
            description="Latency measurements to common hosts",
            collect=network_latency_collector,
        ),
        Metric(
            identifier="network_connection_summary",
            name="Network Connection Summary",
            description="Active network connections with security indicators",
            collect=network_connection_summary_collector,
        ),
        Metric(
            identifier="network_interface_summary",
            name="Network Interface Summary",
            description="Interface health, throughput, and wireless characteristics",
            collect=network_interface_summary_collector,
        ),
        Metric(
            identifier="disk_usage",
            name="Disk Usage",
            description="Comprehensive disk usage with health indicators and capacity forecasting",
            collect=disk_usage_collector,
        ),
        Metric(
            identifier="disk_io",
            name="Disk IO",
            description="Disk IO counters with performance indicators",
            collect=disk_io_collector,
        ),
        Metric(
            identifier="disk_latency",
            name="Disk Latency Analytics",
            description="Per-disk latency, utilisation, and trend analysis",
            collect=disk_latency_collector,
        ),
        Metric(
            identifier="system_uptime",
            name="System Uptime",
            description="System boot time and uptime",
            collect=system_uptime_collector,
        ),
        Metric(
            identifier="battery_health",
            name="Battery Health",
            description="Battery status and charge indicators",
            collect=battery_health_collector,
        ),
        Metric(
            identifier="power_draw",
            name="Power Draw",
            description="System power usage estimates with sensor fallbacks",
            collect=power_draw_collector,
        ),
        Metric(
            identifier="system_temperatures",
            name="System Temperatures",
            description="System temperature sensors",
            collect=system_temperatures_collector,
        ),
        Metric(
            identifier="gpu_usage",
            name="GPU Usage",
            description="GPU utilization and memory usage",
            collect=gpu_usage_collector,
        ),
        Metric(
            identifier="top_cpu_processes",
            name="Top CPU Processes",
            description="Processes with highest real-time CPU usage",
            collect=top_cpu_processes_collector,
        ),
        Metric(
            identifier="detailed_processes",
            name="Detailed Processes",
            description="Comprehensive process monitoring with CPU, memory, and uptime",
            collect=detailed_processes_collector,
        ),
        Metric(
            identifier="top_memory_processes",
            name="Top Memory Processes",
            description="Processes consuming the most memory",
            collect=top_memory_processes_collector,
        ),
        Metric(
            identifier="process_details",
            name="Process Details",
            description="Detailed process metrics for selected PID",
            collect=lambda: {"Info": "Provide PID via ProcessDetailsService"},
        ),
        Metric(
            identifier="alert_monitor",
            name="Alert Monitor",
            description="System alerts and threshold monitoring",
            collect=alert_monitor_collector,
        ),
        Metric(
            identifier="cpu_usage",
            name="CPU Usage",
            description="Enhanced CPU usage with trend analysis",
            collect=cpu_usage_collector,
        ),
        Metric(
            identifier="fan_speeds",
            name="Fan Speeds",
            description="System fan speed monitoring",
            collect=fan_speeds_collector,
        ),
        Metric(
            identifier="ai_predictions",
            name="AI Predictions",
            description="AI-powered predictions and anomaly detection for system metrics",
            collect=ai_prediction_collector,
        ),
        Metric(
            identifier="container_monitoring",
            name="Container Monitoring",
            description="Docker and Kubernetes container monitoring with resource usage",
            collect=container_monitor_collector,
        ),
        Metric(
            identifier="workflow_automation",
            name="Workflow Automation",
            description="Automated remediation and conditional script execution",
            collect=workflow_automation_collector,
        ),
        Metric(
            identifier="ticket_system",
            name="Ticket Management",
            description="Incident tracking and technician task management",
            collect=ticket_system_collector,
        ),
        Metric(
            identifier="external_integrations",
            name="External Integrations",
            description="ServiceNow, Zendesk, Jira, and Slack integration status",
            collect=external_integration_collector,
        ),
    ]
)


# 時系列データベースへのメトリクス書き込み関数
def _write_metric_to_timeseries(metric_id: str, data: Dict[str, str]) -> None:
    """メトリクスデータを時系列データベースに書き込む"""
    if not HAS_TIMESERIES:
        return

    try:
        # 数値データを抽出して時系列データベースに書き込み
        for key, value_str in data.items():
            try:
                # パーセント記号を除去して数値に変換
                if '%' in value_str:
                    value = float(value_str.rstrip('%'))
                else:
                    value = float(value_str)

                # 時系列データベースに書き込み
                write_metric_to_timeseries(
                    measurement=metric_id,
                    value=value,
                    tags={'field': key}
                )

            except (ValueError, TypeError):
                # 数値変換できない場合はスキップ
                continue

    except Exception as e:
        logger.debug(f"時系列データベース書き込みエラー: {e}")


# 既存のメトリクス収集関数を拡張
def collect_metric_with_timeseries(metric_id: str) -> Dict[str, str]:
    """メトリクスを収集し、時系列データベースにも書き込む"""
    metric = get_metric(metric_id)
    if not metric:
        return {}

    data = metric.collect()

    # 時系列データベースに書き込み
    _write_metric_to_timeseries(metric_id, data)

    return data
