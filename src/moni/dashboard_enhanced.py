"""
Enhanced Dashboard and Visualization System
Modern, responsive dashboard with real-time updates and advanced features

Features:
- Real-time metric visualization
- Customizable dashboards
- Alert integration
- Multi-panel layouts
- Export functionality
- Dark mode support
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class ChartType(Enum):
    """Types of charts."""
    LINE = "line"
    AREA = "area"
    BAR = "bar"
    GAUGE = "gauge"
    HEATMAP = "heatmap"
    TABLE = "table"
    STAT = "stat"
    PIE = "pie"
    HISTOGRAM = "histogram"


class TimeRange(Enum):
    """Common time ranges."""
    LAST_5_MINUTES = "5m"
    LAST_15_MINUTES = "15m"
    LAST_30_MINUTES = "30m"
    LAST_HOUR = "1h"
    LAST_6_HOURS = "6h"
    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    CUSTOM = "custom"


class ColorScheme(Enum):
    """Color schemes for visualizations."""
    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"
    COLOR_BLIND_FRIENDLY = "color_blind"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ChartConfig:
    """Configuration for a chart."""
    type: ChartType
    title: str
    metric_name: str
    unit: str = ""

    # Display options
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None

    # Styling
    color: str = "#1f77b4"
    legend_position: str = "bottom"  # 'top', 'bottom', 'right', 'left'
    show_grid: bool = True

    # Time range
    time_range: TimeRange = TimeRange.LAST_HOUR
    custom_start: Optional[datetime] = None
    custom_end: Optional[datetime] = None

    # Aggregation
    aggregation: Optional[str] = None  # 'mean', 'sum', 'max', 'min'
    downsample_to: Optional[str] = None


@dataclass
class PanelConfig:
    """Configuration for a dashboard panel."""
    id: str
    title: str
    charts: List[ChartConfig] = field(default_factory=list)

    # Layout
    width: int = 6  # Grid width (1-12)
    height: int = 4  # Grid height in units
    row: int = 0
    col: int = 0

    # Options
    auto_refresh: bool = True
    refresh_interval_seconds: int = 30
    collapsible: bool = True
    expanded: bool = True


@dataclass
class DashboardConfig:
    """Configuration for a complete dashboard."""
    id: str
    name: str
    description: str = ""
    panels: List[PanelConfig] = field(default_factory=list)

    # Display
    color_scheme: ColorScheme = ColorScheme.LIGHT
    time_range: TimeRange = TimeRange.LAST_HOUR
    auto_refresh: bool = True
    refresh_interval_seconds: int = 30

    # Metadata
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""


@dataclass
class DataPoint:
    """Single data point for visualization."""
    timestamp: datetime
    value: float
    label: Optional[str] = None


@dataclass
class DataSeries:
    """Time series data for visualization."""
    name: str
    data: List[DataPoint] = field(default_factory=list)
    color: Optional[str] = None
    unit: str = ""


@dataclass
class AlertIndicator:
    """Alert indicator on dashboard."""
    alert_id: str
    metric_name: str
    severity: str  # 'info', 'warning', 'error', 'critical'
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


# ============================================================================
# Chart Builder
# ============================================================================

class ChartBuilder:
    """Build charts from metrics and configurations."""

    def __init__(self):
        """Initialize chart builder."""
        self.charts: Dict[str, Dict[str, Any]] = {}

    def build_chart(self, config: ChartConfig, data: DataSeries) -> Dict[str, Any]:
        """Build chart from configuration and data."""
        chart = {
            "type": config.type.value,
            "title": config.title,
            "unit": config.unit,
            "data": {
                "labels": [d.timestamp.isoformat() for d in data.data],
                "datasets": [{
                    "label": data.name,
                    "data": [d.value for d in data.data],
                    "color": config.color,
                    "borderColor": config.color,
                    "backgroundColor": f"{config.color}20"  # 12% opacity
                }]
            },
            "options": {
                "responsive": True,
                "scales": {
                    "y": {
                        "min": config.min_value,
                        "max": config.max_value
                    }
                },
                "plugins": {
                    "legend": {
                        "position": config.legend_position
                    }
                },
                "grid": {
                    "display": config.show_grid
                }
            }
        }

        # Add thresholds as horizontal lines
        if config.threshold_warning:
            chart["options"]["plugins"]["threshold_warning"] = {
                "value": config.threshold_warning,
                "color": "#ff9800"  # Orange
            }

        if config.threshold_critical:
            chart["options"]["plugins"]["threshold_critical"] = {
                "value": config.threshold_critical,
                "color": "#f44336"  # Red
            }

        return chart

    def build_gauge_chart(self, config: ChartConfig, current_value: float) -> Dict[str, Any]:
        """Build gauge chart for current value."""
        return {
            "type": "gauge",
            "title": config.title,
            "unit": config.unit,
            "value": current_value,
            "min": config.min_value or 0,
            "max": config.max_value or 100,
            "thresholds": {
                "warning": config.threshold_warning,
                "critical": config.threshold_critical
            },
            "color": self._get_color_for_value(current_value, config)
        }

    def build_stat_chart(self, config: ChartConfig, value: float,
                        previous_value: Optional[float] = None) -> Dict[str, Any]:
        """Build stat chart showing current value and trend."""
        stat_chart = {
            "type": "stat",
            "title": config.title,
            "unit": config.unit,
            "value": value,
            "color": self._get_color_for_value(value, config)
        }

        if previous_value is not None:
            change = value - previous_value
            change_pct = (change / previous_value * 100) if previous_value != 0 else 0
            stat_chart["change"] = change
            stat_chart["change_percent"] = change_pct
            stat_chart["trend"] = "up" if change > 0 else "down" if change < 0 else "flat"

        return stat_chart

    @staticmethod
    def _get_color_for_value(value: float, config: ChartConfig) -> str:
        """Get color based on value and thresholds."""
        if config.threshold_critical and value > config.threshold_critical:
            return "#f44336"  # Red
        if config.threshold_warning and value > config.threshold_warning:
            return "#ff9800"  # Orange
        return "#4caf50"  # Green


# ============================================================================
# Panel Manager
# ============================================================================

class PanelManager:
    """Manage dashboard panels."""

    def __init__(self):
        """Initialize panel manager."""
        self.panels: Dict[str, PanelConfig] = {}

    def add_panel(self, panel: PanelConfig) -> None:
        """Add panel to manager."""
        self.panels[panel.id] = panel

    def remove_panel(self, panel_id: str) -> None:
        """Remove panel by ID."""
        self.panels.pop(panel_id, None)

    def get_panel(self, panel_id: str) -> Optional[PanelConfig]:
        """Get panel by ID."""
        return self.panels.get(panel_id)

    def reorder_panels(self, panel_ids: List[str]) -> None:
        """Reorder panels in dashboard."""
        for idx, panel_id in enumerate(panel_ids):
            if panel_id in self.panels:
                # Calculate grid position
                cols_per_row = 2
                self.panels[panel_id].row = idx // cols_per_row
                self.panels[panel_id].col = (idx % cols_per_row) * 6

    def get_layout(self) -> List[PanelConfig]:
        """Get panels in layout order."""
        return sorted(self.panels.values(),
                     key=lambda p: (p.row, p.col))


# ============================================================================
# Dashboard Manager
# ============================================================================

class DashboardManager:
    """Manage dashboards."""

    def __init__(self, config_dir: Path = None):
        """Initialize dashboard manager."""
        self.config_dir = config_dir or Path.home() / ".moni" / "dashboards"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.dashboards: Dict[str, DashboardConfig] = {}
        self.panel_managers: Dict[str, PanelManager] = {}
        self.chart_builder = ChartBuilder()

    def create_dashboard(self, config: DashboardConfig) -> None:
        """Create new dashboard."""
        self.dashboards[config.id] = config
        self.panel_managers[config.id] = PanelManager()
        self._save_dashboard(config)

    def add_panel(self, dashboard_id: str, panel: PanelConfig) -> None:
        """Add panel to dashboard."""
        if dashboard_id not in self.dashboards:
            raise ValueError(f"Dashboard {dashboard_id} not found")

        self.dashboards[dashboard_id].panels.append(panel)
        self.panel_managers[dashboard_id].add_panel(panel)
        self._save_dashboard(self.dashboards[dashboard_id])

    def remove_panel(self, dashboard_id: str, panel_id: str) -> None:
        """Remove panel from dashboard."""
        if dashboard_id not in self.dashboards:
            raise ValueError(f"Dashboard {dashboard_id} not found")

        config = self.dashboards[dashboard_id]
        config.panels = [p for p in config.panels if p.id != panel_id]
        self.panel_managers[dashboard_id].remove_panel(panel_id)
        self._save_dashboard(config)

    def get_dashboard(self, dashboard_id: str) -> Optional[DashboardConfig]:
        """Get dashboard by ID."""
        return self.dashboards.get(dashboard_id)

    def list_dashboards(self) -> List[DashboardConfig]:
        """List all dashboards."""
        return list(self.dashboards.values())

    def export_dashboard(self, dashboard_id: str, format: str = "json") -> str:
        """Export dashboard configuration."""
        config = self.dashboards.get(dashboard_id)
        if not config:
            raise ValueError(f"Dashboard {dashboard_id} not found")

        if format == "json":
            return json.dumps({
                "id": config.id,
                "name": config.name,
                "description": config.description,
                "color_scheme": config.color_scheme.value,
                "time_range": config.time_range.value,
                "auto_refresh": config.auto_refresh,
                "refresh_interval": config.refresh_interval_seconds,
                "panels": [
                    {
                        "id": p.id,
                        "title": p.title,
                        "width": p.width,
                        "height": p.height
                    } for p in config.panels
                ]
            }, indent=2)

        return ""

    def _save_dashboard(self, config: DashboardConfig) -> None:
        """Save dashboard to file."""
        file_path = self.config_dir / f"{config.id}.json"
        with open(file_path, 'w') as f:
            json.dump({
                "id": config.id,
                "name": config.name,
                "description": config.description,
                "color_scheme": config.color_scheme.value,
                "panels": len(config.panels),
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            }, f, indent=2)


# ============================================================================
# Real-Time Updates
# ============================================================================

class DashboardUpdateNotifier:
    """Notify dashboard clients of updates."""

    def __init__(self):
        """Initialize notifier."""
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, dashboard_id: str, callback: Callable) -> None:
        """Subscribe to dashboard updates."""
        if dashboard_id not in self.subscribers:
            self.subscribers[dashboard_id] = []
        self.subscribers[dashboard_id].append(callback)

    def unsubscribe(self, dashboard_id: str, callback: Callable) -> None:
        """Unsubscribe from dashboard updates."""
        if dashboard_id in self.subscribers:
            self.subscribers[dashboard_id] = [
                c for c in self.subscribers[dashboard_id] if c != callback
            ]

    def notify_update(self, dashboard_id: str, update_data: Dict[str, Any]) -> None:
        """Notify subscribers of dashboard update."""
        if dashboard_id not in self.subscribers:
            return

        for callback in self.subscribers[dashboard_id]:
            try:
                callback(update_data)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {str(e)}")


# Singleton instances
_dashboard_manager: Optional[DashboardManager] = None
_update_notifier: Optional[DashboardUpdateNotifier] = None


def get_dashboard_manager() -> DashboardManager:
    """Get or create dashboard manager singleton."""
    global _dashboard_manager
    if _dashboard_manager is None:
        _dashboard_manager = DashboardManager()
    return _dashboard_manager


def get_update_notifier() -> DashboardUpdateNotifier:
    """Get or create update notifier singleton."""
    global _update_notifier
    if _update_notifier is None:
        _update_notifier = DashboardUpdateNotifier()
    return _update_notifier
