"""
Comprehensive UX improvements and accessibility features for Moni system monitor.
Provides enhanced user experience with accessibility compliance, theming, and usability optimizations.
"""

from __future__ import annotations

import sys
import logging
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import time
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSlider, QComboBox, QCheckBox, QTextEdit, QTabWidget,
    QScrollArea, QGridLayout, QSplitter, QMenuBar, QMenu, QAction,
    QStatusBar, QProgressBar, QToolTip, QMessageBox, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox, QGroupBox
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QObject, QThread, QPropertyAnimation,
    QEasingCurve, QRect, QSize, QSettings, QCoreApplication
)
from PySide6.QtGui import (
    QFont, QFontMetrics, QPalette, QColor, QIcon, QPixmap, QPainter,
    QLinearGradient, QBrush, QKeySequence, QShortcut, QAccessible
)

logger = logging.getLogger(__name__)


class Theme(Enum):
    """Available UI themes."""
    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"
    AUTO = "auto"


class AccessibilityLevel(Enum):
    """Accessibility compliance levels."""
    STANDARD = "standard"
    AA = "aa"  # WCAG 2.1 AA
    AAA = "aaa"  # WCAG 2.1 AAA


@dataclass
class ColorScheme:
    """Color scheme definition."""
    primary: str
    secondary: str
    background: str
    surface: str
    text_primary: str
    text_secondary: str
    accent: str
    error: str
    warning: str
    success: str
    info: str


@dataclass
class FontSettings:
    """Font configuration settings."""
    family: str = "Segoe UI"
    size: int = 10
    weight: int = 400  # Normal weight
    line_height: float = 1.4
    letter_spacing: float = 0.0


@dataclass
class AccessibilitySettings:
    """Accessibility configuration."""
    high_contrast: bool = False
    large_text: bool = False
    reduced_motion: bool = False
    screen_reader_support: bool = True
    keyboard_navigation: bool = True
    focus_indicators: bool = True
    alt_text_enabled: bool = True
    sound_notifications: bool = False
    text_scale_factor: float = 1.0
    min_color_contrast: float = 4.5  # WCAG AA standard


@dataclass
class AnimationSettings:
    """Animation and transition settings."""
    enabled: bool = True
    duration_fast: int = 150
    duration_normal: int = 300
    duration_slow: int = 500
    easing: str = "ease_out"
    reduced_motion: bool = False


class ThemeManager:
    """Manages UI themes and color schemes."""

    def __init__(self):
        self.current_theme = Theme.AUTO
        self.color_schemes = self._create_default_color_schemes()
        self.custom_schemes: Dict[str, ColorScheme] = {}

    def _create_default_color_schemes(self) -> Dict[Theme, ColorScheme]:
        """Create default color schemes."""
        return {
            Theme.LIGHT: ColorScheme(
                primary="#2196F3",
                secondary="#03DAC6",
                background="#FFFFFF",
                surface="#F5F5F5",
                text_primary="#212121",
                text_secondary="#757575",
                accent="#FF4081",
                error="#F44336",
                warning="#FF9800",
                success="#4CAF50",
                info="#2196F3"
            ),
            Theme.DARK: ColorScheme(
                primary="#BB86FC",
                secondary="#03DAC6",
                background="#121212",
                surface="#1E1E1E",
                text_primary="#FFFFFF",
                text_secondary="#B0B0B0",
                accent="#CF6679",
                error="#CF6679",
                warning="#FFA726",
                success="#66BB6A",
                info="#42A5F5"
            ),
            Theme.HIGH_CONTRAST: ColorScheme(
                primary="#FFFF00",
                secondary="#00FFFF",
                background="#000000",
                surface="#1A1A1A",
                text_primary="#FFFFFF",
                text_secondary="#FFFFFF",
                accent="#FFFFFF",
                error="#FF0000",
                warning="#FFFF00",
                success="#00FF00",
                info="#0080FF"
            )
        }

    def get_color_scheme(self, theme: Theme) -> ColorScheme:
        """Get color scheme for theme."""
        if theme == Theme.AUTO:
            # Detect system theme preference
            app = QApplication.instance()
            if app and app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
                theme = Theme.DARK
            else:
                theme = Theme.LIGHT

        return self.color_schemes.get(theme, self.color_schemes[Theme.LIGHT])

    def apply_theme(self, widget: QWidget, theme: Theme) -> None:
        """Apply theme to widget."""
        scheme = self.get_color_scheme(theme)

        # Create stylesheet
        stylesheet = f"""
        QWidget {{
            background-color: {scheme.background};
            color: {scheme.text_primary};
            font-family: "Segoe UI", Arial, sans-serif;
        }}

        QLabel {{
            color: {scheme.text_primary};
        }}

        QPushButton {{
            background-color: {scheme.primary};
            color: {scheme.background};
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 500;
        }}

        QPushButton:hover {{
            background-color: {self._darken_color(scheme.primary, 0.1)};
        }}

        QPushButton:pressed {{
            background-color: {self._darken_color(scheme.primary, 0.2)};
        }}

        QPushButton:disabled {{
            background-color: {scheme.text_secondary};
            color: {scheme.surface};
        }}

        QFrame {{
            background-color: {scheme.surface};
            border-radius: 8px;
        }}

        QLineEdit, QTextEdit, QComboBox {{
            background-color: {scheme.surface};
            border: 2px solid {scheme.text_secondary};
            border-radius: 4px;
            padding: 8px;
            color: {scheme.text_primary};
        }}

        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border-color: {scheme.primary};
        }}

        QTabWidget::pane {{
            background-color: {scheme.surface};
            border-radius: 8px;
        }}

        QTabBar::tab {{
            background-color: {scheme.background};
            color: {scheme.text_secondary};
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}

        QTabBar::tab:selected {{
            background-color: {scheme.surface};
            color: {scheme.text_primary};
        }}

        QScrollBar:vertical {{
            background-color: {scheme.background};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {scheme.text_secondary};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {scheme.primary};
        }}

        QMenuBar {{
            background-color: {scheme.surface};
            color: {scheme.text_primary};
        }}

        QMenuBar::item:selected {{
            background-color: {scheme.primary};
        }}

        QMenu {{
            background-color: {scheme.surface};
            color: {scheme.text_primary};
            border: 1px solid {scheme.text_secondary};
        }}

        QMenu::item:selected {{
            background-color: {scheme.primary};
        }}

        QStatusBar {{
            background-color: {scheme.surface};
            color: {scheme.text_primary};
        }}
        """

        widget.setStyleSheet(stylesheet)

    def _darken_color(self, color: str, factor: float) -> str:
        """Darken a color by a factor."""
        # Simple darkening - in production, use proper color manipulation
        if color.startswith('#'):
            rgb = int(color[1:], 16)
            r = (rgb >> 16) & 0xFF
            g = (rgb >> 8) & 0xFF
            b = rgb & 0xFF

            r = max(0, int(r * (1 - factor)))
            g = max(0, int(g * (1 - factor)))
            b = max(0, int(b * (1 - factor)))

            return f"#{r:02x}{g:02x}{b:02x}"
        return color


