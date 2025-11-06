"""Multi-monitor support for overlay positioning and management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import json
from pathlib import Path
import logging

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QRect, QPoint, QSize
from PySide6.QtGui import QScreen


logger = logging.getLogger(__name__)


class MonitorPosition(Enum):
    """Predefined monitor positioning options."""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    TOP_CENTER = "top_center"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"
    CENTER_LEFT = "center_left"
    CENTER_RIGHT = "center_right"
    CENTER = "center"
    CUSTOM = "custom"


@dataclass
class MonitorInfo:
    """Information about a display monitor."""
    index: int
    name: str
    geometry: QRect
    available_geometry: QRect
    device_pixel_ratio: float
    refresh_rate: float
    is_primary: bool
    orientation: int
    physical_size: QSize


@dataclass
class OverlayPlacement:
    """Configuration for overlay placement on a specific monitor."""
    monitor_index: int
    position: MonitorPosition
    custom_x: Optional[int] = None
    custom_y: Optional[int] = None
    offset_x: int = 0
    offset_y: int = 0
    enabled: bool = True


class MultiMonitorManager:
    """Manager for multi-monitor overlay support."""

    def __init__(self):
        self.monitors: List[MonitorInfo] = []
        self.overlay_placements: Dict[int, OverlayPlacement] = {}
        self.config_file: Optional[Path] = None
        self._refresh_monitors()

    @staticmethod
    def _clamp_to_geometry(geometry: QRect, widget_size: QSize, x: int, y: int) -> QPoint:
        """Clamp coordinates so the widget stays within the given geometry."""
        left = geometry.left()
        top = geometry.top()
        max_x = left + max(0, geometry.width() - widget_size.width())
        max_y = top + max(0, geometry.height() - widget_size.height())
        clamped_x = max(left, min(x, max_x))
        clamped_y = max(top, min(y, max_y))
        return QPoint(clamped_x, clamped_y)

    def _refresh_monitors(self):
        """Refresh the list of available monitors."""
        self.monitors.clear()
        app = QApplication.instance()
        if not app:
            return

        screens = app.screens()
        primary_screen = app.primaryScreen()

        for i, screen in enumerate(screens):
            monitor_info = MonitorInfo(
                index=i,
                name=screen.name(),
                geometry=screen.geometry(),
                available_geometry=screen.availableGeometry(),
                device_pixel_ratio=screen.devicePixelRatio(),
                refresh_rate=screen.refreshRate(),
                is_primary=(screen == primary_screen),
                orientation=screen.orientation().value if hasattr(screen.orientation(), 'value') else 0,
                physical_size=screen.physicalSize().toSize() if hasattr(screen, 'physicalSize') else QSize(0, 0)
            )
            self.monitors.append(monitor_info)

        self._normalize_overlay_placements()

    def _normalize_overlay_placements(self):
        """Align overlay placements with current monitor configuration."""
        if not self.monitors:
            return

        valid_indices = {monitor.index for monitor in self.monitors}
        normalized: Dict[int, OverlayPlacement] = {}

        for key, placement in list(self.overlay_placements.items()):
            if placement.monitor_index not in valid_indices:
                continue

            monitor_index = placement.monitor_index

            if placement.position != MonitorPosition.CUSTOM:
                placement.custom_x = None
                placement.custom_y = None
            elif placement.custom_x is None or placement.custom_y is None:
                placement.position = MonitorPosition.CENTER
                placement.custom_x = None
                placement.custom_y = None

            normalized[monitor_index] = placement

        self.overlay_placements = normalized

        if not any(placement.enabled for placement in self.overlay_placements.values()):
            primary_monitor = self.get_primary_monitor()
                self.overlay_placements[primary_monitor.index].enabled = True

    def get_monitors(self) -> List[MonitorInfo]:
        """Get list of all available monitors."""
        self._refresh_monitors()
        self.create_default_placements()

    def create_default_placements(self):
        """Create default overlay placements for all monitors."""
        self._refresh_monitors()

        for i, monitor in enumerate(self.monitors):
            if i not in self.overlay_placements:
                # Primary monitor gets center position, others get top-right
                position = MonitorPosition.CENTER if monitor.is_primary else MonitorPosition.TOP_RIGHT
                placement = OverlayPlacement(
                    monitor_index=i,
                    position=position,
                    enabled=monitor.is_primary
                )
                self.overlay_placements[i] = placement

        self._ensure_primary_enabled()
figuration changed since last lookup
        self._refresh_monitors()
        if 0 <= index < len(self.monitors):
            return self.monitors[index]

        return None
{{ ... }}

    def calculate_position(self, monitor_index: int, position: MonitorPosition,
                          widget_size: QSize, offset_x: int = 0, offset_y: int = 0) -> Optional[QPoint]:
        """Calculate absolute position for a widget on a specific monitor."""
        monitor = self.get_monitor_by_index(monitor_index)
        if not monitor:
            return None

        geometry = monitor.available_geometry
        widget_width = widget_size.width()
        widget_height = widget_size.height()
        left = geometry.left()
        top = geometry.top()
        width = geometry.width()
        height = geometry.height()

        # Calculate base position
        if position == MonitorPosition.TOP_LEFT:
            x = left
            y = top
        elif position == MonitorPosition.TOP_RIGHT:
            x = left + max(0, width - widget_width)
            y = top
        elif position == MonitorPosition.TOP_CENTER:
            x = left + (width - widget_width) // 2
            y = top
        elif position == MonitorPosition.BOTTOM_LEFT:
            x = left
            y = top + max(0, height - widget_height)
        elif position == MonitorPosition.BOTTOM_RIGHT:
            x = left + max(0, width - widget_width)
            y = top + max(0, height - widget_height)
        elif position == MonitorPosition.BOTTOM_CENTER:
            x = left + (width - widget_width) // 2
            y = top + max(0, height - widget_height)
        elif position == MonitorPosition.CENTER_LEFT:
            x = left
            y = top + (height - widget_height) // 2
        elif position == MonitorPosition.CENTER_RIGHT:
            x = left + max(0, width - widget_width)
            y = top + (height - widget_height) // 2
        elif position == MonitorPosition.CENTER:
            x = left + (width - widget_width) // 2
            y = top + (height - widget_height) // 2
        else:  # CUSTOM - will be handled separately
            x = left
            y = top

        # Apply offsets
        x += offset_x
        y += offset_y

        return self._clamp_to_geometry(geometry, widget_size, x, y)

    def set_overlay_placement(self, monitor_index: int, placement: OverlayPlacement):
        """Set overlay placement configuration for a monitor."""
        self.overlay_placements[monitor_index] = placement

    def get_overlay_placement(self, monitor_index: int) -> Optional[OverlayPlacement]:
        """Get overlay placement configuration for a monitor."""
        return self.overlay_placements.get(monitor_index)

    def position_overlay(self, widget: QWidget, monitor_index: int) -> bool:
        """Position an overlay widget on the specified monitor."""
        placement = self.get_overlay_placement(monitor_index)
        if not placement or not placement.enabled:
            return False

        widget_size = widget.size()

        if placement.position == MonitorPosition.CUSTOM and placement.custom_x is not None and placement.custom_y is not None:
            # Use custom position
            monitor = self.get_monitor_by_index(monitor_index)
            if monitor:
                geometry = monitor.available_geometry
                x = geometry.left() + placement.custom_x + placement.offset_x
                y = geometry.top() + placement.custom_y + placement.offset_y
                clamped = self._clamp_to_geometry(geometry, widget_size, x, y)
                widget.move(clamped)
                return True
        else:
            # Use predefined position
            position = self.calculate_position(
                monitor_index,
                placement.position,
                widget_size,
                placement.offset_x,
                placement.offset_y
            )
            if position:
                widget.move(position)
                return True

        return False

    def get_monitor_at_point(self, point: QPoint) -> Optional[MonitorInfo]:
        """Get the monitor that contains the given point."""
        for monitor in self.monitors:
            if monitor.geometry.contains(point):
                return monitor
        return None

    def get_monitor_for_widget(self, widget: QWidget) -> Optional[MonitorInfo]:
        """Get the monitor that contains the center of the widget."""
        widget_rect = widget.geometry()
        center_point = widget_rect.center()
        return self.get_monitor_at_point(center_point)

    def snap_to_monitor_edge(self, widget: QWidget, snap_distance: int = 20) -> bool:
        """Snap widget to the nearest monitor edge if within snap distance."""
        current_monitor = self.get_monitor_for_widget(widget)
        if not current_monitor:
            return False

        widget_rect = widget.geometry()
        monitor_rect = current_monitor.available_geometry
        new_x, new_y = widget_rect.x(), widget_rect.y()
        snapped = False

        # Snap to left edge
        if abs(widget_rect.left() - monitor_rect.left()) <= snap_distance:
            new_x = monitor_rect.left()
            snapped = True

        # Snap to right edge
        elif abs(widget_rect.right() - monitor_rect.right()) <= snap_distance:
            new_x = monitor_rect.right() - widget_rect.width()
            snapped = True

        # Snap to top edge
        if abs(widget_rect.top() - monitor_rect.top()) <= snap_distance:
            new_y = monitor_rect.top()
            snapped = True

        # Snap to bottom edge
        elif abs(widget_rect.bottom() - monitor_rect.bottom()) <= snap_distance:
            new_y = monitor_rect.bottom() - widget_rect.height()
            snapped = True

        if snapped:
            widget.move(new_x, new_y)

        return snapped

    def get_monitor_bounds_for_widget(self, widget: QWidget) -> Optional[QRect]:
        """Get the bounds of the monitor containing the widget."""
        monitor = self.get_monitor_for_widget(widget)
        return monitor.available_geometry if monitor else None

    def constrain_widget_to_monitor(self, widget: QWidget) -> bool:
        """Ensure widget stays within its current monitor bounds."""
        monitor_bounds = self.get_monitor_bounds_for_widget(widget)
        if not monitor_bounds:
            return False

        widget_rect = widget.geometry()
        new_x = max(monitor_bounds.left(),
                   min(widget_rect.x(), monitor_bounds.right() - widget_rect.width()))
        new_y = max(monitor_bounds.top(),
                   min(widget_rect.y(), monitor_bounds.bottom() - widget_rect.height()))

        if new_x != widget_rect.x() or new_y != widget_rect.y():
            widget.move(new_x, new_y)
            return True

        return False

    def move_overlay_to_monitor(self, widget: QWidget, target_monitor_index: int,
                               position: MonitorPosition = MonitorPosition.CENTER) -> bool:
        """Move an overlay to a specific monitor."""
        target_monitor = self.get_monitor_by_index(target_monitor_index)
        if not target_monitor:
            return False

        new_position = self.calculate_position(target_monitor_index, position, widget.size())
        if new_position:
            widget.move(new_position)
            return True

        return False

    def get_monitor_layout_info(self) -> Dict[str, any]:
        """Get comprehensive information about the monitor layout."""
        self._refresh_monitors()

        layout_info = {
            "total_monitors": len(self.monitors),
            "primary_monitor_index": next((i for i, m in enumerate(self.monitors) if m.is_primary), 0),
            "total_resolution": QSize(0, 0),
            "monitors": []
        }

        # Calculate total desktop area
        if self.monitors:
            min_x = min(m.geometry.left() for m in self.monitors)
            max_x = max(m.geometry.right() for m in self.monitors)
            min_y = min(m.geometry.top() for m in self.monitors)
            max_y = max(m.geometry.bottom() for m in self.monitors)
            layout_info["total_resolution"] = QSize(max_x - min_x, max_y - min_y)

        # Add detailed monitor information
        for monitor in self.monitors:
            monitor_data = {
                "index": monitor.index,
                "name": monitor.name,
                "geometry": {
                    "x": monitor.geometry.x(),
                    "y": monitor.geometry.y(),
                    "width": monitor.geometry.width(),
                    "height": monitor.geometry.height()
                },
                "available_geometry": {
                    "x": monitor.available_geometry.x(),
                    "y": monitor.available_geometry.y(),
                    "width": monitor.available_geometry.width(),
                    "height": monitor.available_geometry.height()
                },
                "device_pixel_ratio": monitor.device_pixel_ratio,
                "refresh_rate": monitor.refresh_rate,
                "is_primary": monitor.is_primary,
                "orientation": monitor.orientation,
                "physical_size": {
                    "width": monitor.physical_size.width(),
                    "height": monitor.physical_size.height()
                }
            }
            layout_info["monitors"].append(monitor_data)

        return layout_info

    def save_configuration(self, config_file: Path):
        """Save multi-monitor configuration to file."""
        self.config_file = config_file
        config_data = {
            "overlay_placements": {}
        }

        for monitor_index, placement in self.overlay_placements.items():
            config_data["overlay_placements"][str(monitor_index)] = {
                "monitor_index": placement.monitor_index,
                "position": placement.position.value,
                "custom_x": placement.custom_x,
                "custom_y": placement.custom_y,
                "offset_x": placement.offset_x,
                "offset_y": placement.offset_y,
                "enabled": placement.enabled
            }

        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as error:
            logger.error(
                "Failed to save multi-monitor configuration",
                exc_info=True,
                extra={
                    "path": str(config_file),
                    "monitor_count": len(self.overlay_placements),
                },
            )

    def load_configuration(self, config_file: Path):
        """Load multi-monitor configuration from file."""
        if not config_file.exists():
            logger.debug(
                "Multi-monitor configuration file not found",
                extra={
                    "path": str(config_file),
                },
            )
            return

        try:
            with open(config_file, 'r') as handle:
                config_data = json.load(handle)

            placements = config_data.get("overlay_placements", {})

            for monitor_index_str, placement_data in placements.items():
                monitor_index = int(monitor_index_str)
                placement = OverlayPlacement(
                    monitor_index=placement_data["monitor_index"],
                    position=MonitorPosition(placement_data["position"]),
                    custom_x=placement_data.get("custom_x"),
                    custom_y=placement_data.get("custom_y"),
                    offset_x=placement_data.get("offset_x", 0),
                    offset_y=placement_data.get("offset_y", 0),
                    enabled=placement_data.get("enabled", True)
                )
                self.overlay_placements[monitor_index] = placement

        except Exception as error:
            logger.error(
                "Failed to load multi-monitor configuration",
                exc_info=True,
                extra={
                    "path": str(config_file),
                },
            )
            return

        self._refresh_monitors()
        self.create_default_placements()

    def create_default_placements(self):
        """Create default overlay placements for all monitors."""
        self._refresh_monitors()

        for i, monitor in enumerate(self.monitors):
            if i not in self.overlay_placements: