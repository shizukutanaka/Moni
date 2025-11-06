from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices

import matplotlib
matplotlib.use('Qt5Agg')  # Use Qt backend for matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, HourLocator

from ..config import MoniConfig, OverlaySettings, LoggingSettings, AlertSettings, ProfileSettings, ProfileManager, HistorySettings, ThemeSettings, ThemeManager
from ..metrics import Metric, MetricRegistry, MetricHistory, generate_sparkline, get_history
from ..internationalization import i18n_manager


class CPUSparklineOverlay(QWidget):
    """Compact CPU utilization overlay with sparkline visualization."""

    def __init__(self, parent: Optional[QWidget] = None, design_tokens: Optional[DesignTokens] = None):
        super().__init__(parent)
        self.design_tokens = design_tokens or DEFAULT_TOKENS
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(250, 100)

        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.design_tokens.spacing.space_100,
            self.design_tokens.spacing.space_100,
            self.design_tokens.spacing.space_100,
            self.design_tokens.spacing.space_100
        )
        layout.setSpacing(self.design_tokens.spacing.space_050)

        # Title label
        self._title_label = QLabel(i18n_manager.get_text("ui.overlay.title"))
        self._title_label.setStyleSheet(self._get_title_style())
        self._title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title_label)

        # CPU usage label
        self._cpu_label = QLabel(i18n_manager.get_text("ui.overlay.cpu_usage", "CPU: ---%"))
        self._cpu_label.setStyleSheet(self._get_cpu_label_style())
        self._cpu_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._cpu_label)

        # Sparkline label
        self._sparkline_label = QLabel(i18n_manager.get_text("ui.overlay.initializing", "📊 Initializing..."))
        self._sparkline_label.setStyleSheet(self._get_sparkline_style())
        self._sparkline_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._sparkline_label)

        # Per-core display
        self._cores_label = QLabel(i18n_manager.get_text("ui.overlay.cores_initializing", "Cores: Initializing..."))
        self._cores_label.setStyleSheet(self._get_cores_style())
        self._cores_label.setAlignment(Qt.AlignCenter)
        self._cores_label.setWordWrap(True)
        layout.addWidget(self._cores_label)

        # Make window draggable
        self._drag_position = None

    def _get_title_style(self) -> str:
        """Get stylesheet for title label."""
        return f"""
            QLabel {{
                color: {self.design_tokens.colors.text};
                font-weight: bold;
                font-size: {self.design_tokens.typography.font_size_sm}px;
                background-color: {self.design_tokens.colors.surface};
                padding: {self.design_tokens.spacing.space_050}px;
                border-radius: {self.design_tokens.borders.border_radius}px;
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
            }}
        """

    def _get_cpu_label_style(self) -> str:
        """Get stylesheet for CPU usage label."""
        return f"""
            QLabel {{
                color: {self.design_tokens.colors.text};
                font-size: {self.design_tokens.typography.font_size_md}px;
                font-weight: bold;
                background-color: {self.design_tokens.colors.surface};
                padding: {self.design_tokens.spacing.space_075}px;
                border-radius: {self.design_tokens.borders.border_radius}px;
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
            }}
        """

    def _get_sparkline_style(self) -> str:
        """Get stylesheet for sparkline label."""
        return f"""
            QLabel {{
                color: {self.design_tokens.colors.success};
                font-family: {self.design_tokens.typography.font_family_mono};
                font-size: {self.design_tokens.typography.font_size_lg}px;
                background-color: {self.design_tokens.colors.surface};
                padding: {self.design_tokens.spacing.space_075}px;
                border-radius: {self.design_tokens.borders.border_radius}px;
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
            }}
        """

    def _get_cores_style(self) -> str:
        """Get stylesheet for cores label."""
        return f"""
            QLabel {{
                color: {self.design_tokens.colors.text_subtle};
                font-family: {self.design_tokens.typography.font_family_mono};
                font-size: {self.design_tokens.typography.font_size_xs}px;
                background-color: {self.design_tokens.colors.surface};
                padding: {self.design_tokens.spacing.space_050}px;
                border-radius: {self.design_tokens.borders.border_radius}px;
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
            }}
        """

    def update_cpu_data(self, cpu_percent: float, sparkline: str, per_core_data: Dict[str, str]):
        """Update the CPU overlay with new data."""
        # Update main CPU usage
        color = self.design_tokens.colors.success  # Default green
        if cpu_percent > 80:
            color = self.design_tokens.colors.error  # Red for high usage
        elif cpu_percent > 60:
            color = self.design_tokens.colors.warning  # Orange for medium-high
        elif cpu_percent > 40:
            color = self.design_tokens.colors.information  # Blue for medium

        self._cpu_label.setText(f"CPU: {cpu_percent:.1f}%")
        self._cpu_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: {self.design_tokens.typography.font_size_md}px;
                font-weight: bold;
                background-color: {self.design_tokens.colors.surface};
                padding: {self.design_tokens.spacing.space_075}px;
                border-radius: {self.design_tokens.borders.border_radius}px;
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
            }}
        """)

        # Update sparkline
        self._sparkline_label.setText(sparkline)
        self._sparkline_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-family: {self.design_tokens.typography.font_family_mono};
                font-size: {self.design_tokens.typography.font_size_lg}px;
                background-color: {self.design_tokens.colors.surface};
                padding: {self.design_tokens.spacing.space_075}px;
                border-radius: {self.design_tokens.borders.border_radius}px;
                border: {self.design_tokens.borders.border_width}px solid {self.design_tokens.colors.border};
            }}
        """)

        # Update per-core display (show first 4 cores)
        cores_text = ""
        core_count = 0
        for key, value in per_core_data.items():
            if "Core" in key and core_count < 4:
                cores_text += f"{key}: {value}  "
                core_count += 1

        if cores_text:
            self._cores_label.setText(cores_text.strip())

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if event.buttons() == Qt.LeftButton and self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self._drag_position = None

    def contextMenuEvent(self, event):
        """Right-click to close the overlay."""
        self.close()


class MetricListDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        registry: MetricRegistry,
        config: MoniConfig,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n_manager.get_text("ui.dialogs.configure_metrics"))
        self._registry = registry
        self._config = config

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(i18n_manager.get_text("ui.dialogs.select_metrics")))

        self._list_widget = QListWidget(self)
        self._list_widget.setSelectionMode(QListWidget.SingleSelection)
        self._list_widget.setDragEnabled(True)
        self._list_widget.setDefaultDropAction(Qt.MoveAction)
        self._list_widget.setDragDropMode(QListWidget.InternalMove)

        configured_ids = list(config.metrics)
        configured_set = set(configured_ids)
        ordered_metrics: List[Metric] = []

        for metric_id in configured_ids:
            if metric_id in registry:
                ordered_metrics.append(registry.get(metric_id))

        for metric in registry.available_metrics():
            if metric.identifier not in configured_set:
                ordered_metrics.append(metric)

        for metric in ordered_metrics:
            item = QListWidgetItem(metric.name)
            item.setData(Qt.UserRole, metric.identifier)
            item.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsDragEnabled
            )
            item.setCheckState(
                Qt.Checked if metric.identifier in configured_set else Qt.Unchecked
            )
            self._list_widget.addItem(item)

        layout.addWidget(self._list_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def selected_metric_ids(self) -> List[str]:
        selected: List[str] = []
        for index in range(self._list_widget.count()):
            item = self._list_widget.item(index)
            if item.checkState() == Qt.Checked:
                metric_id = item.data(Qt.UserRole)
                if isinstance(metric_id, str):
                    selected.append(metric_id)
        return selected


class OverlaySettingsDialog(QDialog):
    def __init__(self, parent: QWidget, settings: OverlaySettings) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n_manager.get_text("ui.dialogs.overlay_settings"))
        layout = QVBoxLayout(self)

        self._visible_checkbox = QCheckBox(i18n_manager.get_text("ui.dialogs.show_on_launch"), self)
        self._visible_checkbox.setChecked(settings.visible)
        layout.addWidget(self._visible_checkbox)

        self._always_on_top_checkbox = QCheckBox(i18n_manager.get_text("ui.dialogs.always_on_top"), self)
        self._always_on_top_checkbox.setChecked(settings.always_on_top)
        layout.addWidget(self._always_on_top_checkbox)

        opacity_label = QLabel(i18n_manager.get_text("ui.dialogs.opacity"), self)
        layout.addWidget(opacity_label)
        self._opacity_spin = QDoubleSpinBox(self)
        self._opacity_spin.setRange(0.2, 1.0)
        self._opacity_spin.setSingleStep(0.05)
        self._opacity_spin.setValue(settings.opacity)
        layout.addWidget(self._opacity_spin)

        refresh_label = QLabel(i18n_manager.get_text("ui.dialogs.refresh_interval"), self)
        layout.addWidget(refresh_label)
        self._refresh_spin = QSpinBox(self)
        self._refresh_spin.setRange(250, 60000)
        self._refresh_spin.setSingleStep(250)
        self._refresh_spin.setValue(settings.refresh_interval_ms)
        layout.addWidget(self._refresh_spin)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def selected_settings(self, base: OverlaySettings) -> OverlaySettings:
        return base.model_copy(
            update={
                "visible": self._visible_checkbox.isChecked(),
                "always_on_top": self._always_on_top_checkbox.isChecked(),
                "opacity": float(self._opacity_spin.value()),
                "refresh_interval_ms": int(self._refresh_spin.value()),
            }
        )


class LoggingSettingsDialog(QDialog):
    def __init__(self, parent: QWidget, settings: LoggingSettings) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n_manager.get_text("ui.dialogs.logging_automation"))
        self._settings = settings

        layout = QVBoxLayout(self)
        self._enabled_checkbox = QCheckBox(i18n_manager.get_text("ui.dialogs.enable_logging"), self)
        self._enabled_checkbox.setChecked(settings.enabled)
        layout.addWidget(self._enabled_checkbox)

        form = QFormLayout()
        self._interval_spin = QSpinBox(self)
        self._interval_spin.setRange(1000, 600_000)
        self._interval_spin.setSingleStep(1000)
        self._interval_spin.setValue(settings.interval_ms)
        form.addRow(i18n_manager.get_text("ui.dialogs.interval"), self._interval_spin)

        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit(self)
        self._path_edit.setText(str(settings.file_path))
        browse_button = QPushButton(i18n_manager.get_text("ui.dialogs.browse"), self)
        browse_button.clicked.connect(self._browse_file)  # type: ignore[arg-type]
        path_layout.addWidget(self._path_edit)
        path_layout.addWidget(browse_button)
        form.addRow(i18n_manager.get_text("ui.dialogs.log_file"), path_layout)

        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _browse_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select log file",
            str(self._path_edit.text()),
            "JSON Lines (*.jsonl);;All Files (*)",
        )
        if file_path:
            self._path_edit.setText(file_path)

    def selected_settings(self, base: LoggingSettings) -> LoggingSettings:
        return base.model_copy(
            update={
                "enabled": self._enabled_checkbox.isChecked(),
                "interval_ms": int(self._interval_spin.value()),
                "file_path": Path(self._path_edit.text()),
            }
        )


class AlertSettingsDialog(QDialog):
    def __init__(self, parent: QWidget, settings: AlertSettings) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n_manager.get_text("ui.dialogs.threshold_alerts"))

        layout = QVBoxLayout(self)
        self._enabled_checkbox = QCheckBox(i18n_manager.get_text("ui.dialogs.enable_alerts"), self)
        self._enabled_checkbox.setChecked(settings.enabled)
        layout.addWidget(self._enabled_checkbox)

        self._banner_checkbox = QCheckBox(i18n_manager.get_text("ui.dialogs.show_banner"), self)
        self._banner_checkbox.setChecked(settings.show_overlay_banner)
        layout.addWidget(self._banner_checkbox)

        form = QFormLayout()
        self._cpu_spin = QDoubleSpinBox(self)
        self._cpu_spin.setRange(0.0, 100.0)
        self._cpu_spin.setSingleStep(1.0)
        self._cpu_spin.setValue(settings.thresholds.cpu_percent)
        form.addRow(i18n_manager.get_text("ui.dialogs.cpu_threshold"), self._cpu_spin)

        self._memory_spin = QDoubleSpinBox(self)
        self._memory_spin.setRange(0.0, 100.0)
        self._memory_spin.setSingleStep(1.0)
        self._memory_spin.setValue(settings.thresholds.memory_percent)
        form.addRow(i18n_manager.get_text("ui.dialogs.memory_threshold"), self._memory_spin)

        self._cooldown_spin = QSpinBox(self)
        self._cooldown_spin.setRange(5, 3600)
        self._cooldown_spin.setSingleStep(5)
        self._cooldown_spin.setValue(settings.cooldown_seconds)
        form.addRow(i18n_manager.get_text("ui.dialogs.alert_cooldown"), self._cooldown_spin)

        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def selected_settings(self, base: AlertSettings) -> AlertSettings:
        thresholds = base.thresholds.model_copy(
            update={
                "cpu_percent": float(self._cpu_spin.value()),
                "memory_percent": float(self._memory_spin.value()),
            }
        )
        return base.model_copy(
            update={
                "enabled": self._enabled_checkbox.isChecked(),
                "show_overlay_banner": self._banner_checkbox.isChecked(),
                "cooldown_seconds": int(self._cooldown_spin.value()),
                "thresholds": thresholds,
            }
        )


class AlertHistoryDialog(QDialog):
    def __init__(self, parent: QWidget, entries: List[Tuple[int, str]]) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n_manager.get_text("ui.dialogs.alert_history"))
        layout = QVBoxLayout(self)
        if not entries:
            layout.addWidget(QLabel(i18n_manager.get_text("ui.dialogs.no_alerts")))
        else:
            for timestamp_ms, message in reversed(entries):
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                layout.addWidget(QLabel(f"{timestamp} — {message}"))
        button_box = QDialogButtonBox(QDialogButtonBox.Close, self)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class ProfileDialog(QDialog):
    def __init__(self, parent: QWidget, profiles: ProfileManager, registry: MetricRegistry) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Profile")
        self._profiles = profiles
        self._registry = registry

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a monitoring profile:"))

        self._profile_list = QListWidget(self)
        self._profile_list.setSelectionMode(QListWidget.SingleSelection)

        # Add profiles to the list
        for profile_name, profile in profiles.profiles.items():
            item = QListWidgetItem(f"{profile.name} - {profile.description}")
            item.setData(Qt.UserRole, profile_name)
            if profile_name == profiles.current_profile:
                item.setText(f"✓ {item.text()}")
            self._profile_list.addItem(item)

        layout.addWidget(self._profile_list)

        # Profile preview
        preview_layout = QVBoxLayout()
        preview_layout.addWidget(QLabel("Profile Preview:"))
        self._preview_text = QLabel("Select a profile to see details")
        self._preview_text.setWordWrap(True)
        self._preview_text.setStyleSheet("border: 1px solid #ccc; padding: 8px; background-color: #f5f5f5;")
        preview_layout.addWidget(self._preview_text)
        layout.addLayout(preview_layout)

        # Connect selection change
        self._profile_list.itemSelectionChanged.connect(self._update_preview)  # type: ignore[arg-type]

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _update_preview(self) -> None:
        current_item = self._profile_list.currentItem()
        if not current_item:
            return

        profile_name = current_item.data(Qt.UserRole)
        if profile := self._profiles.profiles.get(profile_name):
            metrics_names = [self._registry.get(metric_id).name for metric_id in profile.metrics if metric_id in self._registry]
            preview = f"""
<strong>{profile.name}</strong>
{profile.description}

<strong>Metrics:</strong>
• {', '.join(metrics_names)}

<strong>Settings:</strong>
• Refresh Interval: {profile.overlay.refresh_interval_ms}ms
• Opacity: {profile.overlay.opacity}
• Always on Top: {'Yes' if profile.overlay.always_on_top else 'No'}
• Logging: {'Enabled' if profile.automation.logging.enabled else 'Disabled'}
• Alerts: {'Enabled' if profile.automation.alerts.enabled else 'Disabled'}
            """.strip()
            self._preview_text.setText(preview)

    def selected_profile(self) -> str | None:
        current_item = self._profile_list.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None