class AccessibilityManager:
    """Manages accessibility features and compliance."""

    def __init__(self):
        self.settings = AccessibilitySettings()
        self.font_settings = FontSettings()
        self.screen_reader_enabled = self._detect_screen_reader()

    def _detect_screen_reader(self) -> bool:
        """Detect if screen reader is active."""
        try:
            # Check for common screen readers on Windows
            if sys.platform == "win32":
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq nvda.exe"],
                    capture_output=True, text=True
                )
                if "nvda.exe" in result.stdout:
                    return True

                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq jaws.exe"],
                    capture_output=True, text=True
                )
                if "jaws.exe" in result.stdout:
                    return True
        except Exception:
            pass

        return False

    def apply_accessibility_settings(self, widget: QWidget) -> None:
        """Apply accessibility settings to widget."""
        # Font scaling
        if self.settings.large_text or self.settings.text_scale_factor != 1.0:
            self._apply_font_scaling(widget)

        # High contrast
        if self.settings.high_contrast:
            self._apply_high_contrast(widget)

        # Focus indicators
        if self.settings.focus_indicators:
            self._enhance_focus_indicators(widget)

        # Keyboard navigation
        if self.settings.keyboard_navigation:
            self._setup_keyboard_navigation(widget)

        # Screen reader support
        if self.settings.screen_reader_support:
            self._setup_screen_reader_support(widget)

    def _apply_font_scaling(self, widget: QWidget) -> None:
        """Apply font scaling for better readability."""
        font = widget.font()
        base_size = self.font_settings.size
        scaled_size = int(base_size * self.settings.text_scale_factor)

        if self.settings.large_text:
            scaled_size = int(scaled_size * 1.2)

        font.setPointSize(scaled_size)
        font.setWeight(self.font_settings.weight)
        widget.setFont(font)

        # Apply to all child widgets
        for child in widget.findChildren(QWidget):
            child_font = child.font()
            child_font.setPointSize(scaled_size)
            child.setFont(child_font)

    def _apply_high_contrast(self, widget: QWidget) -> None:
        """Apply high contrast styling."""
        palette = widget.palette()

        # High contrast colors
        palette.setColor(QPalette.Window, QColor("#000000"))
        palette.setColor(QPalette.WindowText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Base, QColor("#000000"))
        palette.setColor(QPalette.AlternateBase, QColor("#1A1A1A"))
        palette.setColor(QPalette.Text, QColor("#FFFFFF"))
        palette.setColor(QPalette.Button, QColor("#333333"))
        palette.setColor(QPalette.ButtonText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Highlight, QColor("#FFFF00"))
        palette.setColor(QPalette.HighlightedText, QColor("#000000"))

        widget.setPalette(palette)

    def _enhance_focus_indicators(self, widget: QWidget) -> None:
        """Enhance focus indicators for better visibility following Atlassian guidelines."""
        # Atlassian-style focus indicators with proper contrast and visibility
        focus_style = """
        QWidget:focus {
            outline: 2px solid #4C9AFF;
            outline-offset: 1px;
        }
        QPushButton:focus {
            outline: 2px solid #4C9AFF;
            outline-offset: 2px;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border-color: #4C9AFF;
            outline: 2px solid rgba(76, 154, 255, 0.5);
            outline-offset: -2px;
        }
        QTabBar::tab:focus {
            outline: 2px solid #4C9AFF;
            outline-offset: -1px;
        }
        """

        current_style = widget.styleSheet()
        widget.setStyleSheet(current_style + focus_style)

    def _setup_keyboard_navigation(self, widget: QWidget) -> None:
        """Set up enhanced keyboard navigation following Atlassian patterns."""
        # Enable tab navigation for all focusable widgets
        widget.setFocusPolicy(Qt.TabFocus)

        # Set up logical tab order
        focusable_widgets = []
        for child in widget.findChildren(QWidget):
            if child.focusPolicy() != Qt.NoFocus:
                focusable_widgets.append(child)

        # Set logical tab order
        for i in range(len(focusable_widgets) - 1):
            QWidget.setTabOrder(focusable_widgets[i], focusable_widgets[i + 1])

        # Add Atlassian-style keyboard shortcuts
        self._setup_atlassian_shortcuts(widget)

    def _setup_atlassian_shortcuts(self, widget: QWidget) -> None:
        """Set up Atlassian-style keyboard shortcuts for better navigation."""
        from PySide6.QtGui import QShortcut, QKeySequence

        # Skip links for screen reader users (focus first interactive element)
        skip_link = QShortcut(QKeySequence("Alt+S"), widget)
        skip_link.activated.connect(lambda: self._focus_first_interactive(widget))

        # Focus management shortcuts
        # Ctrl+Tab to cycle through sections (similar to browser tab behavior)
        next_section = QShortcut(QKeySequence("Ctrl+Tab"), widget)
        next_section.activated.connect(lambda: self._focus_next_section(widget))

        # Shift+Ctrl+Tab for previous section
        prev_section = QShortcut(QKeySequence("Shift+Ctrl+Tab"), widget)
        prev_section.activated.connect(lambda: self._focus_previous_section(widget))

        # Escape to clear focus or close dialogs
        escape_shortcut = QShortcut(QKeySequence("Escape"), widget)
        escape_shortcut.activated.connect(lambda: self._handle_escape(widget))

    def _focus_first_interactive(self, widget: QWidget) -> None:
        """Focus the first interactive element (skip link functionality)."""
        for child in widget.findChildren(QWidget):
            if child.focusPolicy() != Qt.NoFocus and child.isEnabled():
                child.setFocus()
                break

    def _focus_next_section(self, widget: QWidget) -> None:
        """Move focus to next logical section."""
        # This is a simplified implementation - in practice, you'd group widgets by sections
        current_focus = widget.focusWidget()
        if current_focus:
            focusable_widgets = [w for w in widget.findChildren(QWidget)
                               if w.focusPolicy() != Qt.NoFocus and w.isEnabled()]

            try:
                current_index = focusable_widgets.index(current_focus)
                next_index = (current_index + 1) % len(focusable_widgets)
                focusable_widgets[next_index].setFocus()
            except ValueError:
                pass

    def _focus_previous_section(self, widget: QWidget) -> None:
        """Move focus to previous logical section."""
        current_focus = widget.focusWidget()
        if current_focus:
            focusable_widgets = [w for w in widget.findChildren(QWidget)
                               if w.focusPolicy() != Qt.NoFocus and w.isEnabled()]

            try:
                current_index = focusable_widgets.index(current_focus)
                prev_index = (current_index - 1) % len(focusable_widgets)
                focusable_widgets[prev_index].setFocus()
            except ValueError:
                pass

    def _handle_escape(self, widget: QWidget) -> None:
        """Handle escape key - clear focus or close dialogs."""
        if isinstance(widget, QDialog):
            widget.reject()
        else:
            # Clear focus from current widget
            if widget.focusWidget():
                widget.focusWidget().clearFocus()

    def _setup_screen_reader_support(self, widget: QWidget) -> None:
        """Set up screen reader support following Atlassian accessibility guidelines."""
        # Set accessible names and descriptions for better screen reader experience
        for child in widget.findChildren(QWidget):
            if hasattr(child, 'text') and child.text():
                child.setAccessibleName(child.text())

            # Set accessible descriptions for complex widgets
            if isinstance(child, QLabel) and child.pixmap():
                child.setAccessibleDescription("Image: " + (child.accessibleName() or "decorative"))

            elif isinstance(child, QProgressBar):
                child.setAccessibleDescription(f"Progress: {child.value()}% of {child.maximum()}")

            elif isinstance(child, QSlider):
                child.setAccessibleDescription(f"Slider value: {child.value()}")

            elif isinstance(child, QPushButton):
                # Ensure buttons have clear accessible names
                if not child.accessibleName():
                    child.setAccessibleName(child.text())

        # Enable accessible updates for dynamic content
        self._connect_accessible_updates(widget)

    def _connect_accessible_updates(self, widget: QWidget) -> None:
        """Connect signals for accessible updates."""
        from PySide6.QtGui import QAccessible

        # Connect progress bar updates
        for progress_bar in widget.findChildren(QProgressBar):
            progress_bar.valueChanged.connect(
                lambda value, pb=progress_bar: self._update_progress_accessible(pb, value)
            )

        # Connect slider updates
        for slider in widget.findChildren(QSlider):
            slider.valueChanged.connect(
                lambda value, s=slider: self._update_slider_accessible(s, value)
            )

    def _update_progress_accessible(self, progress_bar: QProgressBar, value: int) -> None:
        """Update accessible description for progress bar."""
        from PySide6.QtGui import QAccessible
        max_value = progress_bar.maximum()
        percentage = int((value / max_value) * 100) if max_value > 0 else 0
        progress_bar.setAccessibleDescription(f"Progress: {percentage}% complete, {value} of {max_value}")
        QAccessible.updateAccessibility(progress_bar, 0, QAccessible.Event.ValueChanged)

    def _update_slider_accessible(self, slider: QSlider, value: int) -> None:
        """Update accessible description for slider."""
        from PySide6.QtGui import QAccessible
        min_value = slider.minimum()
        max_value = slider.maximum()
        slider.setAccessibleDescription(f"Value: {value}, range {min_value} to {max_value}")
        QAccessible.updateAccessibility(slider, 0, QAccessible.Event.ValueChanged)

    def check_color_contrast(self, foreground: str, background: str) -> float:
        """Check color contrast ratio for accessibility compliance."""
        def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        def relative_luminance(rgb: Tuple[int, int, int]) -> float:
            def gamma_correct(c: float) -> float:
                return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

            r, g, b = [c / 255.0 for c in rgb]
            return 0.2126 * gamma_correct(r) + 0.7152 * gamma_correct(g) + 0.0722 * gamma_correct(b)

        fg_rgb = hex_to_rgb(foreground)
        bg_rgb = hex_to_rgb(background)

        fg_lum = relative_luminance(fg_rgb)
        bg_lum = relative_luminance(bg_rgb)

        lighter = max(fg_lum, bg_lum)
        darker = min(fg_lum, bg_lum)

        return (lighter + 0.05) / (darker + 0.05)

    def get_accessibility_report(self, widget: QWidget) -> Dict[str, Any]:
        """Generate accessibility compliance report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'accessibility_level': self.settings.min_color_contrast,
            'issues': [],
            'recommendations': [],
            'compliant': True
        }

        # Check focus indicators
        focusable_widgets = widget.findChildren(QWidget)
        focusable_count = sum(1 for w in focusable_widgets if w.focusPolicy() != Qt.NoFocus)

        if focusable_count > 0 and not self.settings.focus_indicators:
            report['issues'].append('Focus indicators are disabled')
            report['compliant'] = False

        # Check font sizes
        small_text_widgets = []
        for child in widget.findChildren(QLabel):
            font_size = child.font().pointSize()
            if font_size < 12:  # Minimum recommended size
                small_text_widgets.append(child.objectName() or 'Unnamed label')

        if small_text_widgets:
            report['issues'].append(f'Small text found in: {", ".join(small_text_widgets)}')
            report['recommendations'].append('Increase font size to at least 12pt')

        # Check for alt text on images
        # Note: This would need to be implemented based on custom image widgets

        # Generate recommendations
        if not self.settings.keyboard_navigation:
            report['recommendations'].append('Enable keyboard navigation for better accessibility')

        if not self.settings.screen_reader_support:
            report['recommendations'].append('Enable screen reader support')

        if self.settings.min_color_contrast < 4.5:
            report['recommendations'].append('Increase minimum color contrast to meet WCAG AA standards')

        return report


class AnimationManager:
    """Manages UI animations and transitions."""

    def __init__(self):
        self.settings = AnimationSettings()
        self.active_animations: List[QPropertyAnimation] = []

    def create_fade_animation(self, widget: QWidget, start_opacity: float = 0.0,
                            end_opacity: float = 1.0, duration: Optional[int] = None) -> QPropertyAnimation:
        """Create fade in/out animation."""
        if not self.settings.enabled or self.settings.reduced_motion:
            return None

        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setStartValue(start_opacity)
        animation.setEndValue(end_opacity)
        animation.setDuration(duration or self.settings.duration_normal)
        animation.setEasingCurve(self._get_easing_curve())

        self.active_animations.append(animation)
        animation.finished.connect(lambda: self._cleanup_animation(animation))

        return animation

    def create_slide_animation(self, widget: QWidget, start_pos: QRect,
                             end_pos: QRect, duration: Optional[int] = None) -> QPropertyAnimation:
        """Create slide animation."""
        if not self.settings.enabled or self.settings.reduced_motion:
            return None

        animation = QPropertyAnimation(widget, b"geometry")
        animation.setStartValue(start_pos)
        animation.setEndValue(end_pos)
        animation.setDuration(duration or self.settings.duration_normal)
        animation.setEasingCurve(self._get_easing_curve())

        self.active_animations.append(animation)
        animation.finished.connect(lambda: self._cleanup_animation(animation))

        return animation

    def create_scale_animation(self, widget: QWidget, start_scale: float = 0.8,
                             end_scale: float = 1.0, duration: Optional[int] = None) -> QPropertyAnimation:
        """Create scale animation."""
        if not self.settings.enabled or self.settings.reduced_motion:
            return None

        # Note: Scale animation would require custom implementation or using QGraphicsView
        # This is a simplified version
        animation = QPropertyAnimation(widget, b"size")
        start_size = QSize(int(widget.width() * start_scale), int(widget.height() * start_scale))
        end_size = QSize(int(widget.width() * end_scale), int(widget.height() * end_scale))

        animation.setStartValue(start_size)
        animation.setEndValue(end_size)
        animation.setDuration(duration or self.settings.duration_normal)
        animation.setEasingCurve(self._get_easing_curve())

        self.active_animations.append(animation)
        animation.finished.connect(lambda: self._cleanup_animation(animation))

        return animation

    def _get_easing_curve(self) -> QEasingCurve:
        """Get easing curve based on settings."""
        easing_map = {
            "linear": QEasingCurve.Linear,
            "ease_in": QEasingCurve.InCubic,
            "ease_out": QEasingCurve.OutCubic,
            "ease_in_out": QEasingCurve.InOutCubic,
            "bounce": QEasingCurve.OutBounce
        }
        return QEasingCurve(easing_map.get(self.settings.easing, QEasingCurve.OutCubic))

    def _cleanup_animation(self, animation: QPropertyAnimation) -> None:
        """Clean up finished animation."""
        if animation in self.active_animations:
            self.active_animations.remove(animation)

    def stop_all_animations(self) -> None:
        """Stop all active animations."""
        for animation in self.active_animations:
            animation.stop()
        self.active_animations.clear()


class UXManager:
    """Main UX and accessibility manager."""

    def __init__(self):
        self.theme_manager = ThemeManager()
        self.accessibility_manager = AccessibilityManager()
        self.animation_manager = AnimationManager()
        self.settings_storage = QSettings("Moni", "UXSettings")

        # Load saved settings
        self._load_settings()

    def _load_settings(self) -> None:
        """Load UX settings from storage."""
        # Theme settings
        theme_name = self.settings_storage.value("theme", Theme.AUTO.value)
        try:
            self.theme_manager.current_theme = Theme(theme_name)
        except ValueError:
            self.theme_manager.current_theme = Theme.AUTO

        # Accessibility settings
        self.accessibility_manager.settings.high_contrast = self.settings_storage.value(
            "accessibility/high_contrast", False, bool
        )
        self.accessibility_manager.settings.large_text = self.settings_storage.value(
            "accessibility/large_text", False, bool
        )
        self.accessibility_manager.settings.reduced_motion = self.settings_storage.value(
            "accessibility/reduced_motion", False, bool
        )
        self.accessibility_manager.settings.text_scale_factor = self.settings_storage.value(
            "accessibility/text_scale_factor", 1.0, float
        )

        # Animation settings
        self.animation_manager.settings.enabled = self.settings_storage.value(
            "animation/enabled", True, bool
        )
        self.animation_manager.settings.reduced_motion = self.accessibility_manager.settings.reduced_motion

    def save_settings(self) -> None:
        """Save UX settings to storage."""
        # Theme settings
        self.settings_storage.setValue("theme", self.theme_manager.current_theme.value)

        # Accessibility settings
        self.settings_storage.setValue(
            "accessibility/high_contrast",
            self.accessibility_manager.settings.high_contrast
        )
        self.settings_storage.setValue(
            "accessibility/large_text",
            self.accessibility_manager.settings.large_text
        )
        self.settings_storage.setValue(
            "accessibility/reduced_motion",
            self.accessibility_manager.settings.reduced_motion
        )
        self.settings_storage.setValue(
            "accessibility/text_scale_factor",
            self.accessibility_manager.settings.text_scale_factor
        )

        # Animation settings
        self.settings_storage.setValue(
            "animation/enabled",
            self.animation_manager.settings.enabled
        )

        self.settings_storage.sync()

    def apply_ux_enhancements(self, widget: QWidget) -> None:
        """Apply all UX enhancements to widget."""
        # Apply theme
        self.theme_manager.apply_theme(widget, self.theme_manager.current_theme)

        # Apply accessibility features
        self.accessibility_manager.apply_accessibility_settings(widget)

        # Set up tooltips with improved styling
        self._setup_enhanced_tooltips(widget)

        # Enable smooth scrolling
        self._setup_smooth_scrolling(widget)

    def _setup_enhanced_tooltips(self, widget: QWidget) -> None:
        """Set up enhanced tooltips with better styling."""
        tooltip_style = """
        QToolTip {
            background-color: rgba(50, 50, 50, 240);
            color: white;
            border: 1px solid gray;
            border-radius: 4px;
            padding: 8px;
            font-size: 11px;
        }
        """
        QToolTip.setFont(QFont("Segoe UI", 10))
        widget.setStyleSheet(widget.styleSheet() + tooltip_style)

    def _setup_smooth_scrolling(self, widget: QWidget) -> None:
        """Set up smooth scrolling for scroll areas."""
        for scroll_area in widget.findChildren(QScrollArea):
            # Enable smooth scrolling
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setWidgetResizable(True)

    def create_settings_dialog(self, parent: QWidget = None) -> QDialog:
        """Create UX settings dialog."""
        dialog = QDialog(parent)
        dialog.setWindowTitle("UX & Accessibility Settings")
        dialog.setModal(True)
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)

        # Theme settings
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout(theme_group)

        theme_combo = QComboBox()
        theme_combo.addItems([theme.value.title() for theme in Theme])
        theme_combo.setCurrentText(self.theme_manager.current_theme.value.title())
        theme_layout.addRow("Theme:", theme_combo)

        layout.addWidget(theme_group)

        # Accessibility settings
        accessibility_group = QGroupBox("Accessibility")
        accessibility_layout = QFormLayout(accessibility_group)

        high_contrast_check = QCheckBox()
        high_contrast_check.setChecked(self.accessibility_manager.settings.high_contrast)
        accessibility_layout.addRow("High Contrast:", high_contrast_check)

        large_text_check = QCheckBox()
        large_text_check.setChecked(self.accessibility_manager.settings.large_text)
        accessibility_layout.addRow("Large Text:", large_text_check)

        reduced_motion_check = QCheckBox()
        reduced_motion_check.setChecked(self.accessibility_manager.settings.reduced_motion)
        accessibility_layout.addRow("Reduce Motion:", reduced_motion_check)

        text_scale_spin = QSpinBox()
        text_scale_spin.setRange(50, 200)
        text_scale_spin.setSuffix("%")
        text_scale_spin.setValue(int(self.accessibility_manager.settings.text_scale_factor * 100))
        accessibility_layout.addRow("Text Scale:", text_scale_spin)

        layout.addWidget(accessibility_group)

        # Animation settings
        animation_group = QGroupBox("Animations")
        animation_layout = QFormLayout(animation_group)

        animations_check = QCheckBox()
        animations_check.setChecked(self.animation_manager.settings.enabled)
        animation_layout.addRow("Enable Animations:", animations_check)

        layout.addWidget(animation_group)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)

        # Connect signals
        def apply_settings():
            # Apply theme
            theme_value = theme_combo.currentText().lower()
            self.theme_manager.current_theme = Theme(theme_value)

            # Apply accessibility settings
            self.accessibility_manager.settings.high_contrast = high_contrast_check.isChecked()
            self.accessibility_manager.settings.large_text = large_text_check.isChecked()
            self.accessibility_manager.settings.reduced_motion = reduced_motion_check.isChecked()
            self.accessibility_manager.settings.text_scale_factor = text_scale_spin.value() / 100.0

            # Apply animation settings
            self.animation_manager.settings.enabled = animations_check.isChecked()
            self.animation_manager.settings.reduced_motion = reduced_motion_check.isChecked()

            # Save settings
            self.save_settings()

            dialog.accept()

        button_box.accepted.connect(apply_settings)
        button_box.rejected.connect(dialog.reject)

        # Apply current theme to dialog
        self.apply_ux_enhancements(dialog)

        return dialog

    def get_ux_status(self) -> Dict[str, Any]:
        """Get comprehensive UX status report."""
        return {
            "theme": {
                "current": self.theme_manager.current_theme.value,
                "available": [theme.value for theme in Theme]
            },
            "accessibility": {
                "high_contrast": self.accessibility_manager.settings.high_contrast,
                "large_text": self.accessibility_manager.settings.large_text,
                "reduced_motion": self.accessibility_manager.settings.reduced_motion,
                "screen_reader_detected": self.accessibility_manager.screen_reader_enabled,
                "text_scale_factor": self.accessibility_manager.settings.text_scale_factor,
                "keyboard_navigation": self.accessibility_manager.settings.keyboard_navigation,
                "focus_indicators": self.accessibility_manager.settings.focus_indicators
            },
            "animations": {
                "enabled": self.animation_manager.settings.enabled,
                "active_count": len(self.animation_manager.active_animations),
                "reduced_motion": self.animation_manager.settings.reduced_motion
            }
        }


# Global UX manager instance
ux_manager = UXManager()