from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Deque, Dict, List, Optional, Tuple

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QKeySequence, QShortcut

from .metrics import (
    DEFAULT_REGISTRY,
    HAS_TIMESERIES,
    Metric,
    MetricHistory,
    MetricRegistry,
    configure_network_monitor_bandwidth,
    configure_network_quality,
)
from .unified_config import MoniConfig, DEFAULT_CONFIG_DIR
from .ai_detector import AIDetector
from .fire_detection import FireDetector
from .auto_alert_manager import AutoAlertManager
from .quantum_security import QuantumSecurityManager

if TYPE_CHECKING:
    from .ui.overlay import OverlayWindow, CPUSparklineOverlay


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MoniContext:
    """Shared runtime context for UI components and automation features."""

    config: MoniConfig
    registry: MetricRegistry
    metric_history: MetricHistory
    ai_detector: AIDetector
    fire_detector: FireDetector
    auto_alert_manager: AutoAlertManager
    quantum_security_manager: QuantumSecurityManager


class MoniApplication(QApplication):
    def __init__(
        self,
        argv: list[str],
        config: Optional[MoniConfig] = None,
        registry: Optional[MetricRegistry] = None,
    ) -> None:
        super().__init__(argv)
        self.setApplicationName("Moni")

        resolved_config = config or MoniConfig.load()

        bandwidth_config = resolved_config.automation.network.bandwidth_test
        bandwidth_payload = bandwidth_config.model_dump()
        if not bandwidth_payload.get("download_endpoint"):
            bandwidth_payload["enabled"] = False
            bandwidth_config.enabled = False
        configure_network_monitor_bandwidth(bandwidth_payload)

        quality_config = resolved_config.automation.network.quality_test
        quality_payload = quality_config.model_dump()
        if quality_payload.get("enabled") and not quality_payload.get("hosts"):
            quality_payload["enabled"] = False
            quality_config.enabled = False
        configure_network_quality(quality_payload)

        resolved_registry = registry or DEFAULT_REGISTRY

        # Initialize detection modules
        ai_detector = AIDetector()
        fire_detector = FireDetector()
        auto_alert_manager = AutoAlertManager()
        quantum_security_manager = QuantumSecurityManager()

        self._context = MoniContext(
            config=resolved_config,
            registry=resolved_registry,
            metric_history=MetricHistory(
                max_entries=resolved_config.automation.history.max_entries
            ),
            ai_detector=ai_detector,
            fire_detector=fire_detector,
            auto_alert_manager=auto_alert_manager,
            quantum_security_manager=quantum_security_manager,
        )
        self._overlay_window = OverlayWindow(
            context=self._context,
            refresh_interval_callback=self.update_refresh_interval,
            logging_config_callback=self.configure_logging,
            alert_config_callback=self.configure_alerts,
            profile_config_callback=self.configure_profile,
            clear_alerts_callback=self.clear_alert_history,
        )
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self._context.config.overlay.refresh_interval_ms)
        self._refresh_timer.timeout.connect(self.refresh_metrics)  # type: ignore[arg-type]
        self._configure_overlay()
        self._logging_timer = QTimer(self)
        self._logging_timer.timeout.connect(self._log_metrics_sample)  # type: ignore[arg-type]
        self._configure_logging()
        self._last_cpu_percent: Optional[float] = None
        self._last_memory_percent: Optional[float] = None
        self._active_alerts: List[str] = []
        self._alert_history: Deque[Tuple[int, str]] = deque(maxlen=100)
        self._latest_metrics_payload: dict[str, dict[str, str]] = {}
        self._latest_metrics_timestamp: Optional[int] = None
        self._last_log_timestamp: Optional[int] = None
        self._last_alert_checks: dict[str, int] = {}
        self._alert_instance_counts: Dict[str, int] = {}
        self._last_alert_timestamp: Optional[int] = None
        self._cpu_overlay: Optional[CPUSparklineOverlay] = None
        self._global_shortcuts: List[QShortcut] = []

        # Setup system tray
        self._setup_system_tray()

        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()

        self._update_automation_panels()

        # 時系列データベースマネージャーの初期化
        if self._context.config.timeseries.enabled:
            try:
                from .timeseries_db import init_timeseries_manager
                init_timeseries_manager(self._context.config.timeseries)
                logger.info("時系列データベースマネージャーを初期化しました")
            except Exception as e:
                logger.error(f"時系列データベース初期化エラー: {e}")

        self._webhook_started = False

        if self._context.config.webhook.enabled:
            try:
                from .webhook import init_webhook_manager, start_webhook_manager_background

                webhook_manager = init_webhook_manager()
                webhook_manager.add_webhook("default", self._context.config.webhook)
                start_webhook_manager_background()
                self._webhook_started = True
                logger.info("Webhookマネージャーを初期化しました")
            except Exception as e:
                logger.error(f"Webhook初期化エラー: {e}")

        self.aboutToQuit.connect(self._shutdown_background_services)  # type: ignore[arg-type]

        # 依存関係マップマネージャーの初期化
        if self._context.config.dependency_map.enabled:
            try:
                from .network_dependency import init_dependency_manager
                dependency_manager = init_dependency_manager(self._context.config.dependency_map)
                dependency_manager.start_monitoring()
                logger.info("依存関係マップマネージャーを初期化しました")
            except Exception as e:
                logger.error(f"依存関係マップ初期化エラー: {e}")

        # 高度なネットワーク監視マネージャーの初期化
        if self._context.config.advanced_network.enabled:
            try:
                from .advanced_network import init_advanced_network_monitor
                network_monitor = init_advanced_network_monitor(self._context.config.advanced_network)
                network_monitor.start_monitoring()
                logger.info("高度なネットワーク監視マネージャーを初期化しました")
            except Exception as e:
                logger.error(f"高度なネットワーク監視初期化エラー: {e}")

    def start(self) -> int:
        self._refresh_timer.start()
        if self._context.config.automation.logging.enabled:
            self._logging_timer.start()
        if self._context.config.overlay.visible:
            self._overlay_window.show()
        return self.exec()

    def _shutdown_background_services(self) -> None:
        try:
            from .webhook import shutdown_webhook_manager
            shutdown_webhook_manager()
        except Exception as exc:
            logger.debug(f"Webhook shutdown error: {exc}")

    def refresh_metrics(self) -> None:
        current_time = self._current_timestamp_ms()
        metrics_data, cpu_total, memory_percent = self._collect_metric_snapshot()

        if not metrics_data:
            return

        snapshot_payload = {metric.identifier: dict(data) for metric, data in metrics_data}
        self._latest_metrics_payload = snapshot_payload
        self._latest_metrics_timestamp = current_time

        # Store historical data if enabled
        if self._context.config.automation.history.enabled:
            self._context.metric_history.add_sample(current_time, snapshot_payload)

        self._overlay_window.update_metrics(metrics_data)
        self._overlay_window.update_cpu_trend(cpu_total, current_time)
        self._overlay_window.set_last_update(current_time)
        self._update_automation_panels()
        self._last_cpu_percent = cpu_total
        self._last_memory_percent = memory_percent
        self._update_alert_state()

        # AI anomaly detection
        try:
            if self._context.ai_detector.trained:
                metric_values = []
                for metric, data in metrics_data:
                    if isinstance(data, dict):
                        # Extract numeric values from metric data
                        for value in data.values():
                            try:
                                if isinstance(value, (int, float)):
                                    metric_values.append(value)
                                elif isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                                    metric_values.append(float(value))
                            except (ValueError, AttributeError):
                                continue
                if len(metric_values) >= 2:  # Need at least 2 values for detection
                    anomaly_detected = self._context.ai_detector.detect_anomaly([metric_values])
                    if anomaly_detected[0]:
                        self._append_alert_history("AI Anomaly Detected in System Metrics")
        except Exception as e:
            logger.debug(f"AI detection error: {e}")

        # Update system tray metrics
        self._update_tray_metrics()
        self._refresh_cpu_overlay()

    def toggle_overlay(self, visible: Optional[bool] = None) -> None:
        if visible is None:
            visible = not self._overlay_window.isVisible()
        self._overlay_window.setVisible(visible)
        self._context.config.overlay.visible = visible
        self._context.config.save()

    def _configure_overlay(self) -> None:
        self._overlay_window.setWindowOpacity(self._context.config.overlay.opacity)
        self._overlay_window.set_always_on_top(self._context.config.overlay.always_on_top)
        if self._context.config.overlay.visible and not self._overlay_window.isVisible():
            self._overlay_window.show()
        elif not self._context.config.overlay.visible and self._overlay_window.isVisible():
            self._overlay_window.hide()

    def update_refresh_interval(self, interval_ms: int) -> None:
        interval_ms = max(250, interval_ms)
        self._context.config.overlay.refresh_interval_ms = interval_ms
        self._refresh_timer.setInterval(interval_ms)
        self._context.config.save()

    def configure_overlay(self, callback: Callable[[OverlayWindow], None]) -> None:
        callback(self._overlay_window)
        self._context.config.save()

    def configure_logging(self, callback: Optional[Callable[[MoniConfig], None]] = None) -> None:
        if callback is not None:
            callback(self._context.config)
            self._context.config.save()
        self._configure_logging()
        self._update_alert_state()
        self._update_automation_panels()
        self._alert_instance_counts.clear()
        self._last_alert_checks.clear()

    def configure_profile(self, callback: Optional[Callable[[MoniConfig], None]] = None) -> None:
        if callback is not None:
            callback(self._context.config)
            self._context.config.save()
        # Reconfigure everything based on new profile
        self._configure_overlay()
        self._configure_logging()
        self._update_alert_state()
        self._update_automation_panels()
        self._alert_instance_counts.clear()
        self._last_alert_checks.clear()

    def _configure_logging(self) -> None:
        settings = self._context.config.automation.logging
        if settings.enabled:
            interval = max(1000, settings.interval_ms)
            self._logging_timer.setInterval(interval)
            self._logging_timer.start()
        else:
            self._logging_timer.stop()

    def _log_metrics_sample(self) -> None:
        settings = self._context.config.automation.logging
        if not settings.enabled:
            return
        current_time = self._current_timestamp_ms()

        payload: dict[str, dict[str, str]]
        if (
            self._latest_metrics_payload
            and self._latest_metrics_timestamp is not None
            and current_time - self._latest_metrics_timestamp
            <= self._context.config.overlay.refresh_interval_ms
        ):
            payload = {key: dict(value) for key, value in self._latest_metrics_payload.items()}
        else:
            metrics_data, _, _ = self._collect_metric_snapshot()
            if not metrics_data:
                return
            payload = {metric.identifier: dict(data) for metric, data in metrics_data}
            self._latest_metrics_payload = {key: dict(value) for key, value in payload.items()}
            self._latest_metrics_timestamp = current_time
        if not payload:
            return
        log_path = Path(settings.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": current_time,
            "metrics": payload,
        }
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._last_log_timestamp = current_time
        except OSError as exc:
            logger.error(
                "Failed to append metrics log; disabling logging",
                exc_info=True,
                extra={"path": str(log_path)},
            )
            settings.enabled = False
            self._context.config.save()
            self._logging_timer.stop()
            self._show_tray_message(
                "Logging Disabled",
                "Metrics logging was disabled after a filesystem error.",
                QSystemTrayIcon.Warning,
                5000,
            )
        finally:
            self._overlay_window.update_automation_metrics(
                history=self._context.metric_history,
                logging_settings=self._context.config.automation.logging,
                logging_last_timestamp=self._last_log_timestamp,
                latest_metrics_timestamp=self._latest_metrics_timestamp,
            )

    def _collect_metric_snapshot(
        self,
    ) -> Tuple[List[Tuple[Metric, dict[str, str]]], Optional[float], Optional[float]]:
        metrics_data: List[Tuple[Metric, dict[str, str]]] = []
        cpu_total: Optional[float] = None
        memory_percent: Optional[float] = None

        for metric_id in self._context.config.metrics:
            try:
                metric = self._context.registry.get(metric_id)
            except KeyError:
                continue
            try:
                data = metric.collect()

                # 時系列データベースに書き込み
                if HAS_TIMESERIES and self._context.config.timeseries.enabled:
                    try:
                        from .metrics import _write_metric_to_timeseries
                        _write_metric_to_timeseries(metric_id, data)
                    except Exception as e:
                        logger.debug(f"時系列データベース書き込みエラー: {e}")

            except Exception as exc:
                metrics_data.append((metric, self._metric_error_payload(exc)))
                continue
            metrics_data.append((metric, data))
            if metric.identifier == "cpu_usage":
                cpu_total = self._extract_percent(data.get("Total"))
            elif metric.identifier == "memory_usage":
                memory_percent = self._extract_percent(data.get("Utilization"))

        return metrics_data, cpu_total, memory_percent

    @staticmethod
    def _metric_error_payload(exc: Exception | None = None) -> dict[str, str]:
        summary = "Collection failed"
        if exc is not None:
            message = f"{exc.__class__.__name__}: {exc}"
            if len(message) > 120:
                message = message[:117] + "..."
            summary = message
        return {"Error": summary}

    def _get_cached_metric_payload(self, metric_id: str) -> Optional[dict[str, str]]:
        payload = self._latest_metrics_payload.get(metric_id)
        if not payload:
            return None
        return dict(payload)

    def _update_automation_panels(self) -> None:
        now_ts = self._current_timestamp_ms()
        self._overlay_window.set_automation_status(self._context.config)
        self._overlay_window.update_automation_metrics(
            history=self._context.metric_history,
            logging_settings=self._context.config.automation.logging,
            logging_last_timestamp=self._last_log_timestamp,
            latest_metrics_timestamp=self._latest_metrics_timestamp,
            alert_counts=self._alert_instance_counts.copy(),
            last_alert_timestamp=self._last_alert_timestamp,
            current_timestamp=now_ts,
        )

    def clear_alert_history(self) -> None:
        self._alert_history.clear()
        self._alert_instance_counts.clear()
        self._last_alert_checks.clear()
        self._last_alert_timestamp = None
        self._overlay_window.set_alert_history([])
        self._update_automation_panels()

    @staticmethod
    def _current_timestamp_ms() -> int:
        from time import time

        return int(time() * 1000)

    def _update_alert_state(self) -> None:
        alerts = self._evaluate_alerts(self._last_cpu_percent, self._last_memory_percent)
        previous = set(self._active_alerts)
        for alert in alerts:
            if alert not in previous:
                self._append_alert_history(alert)
                self._alert_instance_counts[alert] = self._alert_instance_counts.get(alert, 0) + 1
        self._active_alerts = alerts
        show_banner = (
            self._context.config.automation.alerts.show_overlay_banner
            and self._context.config.automation.alerts.enabled
        )
        self._overlay_window.update_alerts(alerts, show_banner)
        self._overlay_window.set_alert_history(list(self._alert_history))
        current_ts = self._current_timestamp_ms()
        self._overlay_window.update_automation_metrics(
            history=self._context.metric_history,
            logging_settings=self._context.config.automation.logging,
            logging_last_timestamp=self._last_log_timestamp,
            latest_metrics_timestamp=self._latest_metrics_timestamp,
            alert_counts=self._alert_instance_counts.copy(),
            last_alert_timestamp=self._last_alert_timestamp,
            current_timestamp=current_ts,
        )

    def _evaluate_alerts(
        self,
        cpu_percent: Optional[float],
        memory_percent: Optional[float],
    ) -> List[str]:
        settings = self._context.config.automation.alerts
        if not settings.enabled:
            return []
        alerts: List[str] = []
        thresholds = settings.thresholds
        now = self._current_timestamp_ms()
        cooldown_ms = settings.cooldown_seconds * 1000

        if cpu_percent is not None and cpu_percent >= thresholds.cpu_percent:
            last_cpu = self._last_alert_checks.get("cpu")
            if last_cpu is None or now - last_cpu >= cooldown_ms:
                alerts.append(
                    f"CPU {cpu_percent:.1f}% ≥ {thresholds.cpu_percent:.1f}%"
                )
                self._last_alert_checks["cpu"] = now
                self._last_alert_timestamp = now
        if memory_percent is not None and memory_percent >= thresholds.memory_percent:
            last_memory = self._last_alert_checks.get("memory")
            if last_memory is None or now - last_memory >= cooldown_ms:
                alerts.append(
                    f"Memory {memory_percent:.1f}% ≥ {thresholds.memory_percent:.1f}%"
                )
                self._last_alert_checks["memory"] = now
                self._last_alert_timestamp = now
        return alerts

    @staticmethod
    def _extract_percent(raw_value: Optional[str]) -> Optional[float]:
        if raw_value is None:
            return None
        try:
            cleaned = raw_value.strip().rstrip("%")
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _append_alert_history(self, alert: str) -> None:
        timestamp = self._current_timestamp_ms()
        entry = (timestamp, alert)
        self._alert_history.append(entry)
        self._last_alert_timestamp = timestamp

        # Webhook通知を送信
        if self._context.config.webhook.enabled:
            try:
                from .webhook import create_alert_event, send_webhook_notification
                event = create_alert_event(
                    title="System Alert",
                    message=alert,
                    severity="warning",
                    metadata={
                        "timestamp": timestamp,
                        "alert_type": "threshold",
                        "source": "moni_system_monitor"
                    }
                )
                send_webhook_notification(event)
            except Exception as e:
                logger.debug(f"Webhook通知送信エラー: {e}")

    def _setup_system_tray(self) -> None:
        """Setup the enhanced system tray icon and menu with quick actions."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(self._create_tray_icon())
        self._tray_icon.setToolTip("Moni System Monitor")

        # Create enhanced tray menu
        tray_menu = QMenu()
        tray_menu.setSeparatorsCollapsible(False)

        # Toggle overlay action
        self._toggle_overlay_action = QAction("Show/Hide Overlay", self)
        self._toggle_overlay_action.triggered.connect(self._toggle_overlay_from_tray)  # type: ignore[arg-type]
        tray_menu.addAction(self._toggle_overlay_action)

        tray_menu.addSeparator()

        # Quick metrics submenu
        metrics_menu = tray_menu.addMenu("Quick Metrics")
        self._cpu_action = QAction("CPU: --", self)
        self._cpu_action.setEnabled(False)
        metrics_menu.addAction(self._cpu_action)

        self._memory_action = QAction("Memory: --", self)
        self._memory_action.setEnabled(False)
        metrics_menu.addAction(self._memory_action)

        self._gpu_action = QAction("GPU: --", self)
        self._gpu_action.setEnabled(False)
        metrics_menu.addAction(self._gpu_action)

        tray_menu.addSeparator()

        # Quick Actions submenu
        quick_actions_menu = tray_menu.addMenu("Quick Actions")

        # Export metrics action
        export_action = QAction("Export Metrics", self)
        export_action.triggered.connect(self._quick_export_metrics)  # type: ignore[arg-type]
        quick_actions_menu.addAction(export_action)

        # Clear alerts action
        clear_alerts_action = QAction("Clear Alerts", self)
        clear_alerts_action.triggered.connect(self._quick_clear_alerts)  # type: ignore[arg-type]
        quick_actions_menu.addAction(clear_alerts_action)

        # Refresh metrics action
        refresh_action = QAction("Refresh Now", self)
        refresh_action.triggered.connect(self._quick_refresh_metrics)  # type: ignore[arg-type]
        quick_actions_menu.addAction(refresh_action)

        # Process manager action
        process_action = QAction("Process Manager", self)
        process_action.triggered.connect(self._open_process_manager)  # type: ignore[arg-type]
        quick_actions_menu.addAction(process_action)

        # Trend graphs action
        trends_action = QAction("View Trends", self)
        trends_action.triggered.connect(self._open_trends_dialog)  # type: ignore[arg-type]
        quick_actions_menu.addAction(trends_action)

        # CPU Sparkline Overlay toggle
        cpu_overlay_action = QAction("Toggle CPU Overlay", self)
        cpu_overlay_action.triggered.connect(self._toggle_cpu_overlay)  # type: ignore[arg-type]
        quick_actions_menu.addAction(cpu_overlay_action)

        tray_menu.addSeparator()

        # Theme submenu
        self._theme_menu = tray_menu.addMenu("Themes")
        self._create_theme_actions(self._theme_menu)

        tray_menu.addSeparator()

        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._overlay_window.show)  # type: ignore[arg-type]
        tray_menu.addAction(settings_action)

        # About action
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about_dialog)  # type: ignore[arg-type]
        tray_menu.addAction(about_action)

        tray_menu.addSeparator()

        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit)  # type: ignore[arg-type]
        tray_menu.addAction(exit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.show()

        # Connect tray icon activation
        self._tray_icon.activated.connect(self._tray_icon_activated)  # type: ignore[arg-type]

    def _create_tray_icon(self) -> QIcon:
        """Create a simple tray icon."""
        from PySide6.QtGui import QPixmap, QPainter, QColor

        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("transparent"))

        painter = QPainter(pixmap)
        painter.setBrush(QColor("#4a90e2"))
        painter.drawEllipse(4, 4, 24, 24)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(12, 12, 8, 8)
        painter.end()

        return QIcon(pixmap)

    def _toggle_overlay_from_tray(self) -> None:
        """Toggle overlay visibility from tray menu."""
        self.toggle_overlay()

    def _tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_overlay()

    def _update_tray_metrics(self) -> None:
        """Update the metrics displayed in the tray menu."""
        if hasattr(self, '_cpu_action'):
            cpu_text = f"CPU: {self._last_cpu_percent:.1f}%" if self._last_cpu_percent is not None else "CPU: --"
            self._cpu_action.setText(cpu_text)

        if hasattr(self, '_memory_action'):
            memory_text = f"Memory: {self._last_memory_percent:.1f}%" if self._last_memory_percent is not None else "Memory: --"
            self._memory_action.setText(memory_text)

        # Update GPU info if available
        if hasattr(self, '_gpu_action'):
            gpu_payload = self._get_cached_metric_payload("gpu_usage")
            if gpu_payload is None:
                try:
                    gpu_payload = self._context.registry.get("gpu_usage").collect()
                except (KeyError, AttributeError, Exception):
                    gpu_payload = None

            if gpu_payload:
                gpu_summary = gpu_payload.get("Total") or next(iter(gpu_payload.values()), "N/A")
                self._gpu_action.setText(f"GPU: {gpu_summary}")
                self._gpu_action.setEnabled(True)
            else:
                self._gpu_action.setText("GPU: --")
                self._gpu_action.setEnabled(False)

    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts for common actions."""
        def register_shortcut(sequence: str, callback: Callable[[], None]) -> None:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)  # type: ignore[arg-type]
            self._global_shortcuts.append(shortcut)

        # Toggle overlay visibility
        register_shortcut("Ctrl+Shift+M", self.toggle_overlay)

        # Show settings
        register_shortcut("Ctrl+,", self._overlay_window.show)

        # Refresh metrics
        register_shortcut("F5", self._refresh_metrics_manually)

        # Quit application
        register_shortcut("Ctrl+Q", self.quit)

    def _refresh_metrics_manually(self) -> None:
        """Manually refresh metrics (useful for debugging)."""
        self.refresh_metrics()

    # Enhanced tray quick action methods
    def _quick_export_metrics(self) -> None:
        """Quick export metrics from tray menu."""
        from .export import MetricExporter
        from datetime import datetime

        try:
            exporter = MetricExporter(
                self._context.metric_history,
                self._context.registry,
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = self._resolve_export_path(timestamp)

            if exporter.export_metrics(export_path, "json"):
                self._show_tray_message(
                    "Export Complete",
                    f"Metrics exported to {export_path}",
                    QSystemTrayIcon.Information,
                    3000
                )
            else:
                logger.error(
                    "Metric export reported failure",
                    extra={"path": str(export_path)}
                )
                self._show_tray_message(
                    "Export Failed",
                    "Could not export metrics",
                    QSystemTrayIcon.Warning,
                    3000
                )
        except Exception as e:
            logger.error("Metric export raised an exception", exc_info=True)
            self._show_tray_message(
                "Export Error",
                f"Export failed: {str(e)}",
                QSystemTrayIcon.Warning,
                3000
            )

    def _resolve_export_path(self, timestamp: str) -> Path:
        """Determine a safe export file path within the config directory."""

        export_dir = DEFAULT_CONFIG_DIR / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        candidate = export_dir / f"metrics_{timestamp}.json"
        counter = 1
        while candidate.exists():
            candidate = export_dir / f"metrics_{timestamp}_{counter}.json"
            counter += 1
        return candidate

    def _quick_clear_alerts(self) -> None:
        """Quick clear alerts from tray menu."""
        try:
            from .metrics import get_metric, get_alert_manager, HAS_TIMESERIES
            from .enhanced_security import AdvancedInputValidator
            if self._context.config.timeseries.enabled:
                try:
                    from .timeseries_db import init_timeseries_manager, shutdown_timeseries_manager
                    init_timeseries_manager(self._context.config.timeseries)
                    logger.info("時系列データベースマネージャーを初期化しました")
                except Exception as e:
                    logger.error(f"時系列データベース初期化エラー: {e}")
            alert_manager = get_alert_manager()
            alert_count = len(alert_manager.get_active_alerts())
            alert_manager.active_alerts.clear()

            logger.info(
                "Cleared active alerts via tray action",
                extra={"count": alert_count},
            )

            self._show_tray_message(
                "Alerts Cleared",
                f"Cleared {alert_count} active alerts",
                QSystemTrayIcon.Information,
                2000
            )
        except Exception as e:
            logger.error("Failed to clear alerts from tray", exc_info=True)
            self._show_tray_message(
                "Clear Failed",
                f"Could not clear alerts: {str(e)}",
                QSystemTrayIcon.Warning,
                3000
            )

    def _quick_refresh_metrics(self) -> None:
        """Quick refresh metrics from tray menu."""
        try:
            self.refresh_metrics()
        except Exception as exc:
            logger.error("Tray metrics refresh failed", exc_info=True)
            self._show_tray_message(
                "Refresh Failed",
                f"Could not refresh metrics: {str(exc)}",
                QSystemTrayIcon.Warning,
                3000
            )
            return

        self._show_tray_message(
            "Metrics Refreshed",
            "All metrics have been refreshed",
            QSystemTrayIcon.Information,
            1500
        )

    def _open_process_manager(self) -> None:
        """Open process manager dialog from tray menu."""
        try:
            from .ui.process_dialog import ProcessManagerDialog
            dialog = ProcessManagerDialog(self._overlay_window)
            dialog.exec()
        except Exception as e:
            logger.error("Failed to open process manager", exc_info=True)
            self._show_tray_message(
                "Process Manager Error",
                f"Could not open process manager: {str(e)}",
                QSystemTrayIcon.Warning,
                3000
            )

    def _open_trends_dialog(self) -> None:
        """Open trends dialog from tray."""
        try:
            if self._overlay_window:
                self._overlay_window.open_history_graph_dialog()
            else:
                self._show_tray_message(
                    "Trends Unavailable",
                    "Overlay window not available",
                    QSystemTrayIcon.Warning,
                    2000
                )
        except Exception as e:
            logger.error("Failed to open trends dialog", exc_info=True)
            self._show_tray_message(
                "Trends Error",
                f"Could not open trends: {str(e)}",
                QSystemTrayIcon.Warning,
                3000
            )

    def _toggle_cpu_overlay(self) -> None:
        """Toggle CPU sparkline overlay from tray."""
        try:
            if self._cpu_overlay is None:
                self._cpu_overlay = CPUSparklineOverlay()
                self._cpu_overlay.destroyed.connect(self._on_cpu_overlay_destroyed)  # type: ignore[arg-type]

            if self._cpu_overlay.isVisible():
                self._cpu_overlay.hide()
                self._show_tray_message(
                    "CPU Overlay",
                    "CPU sparkline overlay hidden",
                    QSystemTrayIcon.Information,
                    2000
                )
                return

            self._cpu_overlay.show()
            self._refresh_cpu_overlay(force=True)
            self._show_tray_message(
                "CPU Overlay",
                "CPU sparkline overlay shown",
                QSystemTrayIcon.Information,
                2000
            )

        except Exception as e:
            logger.error("Failed to toggle CPU overlay", exc_info=True)
            self._show_tray_message(
                "CPU Overlay Error",
                f"Could not toggle CPU overlay: {str(e)}",
                QSystemTrayIcon.Warning,
                3000
            )

    def _show_tray_message(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.Information,
        duration_ms: int = 3000,
    ) -> None:
        """Unified method for displaying tray notifications."""
        if hasattr(self, '_tray_icon') and self._tray_icon:
            self._tray_icon.showMessage(title, message, icon, duration_ms)

    def _refresh_cpu_overlay(self, force: bool = False) -> None:
        overlay = self._cpu_overlay
        if overlay is None:
            return

        if not force and not overlay.isVisible():
            return

        cpu_percent = self._last_cpu_percent
        if cpu_percent is None:
            try:
                import psutil

                cpu_percent = psutil.cpu_percent(interval=0.0)
            except Exception:
                return

        cpu_history = get_history("cpu_total", max_age_seconds=300)
        sparkline = generate_sparkline(cpu_history, length=12)

        per_core_data: Dict[str, str] = {}
        try:
            per_core_metric = self._context.registry.get("per_core_sparkline")
        except KeyError:
            per_core_metric = None

        if per_core_metric is not None:
            try:
                raw_per_core = per_core_metric.collect()
                if isinstance(raw_per_core, dict):
                    formatted: Dict[str, str] = {}
                    for index, value in enumerate(raw_per_core.values(), start=1):
                        formatted[f"Core {index}"] = value
                    per_core_data = formatted
            except Exception:
                per_core_data = {}

        if not per_core_data and self._latest_metrics_payload:
            cpu_payload = self._latest_metrics_payload.get("cpu_usage", {})
            if isinstance(cpu_payload, dict):
                formatted: Dict[str, str] = {}
                for key, value in cpu_payload.items():
                    if key.lower().startswith("core"):
                        formatted[key.split()[0].title()] = value
                if formatted:
                    per_core_data = formatted

        if cpu_percent is None:
            return

        overlay.update_cpu_data(cpu_percent, sparkline, per_core_data)

    def _on_cpu_overlay_destroyed(self, _obj=None) -> None:
        self._cpu_overlay = None

    def _create_theme_actions(self, theme_menu: QMenu) -> None:
        """Create theme selection actions in tray menu."""

        theme_menu.clear()

        theme_manager = self._context.config.themes
        themes = theme_manager.themes

        if not themes:
            placeholder = QAction("No themes available", self)
            placeholder.setEnabled(False)
            theme_menu.addAction(placeholder)
            return

        current_theme = theme_manager.current_theme

        for theme_key, theme in themes.items():
            action = QAction(theme.name, self)
            action.setCheckable(True)
            action.setChecked(theme_key == current_theme)

            def make_theme_callback(theme_id=theme_key):
                def callback() -> None:
                    self._switch_theme(theme_id)

                return callback

            action.triggered.connect(make_theme_callback())  # type: ignore[arg-type]
            theme_menu.addAction(action)

    def _switch_theme(self, theme_name: str) -> None:
        """Switch to a different theme."""
        try:
            theme_manager = self._context.config.themes
            if theme_manager.set_current_theme(theme_name):
                # Apply theme to overlay window
                if self._overlay_window:
                    self._overlay_window._apply_current_theme()

                self._context.config.save()
                if hasattr(self, "_theme_menu"):
                    self._create_theme_actions(self._theme_menu)

                self._show_tray_message(
                    "Theme Changed",
                    f"Switched to {theme_name} theme",
                    QSystemTrayIcon.Information,
                    2000
                )
            else:
                self._show_tray_message(
                    "Theme Error",
                    f"Could not switch to {theme_name}",
                    QSystemTrayIcon.Warning,
                    3000
                )
        except Exception as e:
            self._show_tray_message(
                "Theme Error",
                f"Theme switch failed: {str(e)}",
                QSystemTrayIcon.Critical,
                3000
            )

    def _show_about_dialog(self) -> None:
        """Show about dialog from tray."""
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import Qt
        try:
            about_text = """
            <h2>Moni System Monitor</h2>
            <p><b>Version:</b> 2.0.0</p>
            <p><b>Description:</b> Advanced system monitoring with real-time metrics, alerts, and customizable overlays.</p>

            <h3>Features:</h3>
            <ul>
                <li>Real-time CPU, memory, and GPU monitoring</li>
                <li>Interactive trend graphs and sparkline visualizations</li>
                <li>Configurable alert thresholds and notifications</li>
                <li>Multiple themes with extensive customization</li>
                <li>Data export in multiple formats</li>
                <li>Plugin architecture for extensibility</li>
                <li>Global hotkey support</li>
                <li>Full multi-monitor compatibility</li>
            </ul>

            <p><b>Built with:</b> Python, PySide6, psutil, matplotlib</p>
            <p><b>Open Source:</b> MIT License</p>
            """

            msg_box = QMessageBox()
            msg_box.setWindowTitle("About Moni")
            msg_box.setTextFormat(Qt.RichText)
            msg_box.setText(about_text)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()

        except Exception as e:
            self._tray_icon.showMessage(
                "About Error",
                f"Could not show about dialog: {str(e)}",
                QSystemTrayIcon.Warning,
                3000
            )