class CpuTrendWidget(QWidget):
    """Compact CPU trend panel with sparkline and utilisation summary."""

    def __init__(self, parent: Optional[QWidget] = None, max_age_seconds: int = 300) -> None:
        super().__init__(parent)
        self._max_age_ms = max_age_seconds * 1000
        self._samples: deque[Tuple[int, float]] = deque()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._title_label = QLabel("CPU Trend")
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._title_label)

        self._sparkline_label = QLabel("Collecting data…")
        self._sparkline_label.setObjectName("cpuTrendSparkline")
        self._sparkline_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._sparkline_label.setStyleSheet("font-family: 'Consolas', 'Monaco', monospace;")
        layout.addWidget(self._sparkline_label)

        self._summary_label = QLabel("--")
        self._summary_label.setObjectName("cpuTrendSummary")
        self._summary_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._summary_label)

        self._recent_label = QLabel("--")
        self._recent_label.setObjectName("cpuTrendRecent")
        self._recent_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._recent_label)

    def update_sample(self, timestamp_ms: int, cpu_percent: Optional[float]) -> None:
        if cpu_percent is None:
            return
        self._samples.append((timestamp_ms, cpu_percent))
        cutoff = timestamp_ms - self._max_age_ms
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        self._refresh_view()

    def _refresh_view(self) -> None:
        if len(self._samples) < 3:
            self._sparkline_label.setText("Collecting data…")
            self._summary_label.setText("--")
            self._recent_label.setText("--")
            return

        values = [sample[1] for sample in self._samples]
        sparkline = generate_sparkline(values, length=min(32, len(values)))
        self._sparkline_label.setText(sparkline)

        latest = values[-1]
        peak = max(values)
        average = sum(values) / len(values)
        window_seconds = max(1, (self._samples[-1][0] - self._samples[0][0]) // 1000)

        trend_text = self._calculate_trend(values)
        self._summary_label.setText(
            f"Latest {latest:.1f}% | Peak {peak:.1f}% | Avg {average:.1f}%"
        )
        self._recent_label.setText(
            f"Window {window_seconds}s | Trend {trend_text}"
        )

    @staticmethod
    def _calculate_trend(values: List[float]) -> str:
        if len(values) < 6:
            return "Monitoring"
        third = max(1, len(values) // 3)
        head = values[:third]
        tail = values[-third:]
        head_avg = sum(head) / len(head)
        tail_avg = sum(tail) / len(tail)
        delta = tail_avg - head_avg
        if abs(delta) < 1.0:
            return "Stable"
        if delta > 5.0:
            return "Rising"
        if delta > 0:
            return "Climbing"
        if delta < -5.0:
            return "Falling"
        return "Easing"


class OverlayWindow(QWidget):
    def __init__(
        self,
        context,
        refresh_interval_callback: Callable[[int], None],
        logging_config_callback: Callable[[Callable[[MoniConfig], None] | None], None],
        alert_config_callback: Callable[[Callable[[MoniConfig], None] | None], None],
        profile_config_callback: Callable[[Callable[[MoniConfig], None] | None], None],
        clear_alerts_callback: Callable[[], None],
    ) -> None:  # context: moni.application.MoniContext
        super().__init__()
        self._context = context
        self._refresh_interval_callback = refresh_interval_callback
        self._logging_config_callback = logging_config_callback
        self._alert_config_callback = alert_config_callback
        self._profile_config_callback = profile_config_callback
        self._clear_alerts_callback = clear_alerts_callback
        self._alert_history: List[Tuple[int, str]] = []
        self.setWindowTitle("Moni Overlay")
        self._always_on_top = context.config.overlay.always_on_top
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self._always_on_top)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._build_ui()
        self.setWindowOpacity(context.config.overlay.opacity)
        if not context.config.overlay.visible:
            self.hide()

        # Apply current theme
        self._apply_current_theme()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._title_label = QLabel("System Monitor")
        self._title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title_label)

        self._last_update_label = QLabel("Last update: --")
        self._last_update_label.setAlignment(Qt.AlignCenter)
        self._last_update_label.setObjectName("lastUpdateLabel")
        layout.addWidget(self._last_update_label)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        self._automation_status_label = QLabel("Automation: --")
        self._automation_status_label.setAlignment(Qt.AlignCenter)
        self._automation_status_label.setObjectName("automationStatusLabel")

        self._automation_status_badge = QLabel("•")
        self._automation_status_badge.setObjectName("automationStatusBadge")
        self._automation_status_badge.setAlignment(Qt.AlignCenter)
        self._automation_status_badge.setFixedWidth(18)

        status_row.addWidget(self._automation_status_badge)
        status_row.addWidget(self._automation_status_label)

        layout.addLayout(status_row)

        self._cpu_trend_widget = CpuTrendWidget(self)
        layout.addWidget(self._cpu_trend_widget)

        self._alert_banner = QLabel(self)
        self._alert_banner.setObjectName("alertBanner")
        self._alert_banner.setStyleSheet("background-color: #b00020; color: white; padding: 4px;")
        self._alert_banner.setVisible(False)
        layout.addWidget(self._alert_banner)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Metric", "Value"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree)

        self._automation_metrics_tree = QTreeWidget(self)
        self._automation_metrics_tree.setColumnCount(2)
        self._automation_metrics_tree.setHeaderLabels(["Metric", "Value"])
        self._automation_metrics_tree.setRootIsDecorated(False)
        self._automation_metrics_tree.setAlternatingRowColors(True)
        layout.addWidget(self._automation_metrics_tree)

        controls_layout = QHBoxLayout()
        self._configure_button = QPushButton("Configure")
        self._configure_button.clicked.connect(self.open_metric_dialog)  # type: ignore[arg-type]
        controls_layout.addWidget(self._configure_button)

        self._settings_button = QPushButton("Overlay Settings")
        self._settings_button.clicked.connect(self.open_settings_dialog)  # type: ignore[arg-type]
        controls_layout.addWidget(self._settings_button)

        self._automation_button = QPushButton("Automation")
        self._automation_button.clicked.connect(self.open_logging_dialog)  # type: ignore[arg-type]
        controls_layout.addWidget(self._automation_button)

        self._toggle_logging_button = QPushButton("Enable Logging")
        self._toggle_logging_button.clicked.connect(self.toggle_logging_enabled)  # type: ignore[arg-type]
        controls_layout.addWidget(self._toggle_logging_button)

        self._alerts_button = QPushButton("Alerts")
        self._alerts_button.clicked.connect(self.open_alert_dialog)  # type: ignore[arg-type]
        controls_layout.addWidget(self._alerts_button)

        self._history_button = QPushButton("History")
        self._history_button.clicked.connect(self.open_alert_history)  # type: ignore[arg-type]
        controls_layout.addWidget(self._history_button)

        self._profile_button = QPushButton("Profiles")
        self._profile_button.clicked.connect(self.open_profile_dialog)  # type: ignore[arg-type]
        controls_layout.addWidget(self._profile_button)

        self._history_graph_button = QPushButton("Trends")
        self._history_graph_button.clicked.connect(self.open_history_graph_dialog)  # type: ignore[arg-type]
        controls_layout.addWidget(self._history_graph_button)

        self._theme_button = QPushButton("Theme")
        self._theme_button.clicked.connect(self.open_theme_dialog)  # type: ignore[arg-type]
        controls_layout.addWidget(self._theme_button)

        self._open_logs_button = QPushButton("Open Logs")
        self._open_logs_button.clicked.connect(self.open_log_file)  # type: ignore[arg-type]
        controls_layout.addWidget(self._open_logs_button)

        self._open_log_folder_button = QPushButton("Log Folder")
        self._open_log_folder_button.clicked.connect(self.open_log_folder)  # type: ignore[arg-type]
        controls_layout.addWidget(self._open_log_folder_button)

        self._clear_alerts_button = QPushButton("Clear Alerts")
        self._clear_alerts_button.clicked.connect(self._clear_alerts_callback)  # type: ignore[arg-type]
        controls_layout.addWidget(self._clear_alerts_button)

        self._search_button = QPushButton("Search")
        self._search_button.clicked.connect(self.open_search_dialog)  # type: ignore[arg-type]
        controls_layout.addWidget(self._search_button)

        controls_layout.addStretch(1)

        layout.addLayout(controls_layout)

    def update_metrics(self, metrics_data: Iterable[Tuple[Metric, dict[str, str]]]) -> None:
        self._tree.clear()
        for metric, payload in metrics_data:
            root_item = QTreeWidgetItem([metric.name, ""])
            self._tree.addTopLevelItem(root_item)
            for key, value in payload.items():
                child = QTreeWidgetItem([key, value])
                root_item.addChild(child)
            root_item.setExpanded(True)
        self._tree.resizeColumnToContents(0)
        self._tree.resizeColumnToContents(1)

    def update_cpu_trend(self, cpu_percent: Optional[float], timestamp_ms: Optional[int]) -> None:
        if timestamp_ms is None:
            return
        self._cpu_trend_widget.update_sample(timestamp_ms, cpu_percent)

    def update_automation_metrics(
        self,
        *,
        history: MetricHistory,
        logging_settings: LoggingSettings,
        logging_last_timestamp: Optional[int],
        latest_metrics_timestamp: Optional[int],
        alert_counts: Optional[Dict[str, int]] = None,
        last_alert_timestamp: Optional[int] = None,
        current_timestamp: Optional[int] = None,
    ) -> None:
        self._automation_metrics_tree.clear()

        def _add_row(label: str, value: str) -> None:
            self._automation_metrics_tree.addTopLevelItem(QTreeWidgetItem([label, value]))

        history_samples = history.sample_count()
        history_last = history.last_timestamp()
        history_capacity = getattr(history, "max_entries", None)
        history_first = history.first_timestamp() if hasattr(history, "first_timestamp") else None
        history_retention = history.retention_seconds() if hasattr(history, "retention_seconds") else None
        if history_capacity:
            usage_percent = (history_samples / history_capacity) * 100 if history_capacity else 0.0
            usage_text = f"{history_samples}/{history_capacity} ({usage_percent:.1f}%)"
        else:
            usage_text = str(history_samples)

        _add_row("History samples", str(history_samples))
        _add_row("History usage", usage_text)
        _add_row("History retention", self._format_duration(history_retention))
        _add_row("History first sample", self._format_timestamp(history_first))
        _add_row("Last history sample", self._format_timestamp(history_last))
        _add_row("Last refresh", self._format_timestamp(latest_metrics_timestamp))
        _add_row("Last alert", self._format_timestamp(last_alert_timestamp))
        _add_row(
            "Last alert age",
            self._format_duration(self._calc_age_seconds(current_timestamp, last_alert_timestamp)),
        )

        if logging_settings.enabled:
            interval_text = f"every {logging_settings.interval_ms} ms"
            destination = logging_settings.file_path
            _add_row("Logging", f"enabled ({interval_text})")
            _add_row("Log destination", destination)
            log_path = Path(destination)
            if log_path.exists():
                size_text = self._format_filesize(log_path.stat().st_size)
            else:
                size_text = "--"
            _add_row("Log file size", size_text)
            _add_row("Last log entry", self._format_timestamp(logging_last_timestamp))
            _add_row(
                "Last log age",
                self._format_duration(
                    self._calc_age_seconds(current_timestamp, logging_last_timestamp)
                ),
            )
        else:
            _add_row("Logging", "disabled")

        if alert_counts:
            total_alerts = sum(alert_counts.values())
            _add_row("Alerts triggered", str(total_alerts))
            for alert_label, count in sorted(alert_counts.items(), key=lambda item: item[1], reverse=True):
                _add_row(f"• {alert_label}", f"{count}x")

        badge_details = self._format_status_details(
            logging_enabled=logging_settings.enabled,
            alerts_enabled=self._context.config.automation.alerts.enabled,
            history_enabled=self._context.config.automation.history.enabled,
            last_alert_timestamp=last_alert_timestamp,
            history_usage_text=usage_text,
            history_retention_seconds=history_retention,
            history_first_timestamp=history_first,
            current_timestamp=current_timestamp,
            logging_last_timestamp=logging_last_timestamp,
        )
        _add_row("Automation status", badge_details)

        self._automation_metrics_tree.resizeColumnToContents(0)
        self._automation_metrics_tree.resizeColumnToContents(1)

    def set_last_update(self, timestamp_ms: Optional[int]) -> None:
        self._last_update_label.setText(
            f"Last update: {self._format_timestamp(timestamp_ms)}"
        )

    def set_automation_status(self, config: MoniConfig) -> None:
        logging_settings = config.automation.logging
        alerts_settings = config.automation.alerts
        history_settings = config.automation.history

        if logging_settings.enabled:
            interval = logging_settings.interval_ms
            destination = logging_settings.file_path
            logging_text = f"enabled (every {interval} ms → {destination})"
        else:
            logging_text = "disabled"

        alerts_text = "enabled" if alerts_settings.enabled else "disabled"
        history_text = f"enabled ({history_settings.max_entries} entries)" if history_settings.enabled else "disabled"

        status_lines = [
            f"Logging: {logging_text}",
            f"Alerts: {alerts_text}",
            f"History: {history_text}",
        ]
        self._automation_status_label.setText("\n".join(status_lines))
        self._update_toggle_logging_button(logging_settings.enabled)
        self._update_status_badge(logging_settings.enabled, alerts_settings.enabled, history_settings.enabled)

    @staticmethod
    def _format_timestamp(timestamp_ms: Optional[int]) -> str:
        if timestamp_ms is None:
            return "--"
        try:
            return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, ValueError):
            return "--"

    @staticmethod
    def _format_duration(seconds: Optional[int]) -> str:
        if seconds is None:
            return "--"
        if seconds <= 0:
            return "0s"
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if sec and not parts:
            parts.append(f"{sec}s")
        return " ".join(parts) if parts else "0s"

    @staticmethod
    def _format_filesize(num_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(num_bytes)
        unit_index = 0
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        return f"{size:.1f} {units[unit_index]}"

    def set_always_on_top(self, enabled: bool) -> None:
        self._always_on_top = enabled
        self.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)
        if self.isVisible():
            self.show()

    def is_always_on_top(self) -> bool:
        return self._always_on_top

    def open_metric_dialog(self) -> None:
        dialog = MetricListDialog(self, self._context.registry, self._context.config)
        if dialog.exec() == QDialog.Accepted:
            selected_ids = dialog.selected_metric_ids()
            if selected_ids:
                self._context.config.metrics = selected_ids
                self._context.config.save()

    def open_settings_dialog(self) -> None:
        current_overlay = self._context.config.overlay
        dialog = OverlaySettingsDialog(self, current_overlay)
        if dialog.exec() != QDialog.Accepted:
            return
        updated = dialog.selected_settings(current_overlay)
        self._context.config.overlay = updated
        self._context.config.save()
        self.set_always_on_top(updated.always_on_top)
        self.setWindowOpacity(updated.opacity)
        self._refresh_interval_callback(updated.refresh_interval_ms)
        if updated.visible and not self.isVisible():
            self.show()
        elif not updated.visible and self.isVisible():
            self.hide()

    def open_logging_dialog(self) -> None:
        current_logging = self._context.config.automation.logging
        dialog = LoggingSettingsDialog(self, current_logging)
        if dialog.exec() != QDialog.Accepted:
            return
        updated = dialog.selected_settings(current_logging)

        def apply(config: MoniConfig) -> None:
            config.automation.logging = updated

        self._logging_config_callback(apply)

    def open_alert_dialog(self) -> None:
        current_alerts = self._context.config.automation.alerts
        dialog = AlertSettingsDialog(self, current_alerts)
        if dialog.exec() != QDialog.Accepted:
            return
        updated = dialog.selected_settings(current_alerts)

        def apply(config: MoniConfig) -> None:
            config.automation.alerts = updated

        self._alert_config_callback(apply)

    def open_log_file(self) -> None:
        logging_settings = self._context.config.automation.logging
        if not logging_settings.enabled:
            QMessageBox.information(self, "Automation Logs", "Automation logging is currently disabled.")
            return

        log_path = logging_settings.file_path
        if not log_path.exists():
            QMessageBox.warning(
                self,
                "Automation Logs",
                f"Log file not found at:\n{log_path}"
            )
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path))):
            QMessageBox.warning(
                self,
                "Automation Logs",
                "Failed to open the log file with the associated application."
            )

    def toggle_logging_enabled(self) -> None:
        current_settings = self._context.config.automation.logging
        updated_settings = current_settings.model_copy()
        updated_settings.enabled = not current_settings.enabled

        def apply(config: MoniConfig) -> None:
            config.automation.logging = updated_settings

        self._logging_config_callback(apply)

        if updated_settings.enabled:
            QMessageBox.information(self, "Automation Logging", "Automation logging has been enabled.")
        else:
            QMessageBox.information(self, "Automation Logging", "Automation logging has been disabled.")

    def _update_toggle_logging_button(self, enabled: bool) -> None:
        self._toggle_logging_button.setText("Disable Logging" if enabled else "Enable Logging")

    def open_log_folder(self) -> None:
        logging_settings = self._context.config.automation.logging
        log_path = logging_settings.file_path
        directory = log_path.parent
        if not directory.exists():
            QMessageBox.warning(
                self,
                "Automation Logs",
                f"Log folder not found at:\n{directory}"
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            QMessageBox.warning(
                self,
                "Automation Logs",
                "Failed to open the log folder with the file manager."
            )

    def _update_status_badge(self, logging_enabled: bool, alerts_enabled: bool, history_enabled: bool) -> None:
        enabled_flags = {
            "Logging": logging_enabled,
            "Alerts": alerts_enabled,
            "History": history_enabled,
        }

        if all(enabled_flags.values()):
            color = "#2e7d32"  # green
            tooltip = "Automation features: logging, alerts, and history are enabled."
        elif any(enabled_flags.values()):
            color = "#f9a825"  # amber
            disabled = [name for name, enabled in enabled_flags.items() if not enabled]
            enabled = [name for name, enabled in enabled_flags.items() if enabled]
            tooltip = "Enabled: " + ", ".join(enabled) if enabled else "Enabled: none"
            if disabled:
                tooltip += "\nDisabled: " + ", ".join(disabled)
        else:
            color = "#9e9e9e"  # grey
            tooltip = "Automation features are currently disabled."

        self._automation_status_badge.setStyleSheet(f"color: {color}; font-size: 18px;")
        self._automation_status_badge.setToolTip(tooltip)

    def _format_status_details(
        self,
        *,
        logging_enabled: bool,
        alerts_enabled: bool,
        history_enabled: bool,
        last_alert_timestamp: Optional[int],
        history_usage_text: str,
        history_retention_seconds: Optional[int],
        history_first_timestamp: Optional[int],
        current_timestamp: Optional[int],
        logging_last_timestamp: Optional[int],
    ) -> str:
        status_bits = []
        if logging_enabled:
            status_bits.append("Logging enabled")
        else:
            status_bits.append("Logging disabled")

        if alerts_enabled:
            status_bits.append("Alerts enabled")
        else:
            status_bits.append("Alerts disabled")

        if history_enabled:
            status_bits.append(f"History enabled ({history_usage_text})")
        else:
            status_bits.append("History disabled")

        if last_alert_timestamp is not None:
            status_bits.append(
                f"Last alert at {self._format_timestamp(last_alert_timestamp)}"
            )
        else:
            status_bits.append("No alerts recorded")

        if history_retention_seconds is not None:
            status_bits.append(
                f"Retention {self._format_duration(history_retention_seconds)}"
            )
        if history_first_timestamp is not None:
            status_bits.append(
                f"First sample {self._format_timestamp(history_first_timestamp)}"
            )

        if logging_enabled and logging_last_timestamp is not None:
            status_bits.append(
                "Log age "
                + self._format_duration(
                    self._calc_age_seconds(current_timestamp, logging_last_timestamp)
                )
            )
        if last_alert_timestamp is not None:
            status_bits.append(
                "Alert age "
                + self._format_duration(
                    self._calc_age_seconds(current_timestamp, last_alert_timestamp)
                )
            )

        return " | ".join(status_bits)

    @staticmethod
    def _calc_age_seconds(
        current_timestamp: Optional[int],
        event_timestamp: Optional[int],
    ) -> Optional[int]:
        if current_timestamp is None or event_timestamp is None:
            return None
        delta_ms = current_timestamp - event_timestamp
        if delta_ms < 0:
            return None
        return delta_ms // 1000

    def update_alerts(self, alerts: List[str], show_banner: bool) -> None:
        if not alerts or not show_banner:
            self._alert_banner.setVisible(False)
            self._alert_banner.setText("")
            return
        message = " | ".join(alerts)
        self._alert_banner.setText(f"Alerts: {message}")
        self._alert_banner.setVisible(True)

    def set_alert_history(self, entries: List[Tuple[int, str]]) -> None:
        self._alert_history = entries

    def open_alert_history(self) -> None:
        dialog = AlertHistoryDialog(self, self._alert_history)
        dialog.exec()

    def open_history_graph_dialog(self) -> None:
        # Pass the actual history data from the application
        dialog = HistoryGraphDialog(
            self,
            self._context.metric_history,
            self._context.registry,
            default_metric_ids=list(self._context.config.metrics),
        )
        dialog.exec()

    def open_theme_dialog(self) -> None:
        dialog = ThemeDialog(self, self._context.config.themes)
        if dialog.exec() == QDialog.Accepted:
            if theme_name := dialog.selected_theme():
                if self._context.config.apply_theme(theme_name):
                    self._context.config.save()
                    # Apply the theme to the UI
                    self._apply_current_theme()

    def _apply_current_theme(self) -> None:
        """Apply the current theme to the overlay window."""
        if theme := self._context.config.themes.get_current_theme():
            # Apply colors to the main window
            self.setStyleSheet(f"""
                QTreeWidget {{
                    background-color: {theme.colors.surface};
                    color: {theme.colors.text};
                    border: 1px solid {theme.colors.border};
                    border-radius: {theme.border_radius}px;
                }}
                QTreeWidget::item {{
                    padding: 2px;
                    border-bottom: 1px solid {theme.colors.border};
                }}
                QTreeWidget::item:selected {{
                    background-color: {theme.colors.primary};
                    color: white;
                }}
                QLabel {{
                    color: {theme.colors.text};
                }}
                QPushButton {{
                    background-color: {theme.colors.surface};
                    color: {theme.colors.text};
                    border: 1px solid {theme.colors.border};
                    border-radius: {theme.border_radius}px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme.colors.primary};
                    color: white;
                }}
                QPushButton#alertBanner {{
                    background-color: {theme.colors.error};
                    color: white;
                    border: none;
                    border-radius: {theme.border_radius}px;
                }}
                QDialog {{
                    background-color: {theme.colors.background};
                }}
            """)

            # Set font
            font = self.font()
            font.setFamily(theme.font_family)
            font.setPointSize(theme.font_size)
            self.setFont(font)

    def open_profile_dialog(self) -> None:
        dialog = ProfileDialog(self, self._context.config.profiles, self._context.registry)
        if dialog.exec() == QDialog.Accepted:
            if profile_name := dialog.selected_profile():
                if self._context.config.apply_profile(profile_name):

                    def apply(config: MoniConfig) -> None:
                        pass  # Profile already applied in apply_profile

                    self._profile_config_callback(apply)
                    self._context.config.save()
                    # Update UI to reflect new profile settings
                    self.set_always_on_top(self._context.config.overlay.always_on_top)
                    self.setWindowOpacity(self._context.config.overlay.opacity)
                    self._refresh_interval_callback(self._context.config.overlay.refresh_interval_ms)
                    if self._context.config.overlay.visible and not self.isVisible():
                        self.show()
                    elif not self._context.config.overlay.visible and self.isVisible():
                        self.hide()


    def open_search_dialog(self) -> None:
        """Open search dialog for YouTube, academic papers, and web search."""
        try:
            from .search_dialog import open_search_dialog as open_search
            open_search(self)
        except ImportError:
            QMessageBox.warning(
                self,
                "Search Unavailable",
                "Search functionality is not available.\nPlease check if search components are properly installed."
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Search Error",
                f"Failed to open search dialog:\n{str(e)}"
            )


class ThemeDialog(QDialog):
    def __init__(self, parent: QWidget, themes: ThemeManager) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Theme")
        self.setMinimumSize(600, 400)
        self._themes = themes

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a theme for the application:"))

        # Theme selection
        self._theme_list = QListWidget(self)
        self._theme_list.setSelectionMode(QListWidget.SingleSelection)
        self._theme_list.setMaximumHeight(200)

        # Add themes to the list
        for theme_name, theme in themes.themes.items():
            item = QListWidgetItem(f"{theme.name} - {theme.description}")
            item.setData(Qt.UserRole, theme_name)
            if theme_name == themes.current_theme:
                item.setText(f"✓ {item.text()}")
            self._theme_list.addItem(item)

        layout.addWidget(self._theme_list)

        # Theme preview
        preview_layout = QVBoxLayout()
        preview_layout.addWidget(QLabel("Theme Preview:"))
        self._preview_widget = self._create_theme_preview(themes.get_current_theme())
        preview_layout.addWidget(self._preview_widget)
        layout.addLayout(preview_layout)

        # Connect selection change
        self._theme_list.itemSelectionChanged.connect(self._update_preview)  # type: ignore[arg-type]

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        apply_button = QPushButton("Apply Theme", self)
        apply_button.clicked.connect(self.accept)  # type: ignore[arg-type]
        button_layout.addWidget(apply_button)

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.reject)  # type: ignore[arg-type]
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _create_theme_preview(self, theme: ThemeSettings | None) -> QWidget:
        """Create a preview widget showing the theme colors."""
        if not theme:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.addWidget(QLabel("No theme selected"))
            return widget

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Theme name and description
        name_label = QLabel(f"<b>{theme.name}</b>")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        desc_label = QLabel(theme.description)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet(f"color: {theme.colors.text_secondary};")
        layout.addWidget(desc_label)

        # Color palette preview
        colors_layout = QHBoxLayout()

        colors = [
            ("Background", theme.colors.background),
            ("Surface", theme.colors.surface),
            ("Primary", theme.colors.primary),
            ("Text", theme.colors.text),
            ("Success", theme.colors.success),
            ("Warning", theme.colors.warning),
            ("Error", theme.colors.error),
        ]

        for color_name, color_value in colors:
            color_widget = QWidget()
            color_widget.setMinimumSize(60, 40)
            color_widget.setStyleSheet(f"""
                background-color: {color_value};
                border: 1px solid {theme.colors.border};
                border-radius: {theme.border_radius}px;
            """)
            color_widget.setToolTip(f"{color_name}: {color_value}")

            color_layout = QVBoxLayout(color_widget)
            color_name_label = QLabel(color_name)
            color_name_label.setAlignment(Qt.AlignCenter)
            color_name_label.setStyleSheet(f"color: {theme.colors.text}; font-size: 8px;")
            color_layout.addWidget(color_name_label)

            colors_layout.addWidget(color_widget)

        layout.addLayout(colors_layout)

        # Font preview
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font Preview:"))
        font_label = QLabel("AaBbCc 123")
        font_label.setStyleSheet(f"""
            font-family: {theme.font_family};
            font-size: {theme.font_size + 4}px;
            color: {theme.colors.text};
        """)
        font_layout.addWidget(font_label)
        font_layout.addStretch(1)
        layout.addLayout(font_layout)

        return widget

    def _update_preview(self) -> None:
        """Update the theme preview when selection changes."""
        current_item = self._theme_list.currentItem()
        if not current_item:
            return

        theme_name = current_item.data(Qt.UserRole)
        if theme := self._themes.themes.get(theme_name):
            # Remove old preview and create new one
            old_widget = self._preview_widget
            self._preview_widget = self._create_theme_preview(theme)
            old_widget.setParent(None)
            old_widget.deleteLater()

            # Update the layout
            preview_layout = self.layout()
            if preview_layout:
                # Find the preview layout and replace the widget
                for i in range(preview_layout.count()):
                    item = preview_layout.itemAt(i)
                    if item and item.widget() == old_widget:
                        preview_layout.removeItem(item)
                        preview_layout.insertWidget(i, self._preview_widget)
                        break

    def selected_theme(self) -> str | None:
        current_item = self._theme_list.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None


class HistoryGraphDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        history: MetricHistory,
        registry: MetricRegistry,
        default_metric_ids: Optional[List[str]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Historical Trends")
        self.setMinimumSize(800, 600)
        self._history = history
        self._registry = registry
        self._default_metric_ids = default_metric_ids or []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select metrics to display in the graph:"))

        # Metric selection
        self._metric_list = QListWidget(self)
        self._metric_list.setSelectionMode(QListWidget.MultiSelection)
        self._metric_list.setMaximumHeight(120)

        for metric in registry.available_metrics():
            item = QListWidgetItem(metric.name)
            item.setData(Qt.UserRole, metric.identifier)
            self._metric_list.addItem(item)

        if self._default_metric_ids:
            for index in range(self._metric_list.count()):
                item = self._metric_list.item(index)
                metric_id = item.data(Qt.UserRole)
                if isinstance(metric_id, str) and metric_id in self._default_metric_ids:
                    item.setSelected(True)

        if not self._metric_list.selectedItems() and self._metric_list.count():
            self._metric_list.item(0).setSelected(True)

        layout.addWidget(self._metric_list)

        # Time range selection
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Time range:"))

        self._time_range_combo = QComboBox(self)
        self._time_range_combo.addItems([
            "Last 10 minutes",
            "Last 30 minutes",
            "Last 1 hour",
            "Last 6 hours",
            "Last 24 hours",
            "All data"
        ])
        self._time_range_combo.setCurrentIndex(2)  # Default to 1 hour
        range_layout.addWidget(self._time_range_combo)

        # Graph type selection
        range_layout.addWidget(QLabel("Graph type:"))
        self._graph_type_combo = QComboBox(self)
        self._graph_type_combo.addItems([
            "Line Chart",
            "Area Chart",
            "Bar Chart"
        ])
        self._graph_type_combo.setCurrentIndex(0)
        range_layout.addWidget(self._graph_type_combo)

        layout.addLayout(range_layout)

        # Buttons
        button_layout = QHBoxLayout()

        export_button = QPushButton("Export Data", self)
        export_button.clicked.connect(self._export_data)  # type: ignore[arg-type]
        button_layout.addWidget(export_button)

        refresh_button = QPushButton("Refresh Graph", self)
        refresh_button.clicked.connect(self._refresh_graph)  # type: ignore[arg-type]
        button_layout.addWidget(refresh_button)

        button_layout.addStretch(1)

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.reject)  # type: ignore[arg-type]
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self._summary_label = QLabel("Select metrics to view statistical summary.")
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet("margin-top: 8px; color: #555;")
        layout.addWidget(self._summary_label)

        # Graph area with matplotlib
        self._figure = Figure(figsize=(8, 5), dpi=100)
        self._canvas = FigureCanvas(self._figure)
        layout.addWidget(self._canvas)

        # Store the current axes
        self._axes = self._figure.add_subplot(111)

        # Initialize with empty plot
        self._refresh_graph()

    def _refresh_graph(self) -> None:
        selected_metrics = []
        for item in self._metric_list.selectedItems():
            metric_id = item.data(Qt.UserRole)
            if isinstance(metric_id, str):
                selected_metrics.append(metric_id)

        if not selected_metrics:
            self._show_no_data_message("Please select at least one metric to display.")
            return

        # Calculate time range
        current_time = int(datetime.now().timestamp() * 1000)
        time_range_index = self._time_range_combo.currentIndex()

        if time_range_index == 0:  # 10 minutes
            start_time = current_time - (10 * 60 * 1000)
        elif time_range_index == 1:  # 30 minutes
            start_time = current_time - (30 * 60 * 1000)
        elif time_range_index == 2:  # 1 hour
            start_time = current_time - (60 * 60 * 1000)
        elif time_range_index == 3:  # 6 hours
            start_time = current_time - (6 * 60 * 60 * 1000)
        elif time_range_index == 4:  # 24 hours
            start_time = current_time - (24 * 60 * 60 * 1000)
        else:  # All data
            start_time = None

        # Get historical data
        data = self._history.get_data_range(start_time, current_time)

        if not data:
            self._show_no_data_message("No historical data available for the selected time range.")
            return

        # Filter for selected metrics
        filtered_data = {k: v for k, v in data.items() if k in selected_metrics}

        if not filtered_data:
            self._show_no_data_message("No data available for the selected metrics in the chosen time range.")
            self._summary_label.setText("No data available for the selected metrics in the chosen time range.")
            return

        # Clear previous plot
        self._axes.clear()

        # Plot the data
        summary_stats = self._plot_data(filtered_data, start_time, current_time)
        if summary_stats is None:
            message = "No numeric data available for the selected metrics."
            self._show_no_data_message(message)
            self._summary_label.setText(message)
            return

        # Update the canvas
        self._canvas.draw()

        summary_lines = []
        for metric_name, stats in summary_stats.items():
            summary_lines.append(
                f"{metric_name}: min {stats['min']:.1f} / avg {stats['avg']:.1f} / max {stats['max']:.1f}"
            )
        self._summary_label.setText("\n".join(summary_lines))

    def _plot_data(
        self,
        data: Dict[str, Dict[str, List]],
        start_time: Optional[int],
        end_time: int,
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """Plot the historical data using matplotlib."""
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
        plotted_any = False
        last_dates: List[datetime] = []
        summary_stats: Dict[str, Dict[str, float]] = {}

        def _coerce_numeric(value: object) -> Optional[float]:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.endswith('%'):
                    stripped = stripped[:-1]
                try:
                    return float(stripped)
                except ValueError:
                    return None
            return None

        for i, (metric_id, metric_data) in enumerate(data.items()):
            try:
                metric = self._registry.get(metric_id)
                timestamps = metric_data["timestamps"]
                values_list = metric_data["values"]

                if not timestamps or not values_list:
                    continue

                # Convert timestamps to datetime objects
                dates = [datetime.fromtimestamp(ts / 1000) for ts in timestamps]

                paired_dates: List[datetime] = []
                numeric_values: List[float] = []
                for ts, values in zip(dates, values_list):
                    numeric = None
                    if isinstance(values, dict):
                        for raw_value in values.values():
                            numeric = _coerce_numeric(raw_value)
                            if numeric is not None:
                                break
                    else:
                        numeric = _coerce_numeric(values)

                    if numeric is not None:
                        paired_dates.append(ts)
                        numeric_values.append(numeric)

                if not numeric_values or not paired_dates:
                    continue

                color = colors[i % len(colors)]

                # Plot based on selected graph type
                graph_type = self._graph_type_combo.currentIndex()

                if graph_type == 0:  # Line Chart
                    self._axes.plot(paired_dates, numeric_values, 'o-', color=color, linewidth=2, markersize=4,
                                  label=metric.name)
                elif graph_type == 1:  # Area Chart
                    self._axes.fill_between(paired_dates, numeric_values, alpha=0.3, color=color)
                    self._axes.plot(paired_dates, numeric_values, 'o-', color=color, linewidth=2, markersize=4,
                                  label=metric.name)
                elif graph_type == 2:  # Bar Chart
                    bar_width = 0.8 if len(paired_dates) == 1 else 0.02
                    self._axes.bar(paired_dates, numeric_values, width=bar_width, alpha=0.7, color=color,
                                label=metric.name)

                plotted_any = True
                last_dates = paired_dates

                summary_stats[metric.name] = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "avg": fmean(numeric_values),
                }

            except KeyError:
                continue

        if not plotted_any:
            return None

        # Format the plot
        self._axes.set_title("System Metrics Historical Trends", fontsize=14, fontweight='bold')
        self._axes.set_xlabel("Time", fontsize=12)
        self._axes.set_ylabel("Value", fontsize=12)
        self._axes.legend(loc='upper right')
        self._axes.grid(True, alpha=0.3)

        # Format x-axis for better readability
        if last_dates:
            self._axes.xaxis.set_major_formatter(DateFormatter('%H:%M'))
            self._axes.xaxis.set_major_locator(HourLocator(interval=1))

            # Rotate x-axis labels if too many points
            if len(last_dates) > 10:
                plt.setp(self._axes.xaxis.get_majorticklabels(), rotation=45)

        return summary_stats

    def _show_no_data_message(self, message: str) -> None:
        """Display a message when no data is available."""
        self._axes.clear()
        self._axes.text(0.5, 0.5, message,
                       horizontalalignment='center', verticalalignment='center',
                       transform=self._axes.transAxes, fontsize=12)
        self._axes.set_title("No Data Available", fontsize=14, fontweight='bold')
        self._canvas.draw()
        self._summary_label.setText(message)

    def _export_data(self) -> None:
        """Export historical data to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Historical Data",
            str(Path.home() / "moni_history_export.json"),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            destination = Path(file_path)
            try:
                selected_metrics = [
                    item.data(Qt.UserRole)
                    for item in self._metric_list.selectedItems()
                    if isinstance(item.data(Qt.UserRole), str)
                ]
                metric_filter = selected_metrics or None
                self._history.export_to_json(destination, metric_filter=metric_filter)
                self._show_no_data_message(f"Data exported successfully to:\n{destination}")
            except Exception as e:
                self._show_no_data_message(f"Export failed: {str(e)}")
