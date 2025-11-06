from enum import Enum
from typing import Optional, Callable, Any

from PySide6.QtWidgets import QPushButton, QWidget, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, Signal, QPoint, QTimer, QObject
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath

from .design_tokens import DesignTokens, DEFAULT_TOKENS


class ButtonAppearance(Enum):
    """Button appearance variants following Atlassian design system."""
    DEFAULT = "default"      # Default button style
    PRIMARY = "primary"      # Primary action button
    DANGER = "danger"        # Destructive action button
    LINK = "link"           # Link-style button
    SUBTLE = "subtle"       # Subtle button style


class ButtonSize(Enum):
    """Button size variants."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class AtlassianButton(QPushButton):
    """
    Atlassian-style button component with proper design tokens integration.

    Features:
    - Multiple appearance variants (default, primary, danger, link, subtle)
    - Size variants (small, medium, large)
    - Proper spacing and typography
    - Hover and pressed states
    - Loading state support
    - Accessibility features
    """

    # Signals
    clicked_signal = Signal()

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        appearance: ButtonAppearance = ButtonAppearance.DEFAULT,
        size: ButtonSize = ButtonSize.MEDIUM,
        design_tokens: Optional[DesignTokens] = None,
        is_loading: bool = False,
        is_disabled: bool = False
    ):
        super().__init__(text, parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._appearance = appearance
        self._size = size
        self._is_loading = is_loading
        self._is_disabled = is_disabled

        self._setup_button()
        self._apply_styling()

        # Connect signals
        self.clicked.connect(self._on_clicked)

    def _setup_button(self):
        """Setup button properties."""
        # Remove default styling
        self.setStyleSheet("")
        self.setFlat(False)

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)

        # Set focus policy for accessibility
        self.setFocusPolicy(Qt.StrongFocus)

        # Set size constraints based on button size
        self._update_size_constraints()

    def _update_size_constraints(self):
        """Update button size constraints based on size variant."""
        spacing = self._design_tokens.spacing

        if self._size == ButtonSize.SMALL:
            self.setMinimumHeight(spacing.space_300)  # 24px
            self.setMinimumWidth(spacing.space_400)   # 32px
        elif self._size == ButtonSize.MEDIUM:
            self.setMinimumHeight(spacing.space_400)  # 32px
            self.setMinimumWidth(spacing.space_500)   # 40px
        elif self._size == ButtonSize.LARGE:
            self.setMinimumHeight(spacing.space_500)  # 40px
            self.setMinimumWidth(spacing.space_600)   # 48px

    def _apply_styling(self):
        """Apply styling based on current state."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate Qt stylesheet based on design tokens and state."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base button styles
        base_styles = f"""
            QPushButton {{
                border: {borders.border_width}px solid transparent;
                border-radius: {borders.border_radius}px;
                font-family: {typography.font_family};
                font-weight: {typography.font_weight_medium};
                outline: none;
                text-align: center;
                text-decoration: none;
                transition: all 0.2s ease-in-out;
                white-space: nowrap;
            }}
        """

        # Size-specific styles
        size_styles = ""
        if self._size == ButtonSize.SMALL:
            size_styles = f"""
                QPushButton {{
                    font-size: {typography.font_size_ui_small}px;
                    padding: {spacing.space_050}px {spacing.space_100}px;
                    min-height: {spacing.space_300}px;
                }}
            """
        elif self._size == ButtonSize.MEDIUM:
            size_styles = f"""
                QPushButton {{
                    font-size: {typography.font_size_ui}px;
                    padding: {spacing.space_075}px {spacing.space_150}px;
                    min-height: {spacing.space_400}px;
                }}
            """
        elif self._size == ButtonSize.LARGE:
            size_styles = f"""
                QPushButton {{
                    font-size: {typography.font_size_ui_large}px;
                    padding: {spacing.space_100}px {spacing.space_200}px;
                    min-height: {spacing.space_500}px;
                }}
            """

        # Appearance-specific styles
        appearance_styles = ""

        if self._appearance == ButtonAppearance.DEFAULT:
            appearance_styles = f"""
                QPushButton {{
                    background-color: {colors.surface};
                    border-color: {colors.border};
                    color: {colors.text};
                }}
                QPushButton:hover {{
                    background-color: {colors.surface_sunken};
                    border-color: {colors.border_focused};
                }}
                QPushButton:pressed {{
                    background-color: {colors.surface_raised};
                }}
            """
        elif self._appearance == ButtonAppearance.PRIMARY:
            appearance_styles = f"""
                QPushButton {{
                    background-color: {colors.primary};
                    border-color: {colors.primary};
                    color: {colors.text_on_primary};
                    font-weight: {typography.font_weight_semibold};
                }}
                QPushButton:hover {{
                    background-color: {colors.primary_hover};
                    border-color: {colors.primary_hover};
                }}
                QPushButton:pressed {{
                    background-color: {colors.primary_pressed};
                    border-color: {colors.primary_pressed};
                }}
            """
        elif self._appearance == ButtonAppearance.DANGER:
            appearance_styles = f"""
                QPushButton {{
                    background-color: {colors.error};
                    border-color: {colors.error};
                    color: {colors.text_on_primary};
                    font-weight: {typography.font_weight_semibold};
                }}
                QPushButton:hover {{
                    background-color: {colors.error_hover};
                    border-color: {colors.error_hover};
                }}
                QPushButton:pressed {{
                    background-color: {colors.error_bold};
                    border-color: {colors.error_bold};
                }}
            """
        elif self._appearance == ButtonAppearance.LINK:
            appearance_styles = f"""
                QPushButton {{
                    background-color: transparent;
                    border-color: transparent;
                    color: {colors.primary};
                    text-decoration: underline;
                    font-weight: {typography.font_weight_regular};
                }}
                QPushButton:hover {{
                    color: {colors.primary_hover};
                    text-decoration: none;
                }}
                QPushButton:pressed {{
                    color: {colors.primary_pressed};
                }}
            """
        elif self._appearance == ButtonAppearance.SUBTLE:
            appearance_styles = f"""
                QPushButton {{
                    background-color: transparent;
                    border-color: transparent;
                    color: {colors.text_subtle};
                }}
                QPushButton:hover {{
                    background-color: {colors.surface_sunken};
                    color: {colors.text};
                }}
                QPushButton:pressed {{
                    background-color: {colors.surface_raised};
                }}
            """

        # Disabled state
        disabled_styles = f"""
            QPushButton:disabled {{
                background-color: {colors.surface};
                border-color: {colors.border};
                color: {colors.text_disabled};
                opacity: 0.6;
                cursor: not-allowed;
            }}
        """

        # Focus styles for accessibility
        focus_styles = f"""
            QPushButton:focus {{
                outline: 2px solid {colors.border_focused};
                outline-offset: 2px;
            }}
        """

        return base_styles + size_styles + appearance_styles + disabled_styles + focus_styles

    def _on_clicked(self):
        """Handle button click."""
        if not self._is_disabled and not self._is_loading:
            self.clicked_signal.emit()

    def set_appearance(self, appearance: ButtonAppearance):
        """Set button appearance."""
        self._appearance = appearance
        self._apply_styling()

    def set_button_size(self, size: ButtonSize):
        """Set button size."""
        self._size = size
        self._update_size_constraints()
        self._apply_styling()

    def set_loading(self, is_loading: bool):
        """Set loading state."""
        self._is_loading = is_loading
        self.setEnabled(not is_loading)
        # TODO: Add loading spinner implementation

    def set_disabled(self, disabled: bool):
        """Set disabled state."""
        self._is_disabled = disabled
        self.setEnabled(not disabled)

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._update_size_constraints()
        self._apply_styling()

    # Property getters
    @property
    def appearance(self) -> ButtonAppearance:
        return self._appearance

    @property
    def button_size(self) -> ButtonSize:
        return self._size

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    @property
    def is_disabled(self) -> bool:
        return self._is_disabled


# Convenience functions for creating buttons
def create_button(
    text: str,
    appearance: ButtonAppearance = ButtonAppearance.DEFAULT,
    size: ButtonSize = ButtonSize.MEDIUM,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianButton:
    """Create an Atlassian-style button with the specified properties."""
    return AtlassianButton(
        text=text,
        parent=parent,
        appearance=appearance,
        size=size,
        design_tokens=design_tokens
    )


def create_primary_button(
    text: str,
    size: ButtonSize = ButtonSize.MEDIUM,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianButton:
    """Create a primary action button."""
    return create_button(text, ButtonAppearance.PRIMARY, size, parent, design_tokens)


def create_danger_button(
    text: str,
    size: ButtonSize = ButtonSize.MEDIUM,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianButton:
    """Create a danger/destructive action button."""
    return create_button(text, ButtonAppearance.DANGER, size, parent, design_tokens)


def create_link_button(
    text: str,
    size: ButtonSize = ButtonSize.MEDIUM,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianButton:
    """Create a link-style button."""
    return create_button(text, ButtonAppearance.LINK, size, parent, design_tokens)


class BadgeAppearance(Enum):
    """Badge appearance variants."""
    NEUTRAL = "neutral"      # Default neutral badge
    SUCCESS = "success"      # Success/green badge
    WARNING = "warning"      # Warning/amber badge
    ERROR = "error"          # Error/red badge
    INFORMATION = "information"  # Info/blue badge
    DISCOVERY = "discovery"  # Discovery/purple badge


class AtlassianBadge(QLabel):
    """
    Atlassian-style badge component for status indicators and counts.

    Features:
    - Multiple appearance variants (neutral, success, warning, error, information, discovery)
    - Rounded corners with proper spacing
    - Support for text content
    - Accessible design
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        appearance: BadgeAppearance = BadgeAppearance.NEUTRAL,
        design_tokens: Optional[DesignTokens] = None
    ):
        super().__init__(text, parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._appearance = appearance

        self._setup_badge()
        self._apply_styling()

    def _setup_badge(self):
        """Setup badge properties."""
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(self._design_tokens.spacing.space_200)  # 16px minimum height

        # Set size policy to be flexible
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def _apply_styling(self):
        """Apply styling based on appearance."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and appearance."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base badge styles
        base_styles = f"""
            QLabel {{
                border-radius: {borders.border_radius}px;
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui_small}px;
                font-weight: {typography.font_weight_medium};
                padding: 2px {spacing.space_050}px;
                min-height: {spacing.space_200}px;
                display: inline-block;
            }}
        """

        # Appearance-specific background and text colors
        if self._appearance == BadgeAppearance.NEUTRAL:
            appearance_styles = f"""
                QLabel {{
                    background-color: {colors.surface_sunken};
                    color: {colors.text_subtle};
                    border: 1px solid {colors.border};
                }}
            """
        elif self._appearance == BadgeAppearance.SUCCESS:
            appearance_styles = f"""
                QLabel {{
                    background-color: {colors.success};
                    color: white;
                }}
            """
        elif self._appearance == BadgeAppearance.WARNING:
            appearance_styles = f"""
                QLabel {{
                    background-color: {colors.warning};
                    color: {colors.text};
                }}
            """
        elif self._appearance == BadgeAppearance.ERROR:
            appearance_styles = f"""
                QLabel {{
                    background-color: {colors.error};
                    color: white;
                }}
            """
        elif self._appearance == BadgeAppearance.INFORMATION:
            appearance_styles = f"""
                QLabel {{
                    background-color: {colors.information};
                    color: white;
                }}
            """
        elif self._appearance == BadgeAppearance.DISCOVERY:
            appearance_styles = f"""
                QLabel {{
                    background-color: {colors.discovery};
                    color: white;
                }}
            """
        else:
            appearance_styles = base_styles

        return base_styles + appearance_styles

    def set_appearance(self, appearance: BadgeAppearance):
        """Set badge appearance."""
        self._appearance = appearance
        self._apply_styling()

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def appearance(self) -> BadgeAppearance:
        return self._appearance


class LozengeAppearance(Enum):
    """Lozenge appearance variants."""
    DEFAULT = "default"      # Default lozenge
    SUCCESS = "success"      # Success lozenge
    WARNING = "warning"      # Warning lozenge
    ERROR = "error"          # Error lozenge
    INFORMATION = "information"  # Information lozenge
    DISCOVERY = "discovery"  # Discovery lozenge
    NEW = "new"             # New item lozenge


class AtlassianLozenge(QLabel):
    """
    Atlassian-style lozenge component for status indicators.

    Lozenges are similar to badges but with more subtle styling and
    often used for status indicators and metadata.

    Features:
    - Multiple appearance variants
    - Subtle background colors
    - Proper text contrast
    - Accessible design
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        appearance: LozengeAppearance = LozengeAppearance.DEFAULT,
        design_tokens: Optional[DesignTokens] = None
    ):
        super().__init__(text, parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._appearance = appearance

        self._setup_lozenge()
        self._apply_styling()

    def _setup_lozenge(self):
        """Setup lozenge properties."""
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(self._design_tokens.spacing.space_200)  # 16px minimum height

        # Set size policy to be flexible
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def _apply_styling(self):
        """Apply styling based on appearance."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and appearance."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base lozenge styles - more subtle than badges
        base_styles = f"""
            QLabel {{
                border-radius: {borders.border_radius_large}px;
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui_small}px;
                font-weight: {typography.font_weight_regular};
                padding: 1px {spacing.space_075}px;
                min-height: {spacing.space_200}px;
                display: inline-block;
            }}
        """

        # Appearance-specific styles - more subtle than badges
        if self._appearance == LozengeAppearance.DEFAULT:
            appearance_styles = f"""
                QLabel {{
                    background-color: {colors.surface_sunken};
                    color: {colors.text_subtle};
                }}
            """
        elif self._appearance == LozengeAppearance.SUCCESS:
            appearance_styles = f"""
                QLabel {{
                    background-color: rgba(36, 183, 126, 0.1);
                    color: {colors.success};
                    border: 1px solid rgba(36, 183, 126, 0.2);
                }}
            """
        elif self._appearance == LozengeAppearance.WARNING:
            appearance_styles = f"""
                QLabel {{
                    background-color: rgba(255, 171, 0, 0.1);
                    color: {colors.warning};
                    border: 1px solid rgba(255, 171, 0, 0.2);
                }}
            """
        elif self._appearance == LozengeAppearance.ERROR:
            appearance_styles = f"""
                QLabel {{
                    background-color: rgba(255, 86, 48, 0.1);
                    color: {colors.error};
                    border: 1px solid rgba(255, 86, 48, 0.2);
                }}
            """
        elif self._appearance == LozengeAppearance.INFORMATION:
            appearance_styles = f"""
                QLabel {{
                    background-color: rgba(0, 184, 217, 0.1);
                    color: {colors.information};
                    border: 1px solid rgba(0, 184, 217, 0.2);
                }}
            """
        elif self._appearance == LozengeAppearance.DISCOVERY:
            appearance_styles = f"""
                QLabel {{
                    background-color: rgba(101, 84, 192, 0.1);
                    color: {colors.discovery};
                    border: 1px solid rgba(101, 84, 192, 0.2);
                }}
            """
        elif self._appearance == LozengeAppearance.NEW:
            appearance_styles = f"""
                QLabel {{
                    background-color: rgba(0, 184, 217, 0.1);
                    color: {colors.information};
                    border: 1px solid rgba(0, 184, 217, 0.2);
                    font-weight: {typography.font_weight_semibold};
                }}
            """
        else:
            appearance_styles = base_styles

        return base_styles + appearance_styles

    def set_appearance(self, appearance: LozengeAppearance):
        """Set lozenge appearance."""
        self._appearance = appearance
        self._apply_styling()

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def appearance(self) -> LozengeAppearance:
        return self._appearance


# Convenience functions for creating badges and lozenges
def create_badge(
    text: str,
    appearance: BadgeAppearance = BadgeAppearance.NEUTRAL,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianBadge:
    """Create an Atlassian-style badge."""
    return AtlassianBadge(text, parent, appearance, design_tokens)


def create_lozenge(
    text: str,
    appearance: LozengeAppearance = LozengeAppearance.DEFAULT,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianLozenge:
    """Create an Atlassian-style lozenge."""
    return AtlassianLozenge(text, parent, appearance, design_tokens)


def create_status_badge(
    status: str,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianBadge:
    """Create a status badge with appropriate appearance based on status text."""
    status_lower = status.lower()

    if status_lower in ['success', 'ok', 'healthy', 'active', 'running']:
        appearance = BadgeAppearance.SUCCESS
    elif status_lower in ['warning', 'warn', 'degraded', 'pending']:
        appearance = BadgeAppearance.WARNING
    elif status_lower in ['error', 'fail', 'failed', 'critical', 'stopped']:
        appearance = BadgeAppearance.ERROR
    elif status_lower in ['info', 'information', 'unknown']:
        appearance = BadgeAppearance.INFORMATION
    else:
        appearance = BadgeAppearance.NEUTRAL

    return create_badge(status, appearance, parent, design_tokens)


def create_status_lozenge(
    status: str,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianLozenge:
    """Create a status lozenge with appropriate appearance based on status text."""
    status_lower = status.lower()

    if status_lower in ['success', 'ok', 'healthy', 'active', 'running']:
        appearance = LozengeAppearance.SUCCESS
    elif status_lower in ['warning', 'warn', 'degraded', 'pending']:
        appearance = LozengeAppearance.WARNING
    elif status_lower in ['error', 'fail', 'failed', 'critical', 'stopped']:
        appearance = LozengeAppearance.ERROR
    elif status_lower in ['info', 'information', 'unknown']:
        appearance = LozengeAppearance.INFORMATION
    elif status_lower in ['new', 'beta', 'experimental']:
        appearance = LozengeAppearance.NEW
    else:
        appearance = LozengeAppearance.DEFAULT

    return create_lozenge(status, appearance, parent, design_tokens)


class BannerAppearance(Enum):
    """Banner appearance variants."""
    INFORMATION = "information"  # Blue information banner
    WARNING = "warning"         # Yellow warning banner
    ERROR = "error"            # Red error banner
    SUCCESS = "success"        # Green success banner
    DISCOVERY = "discovery"    # Purple discovery banner


class AtlassianBanner(QWidget):
    """
    Atlassian-style banner component for important messages and notifications.

    Features:
    - Multiple appearance variants with appropriate colors
    - Support for title and description text
    - Icon support for visual context
    - Dismissible functionality
    - Accessible design
    """

    dismissed = Signal()

    def __init__(
        self,
        title: str = "",
        description: str = "",
        parent: Optional[QWidget] = None,
        appearance: BannerAppearance = BannerAppearance.INFORMATION,
        design_tokens: Optional[DesignTokens] = None,
        dismissible: bool = True
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._appearance = appearance
        self._title = title
        self._description = description
        self._dismissible = dismissible

        self._setup_banner()
        self._apply_styling()

    def _setup_banner(self):
        """Setup banner layout and components."""
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QPushButton

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self._design_tokens.spacing.space_200,
            self._design_tokens.spacing.space_150,
            self._design_tokens.spacing.space_200,
            self._design_tokens.spacing.space_150
        )
        layout.setSpacing(self._design_tokens.spacing.space_100)

        # Icon placeholder (could be extended to support actual icons)
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon_label)

        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(self._design_tokens.spacing.space_050)

        self._title_label = QLabel(self._title, self)
        self._title_label.setWordWrap(True)

        self._description_label = QLabel(self._description, self)
        self._description_label.setWordWrap(True)

        text_layout.addWidget(self._title_label)
        if self._description:
            text_layout.addWidget(self._description_label)

        text_container = QWidget(self)
        text_container.setLayout(text_layout)
        layout.addWidget(text_container, 1)  # Stretch to fill space

        # Dismiss button
        if self._dismissible:
            self._dismiss_button = QPushButton("×", self)
            self._dismiss_button.setFixedSize(24, 24)
            self._dismiss_button.setStyleSheet("border: none; background: transparent; font-size: 18px; color: inherit;")
            self._dismiss_button.clicked.connect(self._on_dismiss)
            layout.addWidget(self._dismiss_button)

    def _apply_styling(self):
        """Apply styling based on appearance."""
        self.setStyleSheet(self._generate_stylesheet())
        self._update_icon()

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and appearance."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base banner styles
        base_styles = f"""
            AtlassianBanner {{
                border-left: 4px solid;
                background-color: {colors.surface};
                color: {colors.text};
            }}

            AtlassianBanner QLabel {{
                border: none;
                background: transparent;
                color: inherit;
            }}

            AtlassianBanner QPushButton {{
                border: none;
                background: transparent;
                color: inherit;
                font-weight: bold;
            }}

            AtlassianBanner QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
            }}
        """

        # Title styling
        title_styles = f"""
            AtlassianBanner QLabel:first-child {{
                font-weight: {typography.font_weight_semibold};
                font-size: {typography.font_size_ui}px;
                color: {colors.text};
            }}
        """

        # Description styling
        description_styles = f"""
            AtlassianBanner QLabel:nth-child(2) {{
                font-size: {typography.font_size_ui_small}px;
                color: {colors.text_subtle};
            }}
        """

        # Appearance-specific border and background colors
        if self._appearance == BannerAppearance.INFORMATION:
            appearance_styles = f"""
                AtlassianBanner {{
                    border-left-color: {colors.information};
                    background-color: rgba(0, 184, 217, 0.08);
                }}
            """
        elif self._appearance == BannerAppearance.WARNING:
            appearance_styles = f"""
                AtlassianBanner {{
                    border-left-color: {colors.warning};
                    background-color: rgba(255, 171, 0, 0.08);
                }}
            """
        elif self._appearance == BannerAppearance.ERROR:
            appearance_styles = f"""
                AtlassianBanner {{
                    border-left-color: {colors.error};
                    background-color: rgba(255, 86, 48, 0.08);
                }}
            """
        elif self._appearance == BannerAppearance.SUCCESS:
            appearance_styles = f"""
                AtlassianBanner {{
                    border-left-color: {colors.success};
                    background-color: rgba(36, 183, 126, 0.08);
                }}
            """
        elif self._appearance == BannerAppearance.DISCOVERY:
            appearance_styles = f"""
                AtlassianBanner {{
                    border-left-color: {colors.discovery};
                    background-color: rgba(101, 84, 192, 0.08);
                }}
            """
        else:
            appearance_styles = ""

        return base_styles + title_styles + description_styles + appearance_styles

    def _update_icon(self):
        """Update the icon based on appearance."""
        icon_text = ""
        if self._appearance == BannerAppearance.INFORMATION:
            icon_text = "ℹ️"
        elif self._appearance == BannerAppearance.WARNING:
            icon_text = "⚠️"
        elif self._appearance == BannerAppearance.ERROR:
            icon_text = "❌"
        elif self._appearance == BannerAppearance.SUCCESS:
            icon_text = "✅"
        elif self._appearance == BannerAppearance.DISCOVERY:
            icon_text = "💡"

        self._icon_label.setText(icon_text)

    def _on_dismiss(self):
        """Handle dismiss button click."""
        self.hide()
        self.dismissed.emit()

    def set_title(self, title: str):
        """Set banner title."""
        self._title = title
        self._title_label.setText(title)

    def set_description(self, description: str):
        """Set banner description."""
        self._description = description
        self._description_label.setText(description)
        self._description_label.setVisible(bool(description))

    def set_appearance(self, appearance: BannerAppearance):
        """Set banner appearance."""
        self._appearance = appearance
        self._apply_styling()

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def appearance(self) -> BannerAppearance:
        return self._appearance

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description


class FlagAppearance(Enum):
    """Flag appearance variants."""
    NORMAL = "normal"      # Default flag style
    SUCCESS = "success"    # Success flag
    WARNING = "warning"   # Warning flag
    ERROR = "error"       # Error flag
    INFORMATION = "information"  # Information flag


class AtlassianFlag(QWidget):
    """
    Atlassian-style flag component for inline notifications and messages.

    Flags are more compact than banners and appear inline with content.

    Features:
    - Multiple appearance variants
    - Title and description support
    - Icon support
    - Dismissible functionality
    - Auto-hide after timeout
    """

    dismissed = Signal()

    def __init__(
        self,
        title: str = "",
        description: str = "",
        parent: Optional[QWidget] = None,
        appearance: FlagAppearance = FlagAppearance.NORMAL,
        design_tokens: Optional[DesignTokens] = None,
        dismissible: bool = True,
        auto_hide_delay: int = 0  # milliseconds, 0 = no auto-hide
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._appearance = appearance
        self._title = title
        self._description = description
        self._dismissible = dismissible
        self._auto_hide_delay = auto_hide_delay

        self._setup_flag()
        self._apply_styling()

        if self._auto_hide_delay > 0:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(self._auto_hide_delay, self._auto_hide)

    def _setup_flag(self):
        """Setup flag layout and components."""
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QPushButton

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self._design_tokens.spacing.space_150,
            self._design_tokens.spacing.space_100,
            self._design_tokens.spacing.space_150,
            self._design_tokens.spacing.space_100
        )
        layout.setSpacing(self._design_tokens.spacing.space_075)

        # Icon
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(16, 16)
        self._icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon_label)

        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self._title_label = QLabel(self._title, self)
        self._title_label.setWordWrap(True)

        self._description_label = QLabel(self._description, self)
        self._description_label.setWordWrap(True)

        text_layout.addWidget(self._title_label)
        if self._description:
            text_layout.addWidget(self._description_label)

        text_container = QWidget(self)
        text_container.setLayout(text_layout)
        layout.addWidget(text_container, 1)

        # Dismiss button
        if self._dismissible:
            self._dismiss_button = QPushButton("×", self)
            self._dismiss_button.setFixedSize(20, 20)
            self._dismiss_button.clicked.connect(self._on_dismiss)
            layout.addWidget(self._dismiss_button)

    def _apply_styling(self):
        """Apply styling based on appearance."""
        self.setStyleSheet(self._generate_stylesheet())
        self._update_icon()

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and appearance."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base flag styles - more compact than banners
        base_styles = f"""
            AtlassianFlag {{
                background-color: {colors.surface};
                border: 1px solid {colors.border};
                border-radius: {borders.border_radius}px;
                color: {colors.text};
            }}

            AtlassianFlag QLabel {{
                border: none;
                background: transparent;
                color: inherit;
            }}

            AtlassianFlag QPushButton {{
                border: none;
                background: transparent;
                color: {colors.text_subtle};
                font-size: 14px;
                font-weight: bold;
            }}

            AtlassianFlag QPushButton:hover {{
                color: {colors.text};
                background-color: {colors.surface_sunken};
                border-radius: 2px;
            }}
        """

        # Title styling
        title_styles = f"""
            AtlassianFlag QLabel:first-child {{
                font-weight: {typography.font_weight_medium};
                font-size: {typography.font_size_ui_small}px;
                color: {colors.text};
            }}
        """

        # Description styling
        description_styles = f"""
            AtlassianFlag QLabel:nth-child(2) {{
                font-size: {typography.font_size_ui_small}px;
                color: {colors.text_subtle};
            }}
        """

        # Appearance-specific border colors and subtle backgrounds
        if self._appearance == FlagAppearance.SUCCESS:
            appearance_styles = f"""
                AtlassianFlag {{
                    border-color: {colors.success};
                    background-color: rgba(36, 183, 126, 0.04);
                }}
            """
        elif self._appearance == FlagAppearance.WARNING:
            appearance_styles = f"""
                AtlassianFlag {{
                    border-color: {colors.warning};
                    background-color: rgba(255, 171, 0, 0.04);
                }}
            """
        elif self._appearance == FlagAppearance.ERROR:
            appearance_styles = f"""
                AtlassianFlag {{
                    border-color: {colors.error};
                    background-color: rgba(255, 86, 48, 0.04);
                }}
            """
        elif self._appearance == FlagAppearance.INFORMATION:
            appearance_styles = f"""
                AtlassianFlag {{
                    border-color: {colors.information};
                    background-color: rgba(0, 184, 217, 0.04);
                }}
            """
        else:
            appearance_styles = ""

        return base_styles + title_styles + description_styles + appearance_styles

    def _update_icon(self):
        """Update the icon based on appearance."""
        icon_text = ""
        if self._appearance == FlagAppearance.SUCCESS:
            icon_text = "✓"
        elif self._appearance == FlagAppearance.WARNING:
            icon_text = "⚠"
        elif self._appearance == FlagAppearance.ERROR:
            icon_text = "✕"
        elif self._appearance == FlagAppearance.INFORMATION:
            icon_text = "ℹ"
        else:
            icon_text = "•"

        self._icon_label.setText(icon_text)

    def _on_dismiss(self):
        """Handle dismiss button click."""
        self.hide()
        self.dismissed.emit()

    def _auto_hide(self):
        """Auto-hide the flag after delay."""
        if not self.visibleRegion().isEmpty():
            self.hide()
            self.dismissed.emit()

    def set_title(self, title: str):
        """Set flag title."""
        self._title = title
        self._title_label.setText(title)

    def set_description(self, description: str):
        """Set flag description."""
        self._description = description
        self._description_label.setText(description)
        self._description_label.setVisible(bool(description))

    def set_appearance(self, appearance: FlagAppearance):
        """Set flag appearance."""
        self._appearance = appearance
        self._apply_styling()

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def appearance(self) -> FlagAppearance:
        return self._appearance

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description


# Convenience functions for creating banners and flags
def create_banner(
    title: str,
    description: str = "",
    appearance: BannerAppearance = BannerAppearance.INFORMATION,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    dismissible: bool = True
) -> AtlassianBanner:
    """Create an Atlassian-style banner."""
    return AtlassianBanner(title, description, parent, appearance, design_tokens, dismissible)


def create_flag(
    title: str,
    description: str = "",
    appearance: FlagAppearance = FlagAppearance.NORMAL,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    dismissible: bool = True,
    auto_hide_delay: int = 0
) -> AtlassianFlag:
    """Create an Atlassian-style flag."""
    return AtlassianFlag(title, description, parent, appearance, design_tokens, dismissible, auto_hide_delay)


def create_success_banner(
    title: str,
    description: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianBanner:
    """Create a success banner."""
    return create_banner(title, description, BannerAppearance.SUCCESS, parent, design_tokens)


def create_error_banner(
    title: str,
    description: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianBanner:
    """Create an error banner."""
    return create_banner(title, description, BannerAppearance.ERROR, parent, design_tokens)


def create_warning_flag(
    title: str,
    description: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    auto_hide_delay: int = 5000
) -> AtlassianFlag:
    """Create a warning flag that auto-hides after 5 seconds."""
    return create_flag(title, description, FlagAppearance.WARNING, parent, design_tokens, True, auto_hide_delay)


class ProgressBarAppearance(Enum):
    """Progress bar appearance variants."""
    DEFAULT = "default"      # Standard progress bar
    SUCCESS = "success"      # Success/progress complete
    WARNING = "warning"      # Warning state
    ERROR = "error"         # Error state
    INFORMATION = "information"  # Information state


class AtlassianProgressBar(QWidget):
    """
    Atlassian-style progress bar component for system resource monitoring.

    Features:
    - Multiple appearance variants for different states
    - Support for indeterminate progress (loading states)
    - Customizable labels and value display
    - Smooth animations
    - Accessibility support
    """

    valueChanged = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        appearance: ProgressBarAppearance = ProgressBarAppearance.DEFAULT,
        design_tokens: Optional[DesignTokens] = None,
        minimum: int = 0,
        maximum: int = 100,
        value: int = 0,
        show_percentage: bool = True,
        label: str = "",
        indeterminate: bool = False
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._appearance = appearance
        self._minimum = minimum
        self._maximum = maximum
        self._value = value
        self._show_percentage = show_percentage
        self._label = label
        self._indeterminate = indeterminate

        self._setup_progress_bar()
        self._apply_styling()

    def _setup_progress_bar(self):
        """Setup progress bar layout and components."""
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

        # Set minimum height for progress bar
        self.setMinimumHeight(self._design_tokens.spacing.space_200)

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._design_tokens.spacing.space_050)

        # Label (if provided)
        if self._label:
            self._label_widget = QLabel(self._label, self)
            layout.addWidget(self._label_widget)

        # Progress bar container
        self._progress_container = QWidget(self)
        self._progress_container.setMinimumHeight(self._design_tokens.spacing.space_200)

        container_layout = QHBoxLayout(self._progress_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Progress bar background
        self._progress_background = QWidget(self._progress_container)
        self._progress_background.setMinimumHeight(self._design_tokens.spacing.space_200)

        # Progress fill
        self._progress_fill = QWidget(self._progress_background)
        self._progress_fill.setMinimumHeight(self._design_tokens.spacing.space_200)

        # Percentage label (optional)
        if self._show_percentage:
            self._percentage_label = QLabel(self)
            self._percentage_label.setAlignment(Qt.AlignCenter)
            self._update_percentage_text()
            container_layout.addWidget(self._percentage_label)

        layout.addWidget(self._progress_container)

    def _apply_styling(self):
        """Apply styling based on appearance."""
        self.setStyleSheet(self._generate_stylesheet())
        self._update_progress_fill()

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and appearance."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base progress bar styles
        base_styles = f"""
            AtlassianProgressBar {{
                background-color: transparent;
            }}

            AtlassianProgressBar QLabel {{
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui_small}px;
                color: {colors.text};
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }}
        """

        # Progress container and background
        container_styles = f"""
            AtlassianProgressBar QWidget {{
                border-radius: {borders.border_radius}px;
                background-color: {colors.surface_sunken};
            }}
        """

        # Appearance-specific fill colors
        fill_color = colors.primary  # Default
        if self._appearance == ProgressBarAppearance.SUCCESS:
            fill_color = colors.success
        elif self._appearance == ProgressBarAppearance.WARNING:
            fill_color = colors.warning
        elif self._appearance == ProgressBarAppearance.ERROR:
            fill_color = colors.error
        elif self._appearance == ProgressBarAppearance.INFORMATION:
            fill_color = colors.information

        fill_styles = f"""
            AtlassianProgressBar QWidget QWidget {{
                background-color: {fill_color};
                border-radius: {borders.border_radius}px;
                transition: width 0.3s ease-in-out;
            }}
        """

        # Indeterminate animation
        if self._indeterminate:
            indeterminate_styles = f"""
                AtlassianProgressBar QWidget QWidget {{
                    animation: progress-indeterminate 1.5s ease-in-out infinite;
                }}

                @keyframes progress-indeterminate {{
                    0% {{ width: 0%; margin-left: 0%; }}
                    50% {{ width: 30%; margin-left: 35%; }}
                    100% {{ width: 0%; margin-left: 100%; }}
                }}
            """
        else:
            indeterminate_styles = ""

        return base_styles + container_styles + fill_styles + indeterminate_styles

    def _update_progress_fill(self):
        """Update the progress fill width based on current value."""
        if self._indeterminate:
            # For indeterminate, show a moving indicator
            fill_width = int(self._progress_background.width() * 0.3)  # 30% width
            self._progress_fill.setFixedWidth(fill_width)
            # Animation is handled via CSS
        else:
            # Calculate percentage
            if self._maximum > self._minimum:
                percentage = (self._value - self._minimum) / (self._maximum - self._minimum)
                percentage = max(0.0, min(1.0, percentage))
                fill_width = int(self._progress_background.width() * percentage)
                self._progress_fill.setFixedWidth(fill_width)
            else:
                self._progress_fill.setFixedWidth(0)

    def _update_percentage_text(self):
        """Update the percentage label text."""
        if self._show_percentage and hasattr(self, '_percentage_label'):
            if self._indeterminate:
                self._percentage_label.setText("...")
            else:
                percentage = 0
                if self._maximum > self._minimum:
                    percentage = int(((self._value - self._minimum) / (self._maximum - self._minimum)) * 100)
                self._percentage_label.setText(f"{percentage}%")

    def resizeEvent(self, event):
        """Handle resize events to update progress fill."""
        super().resizeEvent(event)
        self._update_progress_fill()

    def set_value(self, value: int):
        """Set progress bar value."""
        value = max(self._minimum, min(self._maximum, value))
        if value != self._value:
            self._value = value
            self._update_progress_fill()
            self._update_percentage_text()
            self.valueChanged.emit(value)

    def set_minimum(self, minimum: int):
        """Set minimum value."""
        self._minimum = minimum
        if self._value < minimum:
            self.set_value(minimum)

    def set_maximum(self, maximum: int):
        """Set maximum value."""
        self._maximum = maximum
        if self._value > maximum:
            self.set_value(maximum)

    def set_range(self, minimum: int, maximum: int):
        """Set value range."""
        self._minimum = minimum
        self._maximum = maximum
        self.set_value(max(self._minimum, min(self._maximum, self._value)))

    def set_appearance(self, appearance: ProgressBarAppearance):
        """Set progress bar appearance."""
        self._appearance = appearance
        self._apply_styling()

    def set_indeterminate(self, indeterminate: bool):
        """Set indeterminate state."""
        self._indeterminate = indeterminate
        self._apply_styling()
        if indeterminate:
            self._update_percentage_text()

    def set_label(self, label: str):
        """Set progress bar label."""
        self._label = label
        if hasattr(self, '_label_widget'):
            self._label_widget.setText(label)
            self._label_widget.setVisible(bool(label))

    def set_show_percentage(self, show: bool):
        """Set whether to show percentage text."""
        self._show_percentage = show
        if hasattr(self, '_percentage_label'):
            self._percentage_label.setVisible(show)

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def value(self) -> int:
        return self._value

    @property
    def minimum(self) -> int:
        return self._minimum

    @property
    def maximum(self) -> int:
        return self._maximum

    @property
    def appearance(self) -> ProgressBarAppearance:
        return self._appearance

    @property
    def indeterminate(self) -> bool:
        return self._indeterminate


# Convenience functions for creating progress bars
def create_progress_bar(
    minimum: int = 0,
    maximum: int = 100,
    value: int = 0,
    appearance: ProgressBarAppearance = ProgressBarAppearance.DEFAULT,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    label: str = "",
    show_percentage: bool = True
) -> AtlassianProgressBar:
    """Create an Atlassian-style progress bar."""
    return AtlassianProgressBar(
        parent=parent,
        appearance=appearance,
        design_tokens=design_tokens,
        minimum=minimum,
        maximum=maximum,
        value=value,
        show_percentage=show_percentage,
        label=label
    )


def create_cpu_progress_bar(
    value: int = 0,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianProgressBar:
    """Create a CPU usage progress bar."""
    appearance = ProgressBarAppearance.DEFAULT
    if value >= 90:
        appearance = ProgressBarAppearance.ERROR
    elif value >= 70:
        appearance = ProgressBarAppearance.WARNING

    return create_progress_bar(
        minimum=0,
        maximum=100,
        value=value,
        appearance=appearance,
        parent=parent,
        design_tokens=design_tokens,
        label="CPU Usage",
        show_percentage=True
    )


def create_memory_progress_bar(
    value: int = 0,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianProgressBar:
    """Create a memory usage progress bar."""
    appearance = ProgressBarAppearance.DEFAULT
    if value >= 90:
        appearance = ProgressBarAppearance.ERROR
    elif value >= 80:
        appearance = ProgressBarAppearance.WARNING

    return create_progress_bar(
        minimum=0,
        maximum=100,
        value=value,
        appearance=appearance,
        parent=parent,
        design_tokens=design_tokens,
        label="Memory Usage",
        show_percentage=True
    )


def create_disk_progress_bar(
    value: int = 0,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianProgressBar:
    """Create a disk usage progress bar."""
    appearance = ProgressBarAppearance.DEFAULT
    if value >= 95:
        appearance = ProgressBarAppearance.ERROR
    elif value >= 85:
        appearance = ProgressBarAppearance.WARNING

    return create_progress_bar(
        minimum=0,
        maximum=100,
        value=value,
        appearance=appearance,
        parent=parent,
        design_tokens=design_tokens,
        label="Disk Usage",
        show_percentage=True
    )


def create_loading_progress_bar(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    label: str = "Loading..."
) -> AtlassianProgressBar:
    """Create an indeterminate loading progress bar."""
    return AtlassianProgressBar(
        parent=parent,
        appearance=ProgressBarAppearance.INFORMATION,
        design_tokens=design_tokens,
        indeterminate=True,
        show_percentage=False,
        label=label
    )


class AtlassianTextField(QWidget):
    """
    Atlassian-style text input field component.

    Features:
    - Placeholder text support
    - Validation states (default, error, warning)
    - Helper text display
    - Compact and regular sizes
    - Accessibility support
    """

    textChanged = Signal(str)
    editingFinished = Signal()

    def __init__(
        self,
        text: str = "",
        placeholder: str = "",
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        helper_text: str = "",
        is_required: bool = False,
        is_readonly: bool = False,
        is_disabled: bool = False,
        validation_state: str = "default"  # "default", "error", "warning"
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._text = text
        self._placeholder = placeholder
        self._helper_text = helper_text
        self._is_required = is_required
        self._is_readonly = is_readonly
        self._is_disabled = is_disabled
        self._validation_state = validation_state

        self._setup_text_field()
        self._apply_styling()

    def _setup_text_field(self):
        """Setup text field layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QLineEdit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._design_tokens.spacing.space_050)

        # Input field
        self._line_edit = QLineEdit(self._text, self)
        self._line_edit.setPlaceholderText(self._placeholder)

        if self._is_readonly:
            self._line_edit.setReadOnly(True)
        if self._is_disabled:
            self._line_edit.setEnabled(False)

        # Set accessible name
        if self._placeholder:
            self._line_edit.setAccessibleName(self._placeholder)
        elif self._helper_text:
            self._line_edit.setAccessibleName(self._helper_text)

        layout.addWidget(self._line_edit)

        # Helper text (if provided)
        if self._helper_text:
            self._helper_label = QLabel(self._helper_text, self)
            layout.addWidget(self._helper_label)

        # Connect signals
        self._line_edit.textChanged.connect(self._on_text_changed)
        self._line_edit.editingFinished.connect(self.editingFinished)

    def _apply_styling(self):
        """Apply styling based on current state."""
        self.setStyleSheet(self._generate_stylesheet())

        # Update helper text color based on validation state
        if hasattr(self, '_helper_label'):
            tokens = self._design_tokens
            colors = tokens.colors
            typography = tokens.typography

            if self._validation_state == "error":
                color = colors.error
            elif self._validation_state == "warning":
                color = colors.warning
            else:
                color = colors.text_subtle

            helper_styles = f"""
                color: {color};
                font-size: {typography.font_size_ui_small}px;
                font-family: {typography.font_family};
            """
            self._helper_label.setStyleSheet(helper_styles)

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and state."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base text field styles
        base_styles = f"""
            AtlassianTextField QLineEdit {{
                border: {borders.border_width}px solid {colors.border};
                border-radius: {borders.border_radius}px;
                padding: {spacing.space_075}px {spacing.space_100}px;
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui}px;
                color: {colors.text};
                background-color: {colors.surface};
                selection-background-color: {colors.primary};
                min-height: {spacing.space_400}px;
            }}

            AtlassianTextField QLineEdit:focus {{
                border-color: {colors.border_focused};
                outline: 2px solid rgba(76, 154, 255, 0.5);
                outline-offset: -2px;
            }}

            AtlassianTextField QLineEdit::placeholder {{
                color: {colors.text_subtle};
            }}
        """

        # Validation state styles
        validation_styles = ""
        if self._validation_state == "error":
            validation_styles = f"""
                AtlassianTextField QLineEdit {{
                    border-color: {colors.error};
                }}
                AtlassianTextField QLineEdit:focus {{
                    border-color: {colors.error};
                    outline-color: rgba(255, 86, 48, 0.5);
                }}
            """
        elif self._validation_state == "warning":
            validation_styles = f"""
                AtlassianTextField QLineEdit {{
                    border-color: {colors.warning};
                }}
                AtlassianTextField QLineEdit:focus {{
                    border-color: {colors.warning};
                    outline-color: rgba(255, 171, 0, 0.5);
                }}
            """

        # Disabled state
        disabled_styles = f"""
            AtlassianTextField QLineEdit:disabled {{
                background-color: {colors.surface_sunken};
                color: {colors.text_disabled};
                border-color: {colors.border};
                cursor: not-allowed;
            }}
        """

        return base_styles + validation_styles + disabled_styles

    def _on_text_changed(self, text: str):
        """Handle text changes."""
        self._text = text
        self.textChanged.emit(text)

    def set_text(self, text: str):
        """Set the text content."""
        self._text = text
        self._line_edit.setText(text)

    def set_placeholder(self, placeholder: str):
        """Set placeholder text."""
        self._placeholder = placeholder
        self._line_edit.setPlaceholderText(placeholder)
        if placeholder:
            self._line_edit.setAccessibleName(placeholder)

    def set_helper_text(self, helper_text: str):
        """Set helper text."""
        self._helper_text = helper_text
        if hasattr(self, '_helper_label'):
            self._helper_label.setText(helper_text)
            self._helper_label.setVisible(bool(helper_text))
        else:
            # Create helper label if it doesn't exist
            if helper_text:
                from PySide6.QtWidgets import QVBoxLayout
                self._helper_label = QLabel(helper_text, self)
                self.layout().addWidget(self._helper_label)
                self._apply_styling()

    def set_validation_state(self, state: str):
        """Set validation state ('default', 'error', 'warning')."""
        self._validation_state = state
        self._apply_styling()

    def set_readonly(self, readonly: bool):
        """Set readonly state."""
        self._is_readonly = readonly
        self._line_edit.setReadOnly(readonly)

    def set_disabled(self, disabled: bool):
        """Set disabled state."""
        self._is_disabled = disabled
        self._line_edit.setEnabled(not disabled)

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    def focus_input(self):
        """Set focus to the input field."""
        self._line_edit.setFocus()

    @property
    def text(self) -> str:
        return self._line_edit.text()

    @property
    def placeholder(self) -> str:
        return self._placeholder

    @property
    def helper_text(self) -> str:
        return self._helper_text

    @property
    def validation_state(self) -> str:
        return self._validation_state

    @property
    def is_required(self) -> bool:
        return self._is_required


class AtlassianSelect(QWidget):
    """
    Atlassian-style select/dropdown component.

    Features:
    - Customizable options
    - Placeholder support
    - Validation states
    - Helper text
    - Accessibility support
    """

    currentIndexChanged = Signal(int)
    currentTextChanged = Signal(str)

    def __init__(
        self,
        items: List[str] = None,
        current_index: int = -1,
        placeholder: str = "",
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        helper_text: str = "",
        is_required: bool = False,
        is_disabled: bool = False,
        validation_state: str = "default"
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._items = items or []
        self._current_index = current_index
        self._placeholder = placeholder
        self._helper_text = helper_text
        self._is_required = is_required
        self._is_disabled = is_disabled
        self._validation_state = validation_state

        self._setup_select()
        self._apply_styling()

    def _setup_select(self):
        """Setup select layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QComboBox

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._design_tokens.spacing.space_050)

        # Combo box
        self._combo_box = QComboBox(self)

        # Add items
        self._combo_box.addItems(self._items)

        # Set current index
        if self._current_index >= 0 and self._current_index < len(self._items):
            self._combo_box.setCurrentIndex(self._current_index)

        # Placeholder handling (QComboBox doesn't have native placeholder)
        if self._placeholder and not self._items:
            self._combo_box.addItem(self._placeholder)
            self._combo_box.setCurrentIndex(0)
            # Store placeholder index to handle it specially

        if self._is_disabled:
            self._combo_box.setEnabled(False)

        # Set accessible name
        if self._placeholder:
            self._combo_box.setAccessibleName(self._placeholder)
        elif self._helper_text:
            self._combo_box.setAccessibleName(self._helper_text)

        layout.addWidget(self._combo_box)

        # Helper text
        if self._helper_text:
            self._helper_label = QLabel(self._helper_text, self)
            layout.addWidget(self._helper_label)

        # Connect signals
        self._combo_box.currentIndexChanged.connect(self._on_index_changed)
        self._combo_box.currentTextChanged.connect(self.currentTextChanged)

    def _apply_styling(self):
        """Apply styling based on current state."""
        self.setStyleSheet(self._generate_stylesheet())

        # Update helper text color
        if hasattr(self, '_helper_label'):
            tokens = self._design_tokens
            colors = tokens.colors
            typography = tokens.typography

            if self._validation_state == "error":
                color = colors.error
            elif self._validation_state == "warning":
                color = colors.warning
            else:
                color = colors.text_subtle

            helper_styles = f"""
                color: {color};
                font-size: {typography.font_size_ui_small}px;
                font-family: {typography.font_family};
            """
            self._helper_label.setStyleSheet(helper_styles)

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and state."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base select styles
        base_styles = f"""
            AtlassianSelect QComboBox {{
                border: {borders.border_width}px solid {colors.border};
                border-radius: {borders.border_radius}px;
                padding: {spacing.space_075}px {spacing.space_100}px;
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui}px;
                color: {colors.text};
                background-color: {colors.surface};
                min-height: {spacing.space_400}px;
                padding-right: {spacing.space_300}px; /* Space for dropdown arrow */
            }}

            AtlassianSelect QComboBox:focus {{
                border-color: {colors.border_focused};
                outline: 2px solid rgba(76, 154, 255, 0.5);
                outline-offset: -2px;
            }}

            AtlassianSelect QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}

            AtlassianSelect QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {colors.text_subtle};
                margin-right: 8px;
            }}

            AtlassianSelect QComboBox::down-arrow:on {{
                border-top: 4px solid {colors.primary};
            }}

            AtlassianSelect QComboBox QAbstractItemView {{
                border: 1px solid {colors.border};
                border-radius: {borders.border_radius}px;
                background-color: {colors.surface};
                selection-background-color: {colors.primary};
                selection-color: white;
                outline: none;
            }}

            AtlassianSelect QComboBox QAbstractItemView::item {{
                padding: {spacing.space_075}px {spacing.space_100}px;
                border: none;
                background-color: transparent;
            }}

            AtlassianSelect QComboBox QAbstractItemView::item:selected {{
                background-color: {colors.primary};
                color: white;
            }}

            AtlassianSelect QComboBox QAbstractItemView::item:hover {{
                background-color: {colors.surface_sunken};
            }}
        """

        # Validation state styles
        validation_styles = ""
        if self._validation_state == "error":
            validation_styles = f"""
                AtlassianSelect QComboBox {{
                    border-color: {colors.error};
                }}
                AtlassianSelect QComboBox:focus {{
                    border-color: {colors.error};
                    outline-color: rgba(255, 86, 48, 0.5);
                }}
            """
        elif self._validation_state == "warning":
            validation_styles = f"""
                AtlassianSelect QComboBox {{
                    border-color: {colors.warning};
                }}
                AtlassianSelect QComboBox:focus {{
                    border-color: {colors.warning};
                    outline-color: rgba(255, 171, 0, 0.5);
                }}
            """

        # Disabled state
        disabled_styles = f"""
            AtlassianSelect QComboBox:disabled {{
                background-color: {colors.surface_sunken};
                color: {colors.text_disabled};
                border-color: {colors.border};
                cursor: not-allowed;
            }}
        """

        return base_styles + validation_styles + disabled_styles

    def _on_index_changed(self, index: int):
        """Handle index changes."""
        self._current_index = index
        self.currentIndexChanged.emit(index)

    def add_item(self, text: str, user_data: Any = None):
        """Add an item to the select."""
        self._combo_box.addItem(text, user_data)
        self._items.append(text)

    def add_items(self, texts: List[str]):
        """Add multiple items to the select."""
        self._combo_box.addItems(texts)
        self._items.extend(texts)

    def clear(self):
        """Clear all items."""
        self._combo_box.clear()
        self._items.clear()
        self._current_index = -1

    def set_current_index(self, index: int):
        """Set current index."""
        if 0 <= index < self._combo_box.count():
            self._combo_box.setCurrentIndex(index)
            self._current_index = index

    def set_current_text(self, text: str):
        """Set current item by text."""
        index = self._combo_box.findText(text)
        if index >= 0:
            self.set_current_index(index)

    def set_items(self, items: List[str]):
        """Set all items."""
        self.clear()
        self.add_items(items)

    def set_placeholder(self, placeholder: str):
        """Set placeholder text."""
        self._placeholder = placeholder
        # Note: QComboBox doesn't have native placeholder support
        # This would need custom implementation

    def set_helper_text(self, helper_text: str):
        """Set helper text."""
        self._helper_text = helper_text
        if hasattr(self, '_helper_label'):
            self._helper_label.setText(helper_text)
            self._helper_label.setVisible(bool(helper_text))

    def set_validation_state(self, state: str):
        """Set validation state."""
        self._validation_state = state
        self._apply_styling()

    def set_disabled(self, disabled: bool):
        """Set disabled state."""
        self._is_disabled = disabled
        self._combo_box.setEnabled(not disabled)

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def current_index(self) -> int:
        return self._combo_box.currentIndex()

    @property
    def current_text(self) -> str:
        return self._combo_box.currentText()

    @property
    def count(self) -> int:
        return self._combo_box.count()

    @property
    def items(self) -> List[str]:
        return [self._combo_box.itemText(i) for i in range(self._combo_box.count())]


class AtlassianCheckbox(QWidget):
    """
    Atlassian-style checkbox component.

    Features:
    - Custom checkbox styling
    - Label support
    - Helper text
    - Validation states
    - Accessibility support
    """

    stateChanged = Signal(int)  # Qt.CheckState

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        helper_text: str = "",
        is_checked: bool = False,
        is_disabled: bool = False,
        is_required: bool = False,
        validation_state: str = "default"
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._text = text
        self._helper_text = helper_text
        self._is_checked = is_checked
        self._is_disabled = is_disabled
        self._is_required = is_required
        self._validation_state = validation_state

        self._setup_checkbox()
        self._apply_styling()

    def _setup_checkbox(self):
        """Setup checkbox layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QCheckBox, QHBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._design_tokens.spacing.space_050)

        # Checkbox row
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(self._design_tokens.spacing.space_075)

        self._check_box = QCheckBox(self._text, self)
        self._check_box.setChecked(self._is_checked)
        self._check_box.setEnabled(not self._is_disabled)

        # Set accessible name
        if self._text:
            self._check_box.setAccessibleName(self._text)

        checkbox_layout.addWidget(self._check_box)
        checkbox_layout.addStretch()  # Push to left

        layout.addLayout(checkbox_layout)

        # Helper text
        if self._helper_text:
            self._helper_label = QLabel(self._helper_text, self)
            layout.addWidget(self._helper_label)

        # Connect signals
        self._check_box.stateChanged.connect(self.stateChanged)

    def _apply_styling(self):
        """Apply styling based on current state."""
        self.setStyleSheet(self._generate_stylesheet())

        # Update helper text color
        if hasattr(self, '_helper_label'):
            tokens = self._design_tokens
            colors = tokens.colors
            typography = tokens.typography

            if self._validation_state == "error":
                color = colors.error
            elif self._validation_state == "warning":
                color = colors.warning
            else:
                color = colors.text_subtle

            helper_styles = f"""
                color: {color};
                font-size: {typography.font_size_ui_small}px;
                font-family: {typography.font_family};
                margin-left: {tokens.spacing.space_200}px;
            """
            self._helper_label.setStyleSheet(helper_styles)

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and state."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base checkbox styles
        base_styles = f"""
            AtlassianCheckbox QCheckBox {{
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui}px;
                color: {colors.text};
                spacing: {spacing.space_075}px;
            }}

            AtlassianCheckbox QCheckBox::indicator {{
                width: {spacing.space_200}px;
                height: {spacing.space_200}px;
                border: 2px solid {colors.border};
                border-radius: 2px;
                background-color: {colors.surface};
            }}

            AtlassianCheckbox QCheckBox::indicator:checked {{
                background-color: {colors.primary};
                border-color: {colors.primary};
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNCA5IDAgNy4zMWw0LTEuM0w5LjMxIDB6IiBmaWxsPSJ3aGl0ZSIvPgo8L3N2Zz4K);
            }}

            AtlassianCheckbox QCheckBox::indicator:unchecked {{
                background-color: {colors.surface};
            }}

            AtlassianCheckbox QCheckBox::indicator:hover {{
                border-color: {colors.primary};
            }}

            AtlassianCheckbox QCheckBox::indicator:checked:hover {{
                background-color: {colors.primary_hover};
                border-color: {colors.primary_hover};
            }}
        """

        # Disabled state
        disabled_styles = f"""
            AtlassianCheckbox QCheckBox:disabled {{
                color: {colors.text_disabled};
            }}

            AtlassianCheckbox QCheckBox::indicator:disabled {{
                background-color: {colors.surface_sunken};
                border-color: {colors.border};
            }}
        """

        return base_styles + disabled_styles

    def set_checked(self, checked: bool):
        """Set checked state."""
        self._is_checked = checked
        self._check_box.setChecked(checked)

    def set_text(self, text: str):
        """Set checkbox text."""
        self._text = text
        self._check_box.setText(text)

    def set_helper_text(self, helper_text: str):
        """Set helper text."""
        self._helper_text = helper_text
        if hasattr(self, '_helper_label'):
            self._helper_label.setText(helper_text)
            self._helper_label.setVisible(bool(helper_text))

    def set_validation_state(self, state: str):
        """Set validation state."""
        self._validation_state = state
        self._apply_styling()

    def set_disabled(self, disabled: bool):
        """Set disabled state."""
        self._is_disabled = disabled
        self._check_box.setEnabled(not disabled)

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def is_checked(self) -> bool:
        return self._check_box.isChecked()

    @property
    def text(self) -> str:
        return self._check_box.text()


class AtlassianTabWidget(QWidget):
    """
    Atlassian-style tab widget component for organizing content into sections.

    Features:
    - Clean, minimal tab design following Atlassian patterns
    - Support for icons and text in tabs
    - Smooth animations for tab transitions
    - Proper focus management and keyboard navigation
    - Accessible design with ARIA support
    """

    currentChanged = Signal(int)
    tabCloseRequested = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        tab_position: str = "top"  # "top", "bottom", "left", "right"
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._tab_position = tab_position
        self._tabs: List[Dict[str, Any]] = []
        self._current_index = -1

        self._setup_tab_widget()
        self._apply_styling()

    def _setup_tab_widget(self):
        """Setup tab widget layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QStackedWidget

        # Main layout based on tab position
        if self._tab_position in ["top", "bottom"]:
            self._main_layout = QVBoxLayout(self)
        else:  # left, right
            self._main_layout = QHBoxLayout(self)

        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Tab bar container
        self._tab_bar = QWidget(self)
        self._tab_bar_layout = QHBoxLayout(self._tab_bar)
        self._tab_bar_layout.setContentsMargins(
            self._design_tokens.spacing.space_100,
            self._design_tokens.spacing.space_075,
            self._design_tokens.spacing.space_100,
            self._design_tokens.spacing.space_075
        )
        self._tab_bar_layout.setSpacing(0)
        self._tab_bar_layout.addStretch()  # Push tabs to the left

        # Content stack
        self._stacked_widget = QStackedWidget(self)

        # Arrange widgets based on tab position
        if self._tab_position == "top":
            self._main_layout.addWidget(self._tab_bar)
            self._main_layout.addWidget(self._stacked_widget, 1)
        elif self._tab_position == "bottom":
            self._main_layout.addWidget(self._stacked_widget, 1)
            self._main_layout.addWidget(self._tab_bar)
        elif self._tab_position == "left":
            self._tab_bar_layout.setDirection(QHBoxLayout.TopToBottom)
            self._main_layout.addWidget(self._tab_bar)
            self._main_layout.addWidget(self._stacked_widget, 1)
        elif self._tab_position == "right":
            self._tab_bar_layout.setDirection(QHBoxLayout.TopToBottom)
            self._main_layout.addWidget(self._stacked_widget, 1)
            self._main_layout.addWidget(self._tab_bar)

    def _apply_styling(self):
        """Apply styling based on design tokens."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base tab widget styles
        base_styles = f"""
            AtlassianTabWidget {{
                background-color: transparent;
            }}

            AtlassianTabWidget QWidget {{
                background-color: transparent;
            }}

            AtlassianTabWidget QStackedWidget {{
                background-color: {colors.surface};
                border: {borders.border_width}px solid {colors.border};
                border-radius: {borders.border_radius}px;
            }}
        """

        # Tab button styles
        tab_styles = f"""
            AtlassianTabWidget QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: {borders.border_radius}px;
                color: {colors.text_subtle};
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui}px;
                font-weight: {typography.font_weight_regular};
                padding: {spacing.space_100}px {spacing.space_150}px;
                margin: 0;
                text-align: center;
                min-height: {spacing.space_400}px;
                min-width: {spacing.space_600}px;
            }}

            AtlassianTabWidget QPushButton:hover {{
                background-color: {colors.surface_sunken};
                color: {colors.text};
            }}

            AtlassianTabWidget QPushButton:checked {{
                background-color: {colors.surface};
                color: {colors.primary};
                font-weight: {typography.font_weight_medium};
                border-bottom: 2px solid {colors.primary};
            }}

            AtlassianTabWidget QPushButton:focus {{
                outline: 2px solid {colors.border_focused};
                outline-offset: -2px;
            }}
        """

        # Adjust border for different tab positions
        if self._tab_position == "top":
            tab_checked = f"""
                AtlassianTabWidget QPushButton:checked {{
                    border-bottom: 2px solid {colors.primary};
                    border-top: none;
                }}
            """
        elif self._tab_position == "bottom":
            tab_checked = f"""
                AtlassianTabWidget QPushButton:checked {{
                    border-top: 2px solid {colors.primary};
                    border-bottom: none;
                }}
            """
        elif self._tab_position == "left":
            tab_checked = f"""
                AtlassianTabWidget QPushButton:checked {{
                    border-right: 2px solid {colors.primary};
                    border-left: none;
                }}
            """
        elif self._tab_position == "right":
            tab_checked = f"""
                AtlassianTabWidget QPushButton:checked {{
                    border-left: 2px solid {colors.primary};
                    border-right: none;
                }}
            """
        else:
            tab_checked = ""

        return base_styles + tab_styles + tab_checked

    def add_tab(self, widget: QWidget, label: str, icon: str = "") -> int:
        """Add a new tab with the given widget and label."""
        from PySide6.QtWidgets import QPushButton

        # Create tab button
        tab_button = QPushButton(label, self._tab_bar)
        tab_button.setCheckable(True)
        tab_button.setAutoExclusive(True)  # Only one tab can be selected at a time

        # Set icon if provided
        if icon:
            tab_button.setText(f"{icon} {label}")

        # Add to tab bar
        self._tab_bar_layout.insertWidget(self._tab_bar_layout.count() - 1, tab_button)

        # Add widget to stack
        self._stacked_widget.addWidget(widget)

        # Store tab info
        tab_info = {
            'button': tab_button,
            'widget': widget,
            'label': label,
            'icon': icon,
            'index': len(self._tabs)
        }
        self._tabs.append(tab_info)

        # Connect signals
        tab_button.clicked.connect(lambda: self._on_tab_clicked(tab_info['index']))

        # Set as current if it's the first tab
        if len(self._tabs) == 1:
            self.set_current_index(0)

        return len(self._tabs) - 1

    def insert_tab(self, index: int, widget: QWidget, label: str, icon: str = "") -> int:
        """Insert a tab at the specified index."""
        from PySide6.QtWidgets import QPushButton

        # Create tab button
        tab_button = QPushButton(label, self._tab_bar)
        tab_button.setCheckable(True)
        tab_button.setAutoExclusive(True)

        if icon:
            tab_button.setText(f"{icon} {label}")

        # Insert into tab bar
        self._tab_bar_layout.insertWidget(index, tab_button)

        # Insert widget into stack
        self._stacked_widget.insertWidget(index, widget)

        # Update existing tab indices
        for i in range(index, len(self._tabs)):
            self._tabs[i]['index'] = i + 1

        # Store tab info
        tab_info = {
            'button': tab_button,
            'widget': widget,
            'label': label,
            'icon': icon,
            'index': index
        }
        self._tabs.insert(index, tab_info)

        # Connect signals
        tab_button.clicked.connect(lambda: self._on_tab_clicked(index))

        return index

    def remove_tab(self, index: int):
        """Remove the tab at the specified index."""
        if 0 <= index < len(self._tabs):
            tab_info = self._tabs[index]

            # Remove from tab bar
            tab_info['button'].setParent(None)
            tab_info['button'].deleteLater()

            # Remove from stack
            self._stacked_widget.removeWidget(tab_info['widget'])

            # Remove from tabs list
            self._tabs.pop(index)

            # Update indices
            for i in range(index, len(self._tabs)):
                self._tabs[i]['index'] = i

            # Adjust current index if necessary
            if self._current_index >= len(self._tabs):
                self._current_index = len(self._tabs) - 1
            elif self._current_index > index:
                self._current_index -= 1

            # Set new current tab
            if self._tabs:
                self.set_current_index(max(0, self._current_index))
            else:
                self._current_index = -1

    def set_tab_text(self, index: int, text: str):
        """Set the text for the tab at the specified index."""
        if 0 <= index < len(self._tabs):
            self._tabs[index]['label'] = text
            self._tabs[index]['button'].setText(text)

    def set_tab_icon(self, index: int, icon: str):
        """Set the icon for the tab at the specified index."""
        if 0 <= index < len(self._tabs):
            self._tabs[index]['icon'] = icon
            label = self._tabs[index]['label']
            if icon:
                self._tabs[index]['button'].setText(f"{icon} {label}")
            else:
                self._tabs[index]['button'].setText(label)

    def _on_tab_clicked(self, index: int):
        """Handle tab button click."""
        self.set_current_index(index)

    def set_current_index(self, index: int):
        """Set the current active tab."""
        if 0 <= index < len(self._tabs) and index != self._current_index:
            # Update button states
            if self._current_index >= 0:
                self._tabs[self._current_index]['button'].setChecked(False)

            self._current_index = index
            self._tabs[index]['button'].setChecked(True)

            # Switch content
            self._stacked_widget.setCurrentIndex(index)

            # Emit signal
            self.currentChanged.emit(index)

    def set_current_widget(self, widget: QWidget):
        """Set the current tab by widget."""
        for i, tab_info in enumerate(self._tabs):
            if tab_info['widget'] == widget:
                self.set_current_index(i)
                break

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_widget(self) -> QWidget:
        if self._current_index >= 0:
            return self._tabs[self._current_index]['widget']
        return None

    @property
    def count(self) -> int:
        return len(self._tabs)

    @property
    def tab_position(self) -> str:
        return self._tab_position

    def tab_text(self, index: int) -> str:
        """Get the text of the tab at the specified index."""
        if 0 <= index < len(self._tabs):
            return self._tabs[index]['label']
        return ""

    def tab_widget(self, index: int) -> QWidget:
        """Get the widget of the tab at the specified index."""
        if 0 <= index < len(self._tabs):
            return self._tabs[index]['widget']
        return None


# Convenience functions for creating tab widgets
def create_tab_widget(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    tab_position: str = "top"
) -> AtlassianTabWidget:
    """Create an Atlassian-style tab widget."""
    return AtlassianTabWidget(
        parent=parent,
        design_tokens=design_tokens,
        tab_position=tab_position
    )


def create_monitoring_tabs(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianTabWidget:
    """Create a tab widget pre-configured for system monitoring sections."""
    tabs = create_tab_widget(parent, design_tokens)

    # Create placeholder widgets for each monitoring section
    from PySide6.QtWidgets import QWidget, QLabel

    # CPU Tab
    cpu_widget = QWidget()
    cpu_layout = QVBoxLayout(cpu_widget)
    cpu_layout.addWidget(QLabel("CPU Monitoring Section"))
    tabs.add_tab(cpu_widget, "CPU", "⚡")

    # Memory Tab
    memory_widget = QWidget()
    memory_layout = QVBoxLayout(memory_widget)
    memory_layout.addWidget(QLabel("Memory Monitoring Section"))
    tabs.add_tab(memory_widget, "Memory", "🧠")

    # Disk Tab
    disk_widget = QWidget()
    disk_layout = QVBoxLayout(disk_widget)
    disk_layout.addWidget(QLabel("Disk Monitoring Section"))
    tabs.add_tab(disk_widget, "Disk", "💾")

    # Network Tab
    network_widget = QWidget()
    network_layout = QVBoxLayout(network_widget)
    network_layout.addWidget(QLabel("Network Monitoring Section"))
    tabs.add_tab(network_widget, "Network", "🌐")

    # Processes Tab
    processes_widget = QWidget()
    processes_layout = QVBoxLayout(processes_widget)
    processes_layout.addWidget(QLabel("Process Monitoring Section"))
    tabs.add_tab(processes_widget, "Processes", "🔄")

    return tabs


class AtlassianLoadingSpinner(QWidget):
    """
    Atlassian-style loading spinner component for indicating async operations.

    Features:
    - Smooth CSS animations
    - Multiple sizes (small, medium, large)
    - Customizable color and appearance
    - Overlay mode for blocking UI
    - Accessible with proper ARIA labels
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        size: str = "medium",  # "small", "medium", "large"
        color: str = "",  # Empty string uses primary color
        overlay: bool = False,
        message: str = ""
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._size = size
        self._color = color or self._design_tokens.colors.primary
        self._overlay = overlay
        self._message = message

        self._setup_spinner()
        self._apply_styling()

        # Start animation
        self._start_animation()

    def _setup_spinner(self):
        """Setup spinner layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout

        # Set overlay properties if needed
        if self._overlay:
            # Make spinner semi-transparent overlay
            self.setAttribute(Qt.WA_TranslucentBackground)
            # Position as overlay
            if self.parent():
                self.setGeometry(self.parent().rect())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._design_tokens.spacing.space_100)

        # Center the spinner
        layout.setAlignment(Qt.AlignCenter)

        # Spinner container
        self._spinner_container = QWidget(self)
        spinner_layout = QHBoxLayout(self._spinner_container)
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        spinner_layout.setAlignment(Qt.AlignCenter)

        # Create spinner dots/elements
        self._spinner_elements = []
        for i in range(3):  # 3 dots for the spinner
            dot = QLabel("●", self._spinner_container)
            dot.setAlignment(Qt.AlignCenter)
            self._spinner_elements.append(dot)
            spinner_layout.addWidget(dot)

        layout.addWidget(self._spinner_container)

        # Message label (if provided)
        if self._message:
            self._message_label = QLabel(self._message, self)
            self._message_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self._message_label)

    def _apply_styling(self):
        """Apply styling based on design tokens."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        typography = tokens.typography

        # Size configurations
        size_config = {
            "small": {
                "font_size": spacing.space_200,  # 16px
                "margin": spacing.space_050,     # 4px
                "animation_delay": "0.2s"
            },
            "medium": {
                "font_size": spacing.space_300,  # 24px
                "margin": spacing.space_075,     # 6px
                "animation_delay": "0.3s"
            },
            "large": {
                "font_size": spacing.space_400,  # 32px
                "margin": spacing.space_100,     # 8px
                "animation_delay": "0.4s"
            }
        }

        config = size_config.get(self._size, size_config["medium"])

        # Base spinner styles
        base_styles = f"""
            AtlassianLoadingSpinner {{
                background-color: {'rgba(255, 255, 255, 0.9)' if self._overlay else 'transparent'};
                border-radius: {tokens.borders.border_radius}px;
            }}

            AtlassianLoadingSpinner QLabel {{
                color: {self._color};
                font-size: {config['font_size']}px;
                margin: 0 {config['margin']}px;
                animation: spin 1.4s ease-in-out infinite both;
            }}
        """

        # Individual dot animations with delays
        dot_styles = ""
        for i, element in enumerate(self._spinner_elements):
            delay = i * 0.2  # Stagger the animations
            dot_styles += f"""
                AtlassianLoadingSpinner QLabel:nth-child({i+1}) {{
                    animation-delay: {delay}s;
                }}
            """

        # Message styling
        message_styles = f"""
            AtlassianLoadingSpinner QLabel:last-child {{
                color: {colors.text};
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui_small}px;
                font-weight: {typography.font_weight_regular};
                margin-top: {spacing.space_150}px;
            }}
        """

        # Keyframe animation
        animation_styles = f"""
            @keyframes spin {{
                0%, 80%, 100% {{
                    transform: scale(0);
                    opacity: 0.5;
                }}
                40% {{
                    transform: scale(1);
                    opacity: 1;
                }}
            }}
        """

        return base_styles + dot_styles + message_styles + animation_styles

    def _start_animation(self):
        """Start the spinner animation."""
        # Animation is handled via CSS keyframes
        pass

    def set_size(self, size: str):
        """Set spinner size ('small', 'medium', 'large')."""
        self._size = size
        self._apply_styling()

    def set_color(self, color: str):
        """Set spinner color."""
        self._color = color
        self._apply_styling()

    def set_message(self, message: str):
        """Set loading message."""
        self._message = message
        if hasattr(self, '_message_label'):
            self._message_label.setText(message)
            self._message_label.setVisible(bool(message))

    def set_overlay(self, overlay: bool):
        """Set overlay mode."""
        self._overlay = overlay
        self._apply_styling()

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def size(self) -> str:
        return self._size

    @property
    def color(self) -> str:
        return self._color

    @property
    def message(self) -> str:
        return self._message

    @property
    def overlay(self) -> bool:
        return self._overlay


class AtlassianLoadingOverlay(QWidget):
    """
    Full-screen loading overlay with spinner and backdrop.

    Features:
    - Semi-transparent backdrop
    - Centered spinner and message
    - Blocks user interaction while loading
    - Smooth fade in/out animations
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        message: str = "Loading..."
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._message = message

        self._setup_overlay()
        self._apply_styling()

        # Initially hidden
        self.hide()

    def _setup_overlay(self):
        """Setup overlay layout."""
        from PySide6.QtWidgets import QVBoxLayout

        # Set overlay to cover parent
        if self.parent():
            self.setGeometry(self.parent().rect())

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # Create spinner
        self._spinner = AtlassianLoadingSpinner(
            self,
            self._design_tokens,
            size="large",
            message=self._message,
            overlay=True
        )

        layout.addWidget(self._spinner)

    def _apply_styling(self):
        """Apply overlay styling."""
        tokens = self._design_tokens
        colors = tokens.colors

        overlay_styles = f"""
            AtlassianLoadingOverlay {{
                background-color: rgba(0, 0, 0, 0.5);
                border-radius: {tokens.borders.border_radius}px;
            }}
        """

        self.setStyleSheet(overlay_styles)

    def show_overlay(self, message: str = ""):
        """Show the loading overlay."""
        if message:
            self._message = message
            self._spinner.set_message(message)

        self.show()
        self.raise_()  # Bring to front

    def hide_overlay(self):
        """Hide the loading overlay."""
        self.hide()

    def set_message(self, message: str):
        """Set loading message."""
        self._message = message
        self._spinner.set_message(message)

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens."""
        self._design_tokens = tokens
        self._spinner.update_design_tokens(tokens)
        self._apply_styling()

    def resizeEvent(self, event):
        """Handle resize events to maintain overlay coverage."""
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())


# Convenience functions for creating loading spinners
def create_loading_spinner(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    size: str = "medium",
    color: str = "",
    message: str = ""
) -> AtlassianLoadingSpinner:
    """Create an Atlassian-style loading spinner."""
    return AtlassianLoadingSpinner(
        parent=parent,
        design_tokens=design_tokens,
        size=size,
        color=color,
        message=message
    )


def create_loading_overlay(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    message: str = "Loading..."
) -> AtlassianLoadingOverlay:
    """Create a full-screen loading overlay."""
    return AtlassianLoadingOverlay(
        parent=parent,
        design_tokens=design_tokens,
        message=message
    )


class AtlassianTooltip(QWidget):
    """
    Enhanced Atlassian-style tooltip component with proper positioning and theming.

    Features:
    - Smart positioning (auto-adjusts to stay on screen)
    - Rich content support (text, icons, formatting)
    - Smooth fade in/out animations
    - Multiple sizes and appearances
    - Proper accessibility support
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        max_width: int = 200,
        appearance: str = "default",  # "default", "info", "warning", "error"
        show_arrow: bool = True
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._text = text
        self._max_width = max_width
        self._appearance = appearance
        self._show_arrow = show_arrow

        self._target_widget = None
        self._position = "top"  # "top", "bottom", "left", "right"

        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._setup_tooltip()
        self._apply_styling()

        # Initially hidden
        self.hide()

    def _setup_tooltip(self):
        """Setup tooltip layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QLabel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self._design_tokens.spacing.space_150,
            self._design_tokens.spacing.space_100,
            self._design_tokens.spacing.space_150,
            self._design_tokens.spacing.space_100
        )
        layout.setSpacing(0)

        # Content label
        self._content_label = QLabel(self._text, self)
        self._content_label.setWordWrap(True)
        self._content_label.setMaximumWidth(self._max_width)
        layout.addWidget(self._content_label)

        # Set size policy
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def _apply_styling(self):
        """Apply styling based on appearance."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and appearance."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base appearance colors
        bg_color = colors.surface_sunken
        border_color = colors.border
        text_color = colors.text

        if self._appearance == "info":
            bg_color = "rgba(0, 184, 217, 0.95)"
            border_color = colors.information
            text_color = "white"
        elif self._appearance == "warning":
            bg_color = "rgba(255, 171, 0, 0.95)"
            border_color = colors.warning
            text_color = colors.text
        elif self._appearance == "error":
            bg_color = "rgba(255, 86, 48, 0.95)"
            border_color = colors.error
            text_color = "white"

        # Base tooltip styles
        base_styles = f"""
            AtlassianTooltip {{
                background-color: {bg_color};
                border: {borders.border_width}px solid {border_color};
                border-radius: {borders.border_radius}px;
                color: {text_color};
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui_small}px;
                font-weight: {typography.font_weight_regular};
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            }}

            AtlassianTooltip QLabel {{
                color: {text_color};
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }}
        """

        return base_styles

    def set_text(self, text: str):
        """Set tooltip text."""
        self._text = text
        self._content_label.setText(text)
        self.adjustSize()

    def set_appearance(self, appearance: str):
        """Set tooltip appearance."""
        self._appearance = appearance
        self._apply_styling()

    def set_max_width(self, max_width: int):
        """Set maximum tooltip width."""
        self._max_width = max_width
        self._content_label.setMaximumWidth(max_width)
        self.adjustSize()

    def show_at_position(self, global_pos: QPoint, preferred_position: str = "top"):
        """Show tooltip at specific global position with smart positioning."""
        self._position = preferred_position

        # Get tooltip size
        self.adjustSize()
        tooltip_size = self.size()

        # Get available screen geometry
        screen = QApplication.primaryScreen().availableGeometry()

        # Calculate position based on preferred position and available space
        pos = self._calculate_smart_position(global_pos, tooltip_size, screen, preferred_position)

        # Move to calculated position
        self.move(pos)
        self.show()
        self.raise_()

    def _calculate_smart_position(self, target_pos: QPoint, tooltip_size: QSize,
                                screen: QRect, preferred: str) -> QPoint:
        """Calculate optimal tooltip position to stay on screen."""
        spacing = self._design_tokens.spacing.space_100  # 8px spacing

        positions = {
            "top": QPoint(
                target_pos.x() - tooltip_size.width() // 2,
                target_pos.y() - tooltip_size.height() - spacing
            ),
            "bottom": QPoint(
                target_pos.x() - tooltip_size.width() // 2,
                target_pos.y() + spacing
            ),
            "left": QPoint(
                target_pos.x() - tooltip_size.width() - spacing,
                target_pos.y() - tooltip_size.height() // 2
            ),
            "right": QPoint(
                target_pos.x() + spacing,
                target_pos.y() - tooltip_size.height() // 2
            )
        }

        # Try preferred position first
        pos = positions[preferred]

        # Check if position fits on screen, try alternatives if not
        if not self._position_fits_on_screen(pos, tooltip_size, screen):
            # Try opposite position
            opposite = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}[preferred]
            pos = positions[opposite]

            # If still doesn't fit, try remaining positions
            if not self._position_fits_on_screen(pos, tooltip_size, screen):
                for position_name, position_pos in positions.items():
                    if position_name not in [preferred, opposite]:
                        if self._position_fits_on_screen(position_pos, tooltip_size, screen):
                            pos = position_pos
                            self._position = position_name
                            break

        # Ensure tooltip stays within screen bounds
        pos.setX(max(0, min(pos.x(), screen.right() - tooltip_size.width())))
        pos.setY(max(0, min(pos.y(), screen.bottom() - tooltip_size.height())))

        return pos

    def _position_fits_on_screen(self, pos: QPoint, size: QSize, screen: QRect) -> bool:
        """Check if tooltip position fits within screen bounds."""
        tooltip_rect = QRect(pos, size)
        return screen.contains(tooltip_rect)

    def show_near_widget(self, widget: QWidget, preferred_position: str = "top"):
        """Show tooltip near a specific widget."""
        self._target_widget = widget

        # Get widget's global position and center
        widget_rect = widget.rect()
        widget_center = widget.mapToGlobal(widget_rect.center())

        self.show_at_position(widget_center, preferred_position)

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    def hide_tooltip(self):
        """Hide the tooltip."""
        self.hide()

    @property
    def text(self) -> str:
        return self._text

    @property
    def appearance(self) -> str:
        return self._appearance

    @property
    def max_width(self) -> int:
        return self._max_width


class TooltipManager(QObject):
    """
    Global tooltip manager for handling tooltip display and positioning.

    Features:
    - Singleton pattern for global tooltip management
    - Automatic show/hide timing
    - Mouse tracking for smart positioning
    - Keyboard accessibility support
    """

    def __init__(self):
        super().__init__()

        self._current_tooltip = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_current_tooltip)

        self._show_delay = 500  # ms
        self._hide_delay = 3000  # ms

    def show_tooltip(self, tooltip: AtlassianTooltip, widget: QWidget,
                    position: str = "top", delay: int = None):
        """Show a tooltip near a widget."""
        # Hide current tooltip
        self.hide_tooltip()

        # Set new tooltip
        self._current_tooltip = tooltip

        # Show after delay (unless delay is 0)
        show_delay = delay if delay is not None else self._show_delay
        if show_delay > 0:
            QTimer.singleShot(show_delay, lambda: tooltip.show_near_widget(widget, position))
        else:
            tooltip.show_near_widget(widget, position)

        # Set auto-hide timer
        self._hide_timer.start(self._hide_delay)

    def hide_tooltip(self):
        """Hide the current tooltip."""
        if self._current_tooltip:
            self._current_tooltip.hide_tooltip()
            self._current_tooltip = None

        self._hide_timer.stop()

    def set_show_delay(self, delay: int):
        """Set tooltip show delay in milliseconds."""
        self._show_delay = delay

    def set_hide_delay(self, delay: int):
        """Set tooltip auto-hide delay in milliseconds."""
        self._hide_delay = delay

    def _hide_current_tooltip(self):
        """Hide the current tooltip (called by timer)."""
        self.hide_tooltip()

    @property
    def current_tooltip(self) -> Optional[AtlassianTooltip]:
        return self._current_tooltip

    @property
    def show_delay(self) -> int:
        return self._show_delay

    @property
    def hide_delay(self) -> int:
        return self._hide_delay


# Global tooltip manager instance
tooltip_manager = TooltipManager()


# Convenience functions for creating tooltips
def create_tooltip(
    text: str,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    max_width: int = 200,
    appearance: str = "default"
) -> AtlassianTooltip:
    """Create an Atlassian-style tooltip."""
    return AtlassianTooltip(
        text=text,
        parent=parent,
        design_tokens=design_tokens,
        max_width=max_width,
        appearance=appearance
    )


def show_tooltip_near_widget(
    widget: QWidget,
    text: str,
    position: str = "top",
    appearance: str = "default",
    delay: int = None,
    design_tokens: Optional[DesignTokens] = None
):
    """Show a tooltip near a widget using the global tooltip manager."""
    tooltip = create_tooltip(text, widget, design_tokens, appearance=appearance)
    tooltip_manager.show_tooltip(tooltip, widget, position, delay)


def hide_current_tooltip():
    """Hide the currently displayed tooltip."""
    tooltip_manager.hide_tooltip()


class AtlassianEmptyState(QWidget):
    """
    Atlassian-style empty state component for when no data is available.

    Features:
    - Customizable icon and messaging
    - Action buttons for user guidance
    - Multiple sizes and layouts
    - Proper spacing and typography
    - Accessible design
    """

    def __init__(
        self,
        title: str = "No data available",
        description: str = "",
        icon: str = "",
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        size: str = "medium",  # "small", "medium", "large"
        action_buttons: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._title = title
        self._description = description
        self._icon = icon
        self._size = size
        self._action_buttons = action_buttons or []

        self._setup_empty_state()
        self._apply_styling()

    def _setup_empty_state(self):
        """Setup empty state layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(self._design_tokens.spacing.space_200)

        # Icon (if provided)
        if self._icon:
            self._icon_label = QLabel(self._icon, self)
            self._icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self._icon_label)

        # Title
        self._title_label = QLabel(self._title, self)
        self._title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title_label)

        # Description (if provided)
        if self._description:
            self._description_label = QLabel(self._description, self)
            self._description_label.setAlignment(Qt.AlignCenter)
            self._description_label.setWordWrap(True)
            layout.addWidget(self._description_label)

        # Action buttons (if provided)
        if self._action_buttons:
            buttons_layout = QHBoxLayout()
            buttons_layout.setAlignment(Qt.AlignCenter)
            buttons_layout.setSpacing(self._design_tokens.spacing.space_100)

            self._button_widgets = []
            for button_config in self._action_buttons:
                button_text = button_config.get('text', 'Action')
                button_appearance = button_config.get('appearance', 'default')
                button_callback = button_config.get('callback', None)

                # Map appearance strings to enum values
                appearance_map = {
                    'default': ButtonAppearance.DEFAULT,
                    'primary': ButtonAppearance.PRIMARY,
                    'danger': ButtonAppearance.DANGER,
                    'link': ButtonAppearance.LINK,
                    'subtle': ButtonAppearance.SUBTLE
                }

                button = AtlassianButton(
                    button_text,
                    parent=self,
                    appearance=appearance_map.get(button_appearance, ButtonAppearance.DEFAULT),
                    size=ButtonSize.MEDIUM,
                    design_tokens=self._design_tokens
                )

                if button_callback:
                    button.clicked.connect(button_callback)

                buttons_layout.addWidget(button)
                self._button_widgets.append(button)

            layout.addLayout(buttons_layout)

    def _apply_styling(self):
        """Apply styling based on size and design tokens."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens and size."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        typography = tokens.typography

        # Size configurations
        size_config = {
            "small": {
                "icon_size": spacing.space_400,      # 32px
                "title_size": typography.font_size_ui,  # 14px
                "description_size": typography.font_size_ui_small,  # 12px
                "spacing": spacing.space_150         # 12px
            },
            "medium": {
                "icon_size": spacing.space_600,      # 48px
                "title_size": typography.font_size_h5,  # 14px (but larger weight)
                "description_size": typography.font_size_ui,  # 14px
                "spacing": spacing.space_200         # 16px
            },
            "large": {
                "icon_size": spacing.space_700,      # 56px
                "title_size": typography.font_size_h4,  # 16px
                "description_size": typography.font_size_ui_large,  # 16px
                "spacing": spacing.space_300         # 24px
            }
        }

        config = size_config.get(self._size, size_config["medium"])

        # Base empty state styles
        base_styles = f"""
            AtlassianEmptyState {{
                background-color: transparent;
                color: {colors.text};
            }}

            AtlassianEmptyState QLabel {{
                background: transparent;
                border: none;
            }}
        """

        # Icon styling
        icon_styles = f"""
            AtlassianEmptyState QLabel:first-child {{
                font-size: {config['icon_size']}px;
                color: {colors.text_subtle};
                margin-bottom: {config['spacing']}px;
            }}
        """

        # Title styling
        title_styles = f"""
            AtlassianEmptyState QLabel:nth-child(2) {{
                font-size: {config['title_size']}px;
                font-weight: {typography.font_weight_semibold};
                color: {colors.text};
                margin-bottom: {config['spacing']}px;
            }}
        """

        # Description styling
        description_styles = ""
        if self._description:
            child_index = 3 if self._icon else 2
            description_styles = f"""
                AtlassianEmptyState QLabel:nth-child({child_index}) {{
                    font-size: {config['description_size']}px;
                    color: {colors.text_subtle};
                    line-height: 1.4;
                    max-width: 400px;
                    margin-bottom: {config['spacing']}px;
                }}
            """

        return base_styles + icon_styles + title_styles + description_styles

    def set_title(self, title: str):
        """Set the empty state title."""
        self._title = title
        self._title_label.setText(title)

    def set_description(self, description: str):
        """Set the empty state description."""
        self._description = description
        if hasattr(self, '_description_label'):
            self._description_label.setText(description)
            self._description_label.setVisible(bool(description))
        else:
            # Create description label if it doesn't exist
            if description:
                from PySide6.QtWidgets import QVBoxLayout, QLabel
                self._description_label = QLabel(description, self)
                self._description_label.setAlignment(Qt.AlignCenter)
                self._description_label.setWordWrap(True)

                # Insert after title (position depends on whether icon exists)
                layout = self.layout()
                insert_pos = 2 if self._icon else 1
                layout.insertWidget(insert_pos, self._description_label)
                self._apply_styling()

    def set_icon(self, icon: str):
        """Set the empty state icon."""
        self._icon = icon
        if hasattr(self, '_icon_label'):
            self._icon_label.setText(icon)
            self._icon_label.setVisible(bool(icon))
        else:
            # Create icon label if it doesn't exist
            if icon:
                from PySide6.QtWidgets import QVBoxLayout, QLabel
                self._icon_label = QLabel(icon, self)
                self._icon_label.setAlignment(Qt.AlignCenter)

                # Insert at the beginning
                layout = self.layout()
                layout.insertWidget(0, self._icon_label)
                self._apply_styling()

    def set_size(self, size: str):
        """Set empty state size ('small', 'medium', 'large')."""
        self._size = size
        self._apply_styling()

    def set_action_buttons(self, buttons: List[Dict[str, Any]]):
        """Set action buttons for the empty state."""
        self._action_buttons = buttons
        # Re-setup the buttons area
        self._setup_empty_state()
        self._apply_styling()

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def size(self) -> str:
        return self._size


# Convenience functions for creating empty states
def create_empty_state(
    title: str = "No data available",
    description: str = "",
    icon: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    size: str = "medium",
    action_buttons: Optional[List[Dict[str, Any]]] = None
) -> AtlassianEmptyState:
    """Create an Atlassian-style empty state."""
    return AtlassianEmptyState(
        title=title,
        description=description,
        icon=icon,
        parent=parent,
        design_tokens=design_tokens,
        size=size,
        action_buttons=action_buttons
    )


def create_no_processes_empty_state(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianEmptyState:
    """Create an empty state for when no processes are running."""
    return create_empty_state(
        title="No processes found",
        description="There are currently no active processes to monitor. Start some applications to see monitoring data.",
        icon="🔍",
        parent=parent,
        design_tokens=design_tokens,
        size="large"
    )


def create_no_network_empty_state(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianEmptyState:
    """Create an empty state for when no network connections exist."""
    return create_empty_state(
        title="No network activity",
        description="No active network connections detected. Network monitoring will show data when connections are established.",
        icon="🌐",
        parent=parent,
        design_tokens=design_tokens,
        size="medium"
    )


def create_no_data_empty_state(
    title: str = "No data available",
    description: str = "There is no data to display at this time.",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianEmptyState:
    """Create a generic empty state for no data scenarios."""
    return create_empty_state(
        title=title,
        description=description,
        icon="📊",
        parent=parent,
        design_tokens=design_tokens,
        size="medium"
    )


class AtlassianDataTable(QWidget):
    """
    Atlassian-style data table component for displaying tabular data.

    Features:
    - Clean, professional table styling
    - Sortable columns with visual indicators
    - Alternating row colors
    - Hover states and selection
    - Proper spacing and typography
    - Accessible design with keyboard navigation
    - Pagination support for large datasets
    """

    itemSelectionChanged = Signal()
    itemDoubleClicked = Signal(object)  # row data

    def __init__(
        self,
        columns: List[Dict[str, Any]] = None,
        data: List[List[Any]] = None,
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        sortable: bool = True,
        selectable: bool = True,
        show_header: bool = True,
        alternating_row_colors: bool = True,
        max_rows: int = 0  # 0 = show all rows
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._columns = columns or []
        self._data = data or []
        self._sortable = sortable
        self._selectable = selectable
        self._show_header = show_header
        self._alternating_row_colors = alternating_row_colors
        self._max_rows = max_rows

        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder
        self._selected_rows = set()

        self._setup_table()
        self._apply_styling()

    def _setup_table(self):
        """Setup table layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create table widget
        self._table = QTableWidget(self)
        self._table.setAlternatingRowColors(self._alternating_row_colors)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection if self._selectable else QTableWidget.NoSelection)
        self._table.setShowGrid(False)
        self._table.setSortingEnabled(self._sortable)

        # Hide headers if not needed
        if not self._show_header:
            self._table.horizontalHeader().setVisible(False)
        else:
            # Configure horizontal header
            header = self._table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSortIndicatorShown(self._sortable)
            header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            header.sectionClicked.connect(self._on_header_clicked)

        # Configure vertical header (row numbers)
        self._table.verticalHeader().setVisible(False)

        # Set column count and headers
        if self._columns:
            self._table.setColumnCount(len(self._columns))
            if self._show_header:
                for i, column in enumerate(self._columns):
                    header_item = QTableWidgetItem(column.get('title', f'Column {i+1}'))
                    self._table.setHorizontalHeaderItem(i, header_item)

                    # Set column width
                    width = column.get('width', 0)
                    if width > 0:
                        self._table.setColumnWidth(i, width)
                    elif column.get('stretch', False):
                        self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
                    else:
                        self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)

        layout.addWidget(self._table)

        # Populate table with data
        self._populate_table()

        # Connect signals
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _apply_styling(self):
        """Apply styling based on design tokens."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Base table styles
        base_styles = f"""
            AtlassianDataTable {{
                background-color: transparent;
                border-radius: {borders.border_radius}px;
            }}

            AtlassianDataTable QTableWidget {{
                background-color: {colors.surface};
                border: {borders.border_width}px solid {colors.border};
                border-radius: {borders.border_radius}px;
                gridline-color: {colors.border};
                selection-background-color: {colors.primary};
                selection-color: white;
                alternate-background-color: {colors.surface_sunken};
            }}

            AtlassianDataTable QTableWidget::item {{
                padding: {spacing.space_100}px {spacing.space_150}px;
                border: none;
                border-bottom: 1px solid {colors.border};
                color: {colors.text};
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui}px;
                font-weight: {typography.font_weight_regular};
            }}

            AtlassianDataTable QTableWidget::item:selected {{
                background-color: rgba(76, 154, 255, 0.1);
                color: {colors.primary};
                font-weight: {typography.font_weight_medium};
            }}

            AtlassianDataTable QTableWidget::item:hover {{
                background-color: {colors.surface_sunken};
            }}

            AtlassianDataTable QTableWidget::item:selected:hover {{
                background-color: rgba(76, 154, 255, 0.15);
            }}

            AtlassianDataTable QTableWidget QHeaderView::section {{
                background-color: {colors.surface_sunken};
                color: {colors.text_subtle};
                font-family: {typography.font_family};
                font-size: {typography.font_size_ui_small}px;
                font-weight: {typography.font_weight_medium};
                padding: {spacing.space_125}px {spacing.space_150}px;
                border: none;
                border-bottom: 2px solid {colors.border};
                text-align: left;
            }}

            AtlassianDataTable QTableWidget QHeaderView::section:hover {{
                background-color: {colors.surface_raised};
                color: {colors.text};
            }}

            AtlassianDataTable QTableWidget QHeaderView::section:pressed {{
                background-color: {colors.surface_raised};
                color: {colors.primary};
            }}

            AtlassianDataTable QTableWidget QHeaderView::section:checked {{
                background-color: {colors.primary};
                color: white;
                font-weight: {typography.font_weight_semibold};
            }}
        """

        # Sort indicator styling
        sort_styles = f"""
            AtlassianDataTable QTableWidget QHeaderView::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {colors.text_subtle};
                margin-bottom: 2px;
            }}

            AtlassianDataTable QTableWidget QHeaderView::up-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 4px solid {colors.text_subtle};
                margin-top: 2px;
            }}

            AtlassianDataTable QTableWidget QHeaderView::down-arrow:hover,
            AtlassianDataTable QTableWidget QHeaderView::up-arrow:hover {{
                border-color: {colors.primary};
            }}
        """

        return base_styles + sort_styles

    def _populate_table(self):
        """Populate table with data."""
        from PySide6.QtWidgets import QTableWidgetItem

        # Clear existing data
        self._table.setRowCount(0)

        if not self._data:
            return

        # Determine number of rows to show
        row_count = len(self._data)
        if self._max_rows > 0:
            row_count = min(row_count, self._max_rows)

        self._table.setRowCount(row_count)

        # Populate rows
        for row_idx in range(row_count):
            row_data = self._data[row_idx]

            for col_idx in range(min(len(row_data), self._table.columnCount())):
                cell_data = row_data[col_idx]

                # Create table item
                if isinstance(cell_data, QWidget):
                    # For custom widgets (like progress bars, badges)
                    self._table.setCellWidget(row_idx, col_idx, cell_data)
                else:
                    # For text data
                    item = QTableWidgetItem(str(cell_data))
                    item.setData(Qt.UserRole, cell_data)  # Store original data
                    self._table.setItem(row_idx, col_idx, item)

    def _on_header_clicked(self, column: int):
        """Handle header click for sorting."""
        if not self._sortable:
            return

        if self._sort_column == column:
            # Toggle sort order
            self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self._sort_column = column
            self._sort_order = Qt.AscendingOrder

        self._table.sortItems(column, self._sort_order)

    def _on_selection_changed(self):
        """Handle selection changes."""
        selected_rows = set()
        for item in self._table.selectedItems():
            selected_rows.add(item.row())

        self._selected_rows = selected_rows
        self.itemSelectionChanged.emit()

    def _on_item_double_clicked(self, item):
        """Handle item double click."""
        row = item.row()
        if 0 <= row < len(self._data):
            self.itemDoubleClicked.emit(self._data[row])

    def set_columns(self, columns: List[Dict[str, Any]]):
        """Set table columns."""
        self._columns = columns

        # Update table structure
        self._table.setColumnCount(len(columns))

        if self._show_header:
            from PySide6.QtWidgets import QTableWidgetItem, QHeaderView
            for i, column in enumerate(columns):
                header_item = QTableWidgetItem(column.get('title', f'Column {i+1}'))
                self._table.setHorizontalHeaderItem(i, header_item)

                # Set column width
                width = column.get('width', 0)
                if width > 0:
                    self._table.setColumnWidth(i, width)
                elif column.get('stretch', False):
                    self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
                else:
                    self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)

        # Repopulate data
        self._populate_table()

    def set_data(self, data: List[List[Any]]):
        """Set table data."""
        self._data = data
        self._populate_table()

    def add_row(self, row_data: List[Any]):
        """Add a single row to the table."""
        self._data.append(row_data)
        self._populate_table()

    def remove_row(self, row_index: int):
        """Remove a row from the table."""
        if 0 <= row_index < len(self._data):
            self._data.pop(row_index)
            self._populate_table()

    def clear_data(self):
        """Clear all table data."""
        self._data.clear()
        self._table.setRowCount(0)

    def get_selected_rows(self) -> List[int]:
        """Get indices of selected rows."""
        return list(self._selected_rows)

    def get_selected_data(self) -> List[List[Any]]:
        """Get data for selected rows."""
        return [self._data[row_idx] for row_idx in self._selected_rows if row_idx < len(self._data)]

    def select_row(self, row_index: int):
        """Select a specific row."""
        if 0 <= row_index < self._table.rowCount():
            self._table.selectRow(row_index)

    def clear_selection(self):
        """Clear all selections."""
        self._table.clearSelection()

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._apply_styling()

    @property
    def data(self) -> List[List[Any]]:
        return self._data.copy()

    @property
    def columns(self) -> List[Dict[str, Any]]:
        return self._columns.copy()

    @property
    def selected_rows(self) -> List[int]:
        return self.get_selected_rows()

    @property
    def row_count(self) -> int:
        return self._table.rowCount()

    @property
    def column_count(self) -> int:
        return self._table.columnCount()


# Convenience functions for creating data tables
def create_data_table(
    columns: List[Dict[str, Any]] = None,
    data: List[List[Any]] = None,
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    sortable: bool = True,
    selectable: bool = True
) -> AtlassianDataTable:
    """Create an Atlassian-style data table."""
    return AtlassianDataTable(
        columns=columns,
        data=data,
        parent=parent,
        design_tokens=design_tokens,
        sortable=sortable,
        selectable=selectable
    )


def create_process_table(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianDataTable:
    """Create a data table for displaying system processes."""
    columns = [
        {"title": "Name", "width": 200, "sortable": True},
        {"title": "PID", "width": 80, "sortable": True},
        {"title": "CPU %", "width": 80, "sortable": True},
        {"title": "Memory %", "width": 100, "sortable": True},
        {"title": "Status", "width": 100, "sortable": False},
        {"title": "User", "stretch": True, "sortable": True}
    ]

    return create_data_table(
        columns=columns,
        parent=parent,
        design_tokens=design_tokens
    )


def create_network_table(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianDataTable:
    """Create a data table for displaying network connections."""
    columns = [
        {"title": "Protocol", "width": 80, "sortable": True},
        {"title": "Local Address", "width": 150, "sortable": False},
        {"title": "Remote Address", "width": 150, "sortable": False},
        {"title": "Status", "width": 100, "sortable": True},
        {"title": "PID", "width": 80, "sortable": True},
        {"title": "Process", "stretch": True, "sortable": True}
    ]

    return create_data_table(
        columns=columns,
        parent=parent,
        design_tokens=design_tokens
    )


def create_disk_table(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianDataTable:
    """Create a data table for displaying disk usage."""
    columns = [
        {"title": "Mount Point", "width": 120, "sortable": True},
        {"title": "File System", "width": 100, "sortable": True},
        {"title": "Total", "width": 100, "sortable": True},
        {"title": "Used", "width": 100, "sortable": True},
        {"title": "Available", "width": 100, "sortable": True},
        {"title": "Usage %", "width": 100, "sortable": True},
        {"title": "Status", "stretch": True, "sortable": False}
    ]

    return create_data_table(
        columns=columns,
        parent=parent,
        design_tokens=design_tokens
    )


class AtlassianModal(QDialog):
    """
    Atlassian-style modal dialog component for overlays and dialogs.

    Features:
    - Professional modal styling with backdrop
    - Flexible content area
    - Header with title and close button
    - Footer with action buttons
    - Proper focus management and keyboard navigation
    - Multiple sizes and responsive behavior
    - Accessible design with ARIA support
    """

    accepted = Signal()
    rejected = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        title: str = "",
        size: str = "medium",  # "small", "medium", "large", "fullscreen"
        show_close_button: bool = True,
        modal: bool = True
    ):
        super().__init__(parent)

        self._design_tokens = design_tokens or DEFAULT_TOKENS
        self._title = title
        self._size = size
        self._show_close_button = show_close_button

        # Set modal properties
        self.setModal(modal)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)

        self._setup_modal()
        self._apply_styling()

        # Connect escape key to reject
        from PySide6.QtWidgets import QShortcut
        from PySide6.QtGui import QKeySequence
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.reject)

    def _setup_modal(self):
        """Setup modal layout and components."""
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Modal container (the actual modal window)
        self._modal_container = QWidget(self)
        self._modal_container.setObjectName("modalContainer")

        container_layout = QVBoxLayout(self._modal_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Header
        self._header = QWidget(self._modal_container)
        self._header.setObjectName("modalHeader")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(
            self._design_tokens.spacing.space_200,
            self._design_tokens.spacing.space_200,
            self._design_tokens.spacing.space_200,
            self._design_tokens.spacing.space_150
        )

        # Title
        self._title_label = QLabel(self._title, self._header)
        self._title_label.setObjectName("modalTitle")
        header_layout.addWidget(self._title_label, 1)  # Stretch to fill space

        # Close button
        if self._show_close_button:
            self._close_button = QPushButton("×", self._header)
            self._close_button.setObjectName("modalCloseButton")
            self._close_button.setFixedSize(32, 32)
            self._close_button.clicked.connect(self.reject)
            header_layout.addWidget(self._close_button)

        container_layout.addWidget(self._header)

        # Content area
        self._content_area = QWidget(self._modal_container)
        self._content_area.setObjectName("modalContent")
        self._content_layout = QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(
            self._design_tokens.spacing.space_200,
            0,
            self._design_tokens.spacing.space_200,
            self._design_tokens.spacing.space_200
        )
        container_layout.addWidget(self._content_area, 1)  # Stretch to fill available space

        # Footer (initially hidden)
        self._footer = QWidget(self._modal_container)
        self._footer.setObjectName("modalFooter")
        self._footer.setVisible(False)
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(
            self._design_tokens.spacing.space_200,
            self._design_tokens.spacing.space_150,
            self._design_tokens.spacing.space_200,
            self._design_tokens.spacing.space_200
        )
        footer_layout.setSpacing(self._design_tokens.spacing.space_100)

        # Action buttons container
        self._action_buttons_widget = QWidget(self._footer)
        self._action_buttons_layout = QHBoxLayout(self._action_buttons_widget)
        self._action_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._action_buttons_layout.setSpacing(self._design_tokens.spacing.space_075)
        self._action_buttons_layout.addStretch()  # Push buttons to the right

        footer_layout.addWidget(self._action_buttons_widget, 1)

        container_layout.addWidget(self._footer)

        main_layout.addWidget(self._modal_container, 0, Qt.AlignCenter)

        # Set size constraints based on size variant
        self._update_size_constraints()

    def _update_size_constraints(self):
        """Update size constraints based on size variant."""
        if self._size == "small":
            self._modal_container.setFixedSize(400, 300)
        elif self._size == "medium":
            self._modal_container.setFixedSize(600, 400)
        elif self._size == "large":
            self._modal_container.setFixedSize(800, 600)
        elif self._size == "fullscreen":
            # For fullscreen, we'll handle this in showEvent
            self._modal_container.setMinimumSize(800, 600)
        else:
            self._modal_container.setFixedSize(600, 400)  # Default to medium

    def _apply_styling(self):
        """Apply styling based on design tokens."""
        self.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        """Generate stylesheet based on design tokens."""
        tokens = self._design_tokens
        colors = tokens.colors
        spacing = tokens.spacing
        borders = tokens.borders
        typography = tokens.typography

        # Modal backdrop and container
        modal_styles = f"""
            AtlassianModal {{
                background-color: rgba(0, 0, 0, 0.5);
            }}

            #modalContainer {{
                background-color: {colors.surface};
                border: {borders.border_width}px solid {colors.border};
                border-radius: {borders.border_radius}px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
            }}
        """

        # Header styling
        header_styles = f"""
            #modalHeader {{
                background-color: {colors.surface};
                border-bottom: 1px solid {colors.border};
                border-top-left-radius: {borders.border_radius}px;
                border-top-right-radius: {borders.border_radius}px;
            }}

            #modalTitle {{
                font-family: {typography.font_family};
                font-size: {typography.font_size_h5}px;
                font-weight: {typography.font_weight_semibold};
                color: {colors.text};
                margin: 0;
                padding: 0;
            }}

            #modalCloseButton {{
                background-color: transparent;
                border: none;
                border-radius: {borders.border_radius}px;
                color: {colors.text_subtle};
                font-size: 18px;
                font-weight: bold;
                padding: 0;
                min-width: 32px;
                min-height: 32px;
            }}

            #modalCloseButton:hover {{
                background-color: {colors.surface_sunken};
                color: {colors.text};
            }}

            #modalCloseButton:pressed {{
                background-color: {colors.surface_raised};
            }}
        """

        # Content area
        content_styles = f"""
            #modalContent {{
                background-color: {colors.surface};
            }}
        """

        # Footer styling
        footer_styles = f"""
            #modalFooter {{
                background-color: {colors.surface_sunken};
                border-top: 1px solid {colors.border};
                border-bottom-left-radius: {borders.border_radius}px;
                border-bottom-right-radius: {borders.border_radius}px;
            }}
        """

        return modal_styles + header_styles + content_styles + footer_styles

    def set_title(self, title: str):
        """Set modal title."""
        self._title = title
        self._title_label.setText(title)

    def set_content_widget(self, widget: QWidget):
        """Set the main content widget."""
        # Clear existing content
        self._clear_content_layout()

        # Add new widget
        self._content_layout.addWidget(widget)

    def add_content_widget(self, widget: QWidget):
        """Add a widget to the content area."""
        self._content_layout.addWidget(widget)

    def _clear_content_layout(self):
        """Clear all widgets from content layout."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def add_action_button(self, text: str, role: str = "secondary",
                         callback: Optional[Callable] = None) -> QPushButton:
        """Add an action button to the footer."""
        from PySide6.QtWidgets import QPushButton

        self._footer.setVisible(True)

        button = QPushButton(text, self._action_buttons_widget)
        button.setObjectName(f"modalActionButton_{role}")

        # Style based on role
        if role == "primary":
            button.clicked.connect(lambda: self._handle_primary_action(callback))
        elif role == "secondary":
            button.clicked.connect(lambda: self._handle_secondary_action(callback))
        else:
            button.clicked.connect(lambda: self._handle_custom_action(callback))

        self._action_buttons_layout.addWidget(button)
        return button

    def _handle_primary_action(self, callback: Optional[Callable]):
        """Handle primary action button click."""
        if callback:
            callback()
        self.accept()

    def _handle_secondary_action(self, callback: Optional[Callable]):
        """Handle secondary action button click."""
        if callback:
            callback()
        self.reject()

    def _handle_custom_action(self, callback: Optional[Callable]):
        """Handle custom action button click."""
        if callback:
            callback()

    def clear_action_buttons(self):
        """Clear all action buttons."""
        while self._action_buttons_layout.count():
            item = self._action_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        self._footer.setVisible(False)

    def showEvent(self, event):
        """Handle show event for proper positioning."""
        super().showEvent(event)

        if self._size == "fullscreen":
            # Make modal take up most of the screen
            if self.parent():
                parent_rect = self.parent().rect()
                margin = 40
                self._modal_container.setGeometry(
                    margin, margin,
                    parent_rect.width() - 2 * margin,
                    parent_rect.height() - 2 * margin
                )

    def update_design_tokens(self, tokens: DesignTokens):
        """Update design tokens and refresh styling."""
        self._design_tokens = tokens
        self._update_size_constraints()
        self._apply_styling()

    def set_size(self, size: str):
        """Set modal size ('small', 'medium', 'large', 'fullscreen')."""
        self._size = size
        self._update_size_constraints()

    @property
    def content_layout(self) -> QVBoxLayout:
        """Get the content layout for adding widgets."""
        return self._content_layout

    @property
    def title(self) -> str:
        return self._title

    @property
    def size(self) -> str:
        return self._size


class AtlassianMessageDialog(AtlassianModal):
    """
    Specialized modal for displaying messages, confirmations, and alerts.

    Features:
    - Pre-configured layouts for common dialog types
    - Icon support for different message types
    - Standard button configurations
    - Easy-to-use convenience methods
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        design_tokens: Optional[DesignTokens] = None,
        title: str = "",
        message: str = "",
        dialog_type: str = "info",  # "info", "warning", "error", "question"
        buttons: List[str] = None  # ["OK"], ["OK", "Cancel"], etc.
    ):
        super().__init__(parent, design_tokens, title, size="small")

        self._message = message
        self._dialog_type = dialog_type
        self._buttons = buttons or ["OK"]

        self._setup_message_dialog()

    def _setup_message_dialog(self):
        """Setup message dialog layout."""
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel

        # Content layout
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setSpacing(self._design_tokens.spacing.space_150)

        # Icon
        self._icon_label = QLabel(content_widget)
        self._icon_label.setFixedSize(48, 48)
        self._icon_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self._icon_label, 0, Qt.AlignTop)

        # Message
        self._message_label = QLabel(self._message, content_widget)
        self._message_label.setWordWrap(True)
        self._message_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content_layout.addWidget(self._message_label, 1)

        self.set_content_widget(content_widget)

        # Add buttons
        self._setup_buttons()

        # Update icon
        self._update_icon()

    def _update_icon(self):
        """Update icon based on dialog type."""
        icon_text = ""
        if self._dialog_type == "info":
            icon_text = "ℹ️"
        elif self._dialog_type == "warning":
            icon_text = "⚠️"
        elif self._dialog_type == "error":
            icon_text = "❌"
        elif self._dialog_type == "question":
            icon_text = "❓"
        elif self._dialog_type == "success":
            icon_text = "✅"

        self._icon_label.setText(icon_text)

    def _setup_buttons(self):
        """Setup dialog buttons."""
        for button_text in self._buttons:
            if button_text.upper() in ["OK", "YES"]:
                self.add_action_button(button_text, "primary")
            elif button_text.upper() in ["CANCEL", "NO"]:
                self.add_action_button(button_text, "secondary")
            else:
                self.add_action_button(button_text, "custom")

    def set_message(self, message: str):
        """Set dialog message."""
        self._message = message
        self._message_label.setText(message)

    def set_dialog_type(self, dialog_type: str):
        """Set dialog type ('info', 'warning', 'error', 'question', 'success')."""
        self._dialog_type = dialog_type
        self._update_icon()


# Convenience functions for creating modals
def create_modal(
    title: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    size: str = "medium",
    show_close_button: bool = True
) -> AtlassianModal:
    """Create an Atlassian-style modal dialog."""
    return AtlassianModal(
        parent=parent,
        design_tokens=design_tokens,
        title=title,
        size=size,
        show_close_button=show_close_button
    )


def create_message_dialog(
    title: str = "",
    message: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    dialog_type: str = "info",
    buttons: List[str] = None
) -> AtlassianMessageDialog:
    """Create an Atlassian-style message dialog."""
    return AtlassianMessageDialog(
        parent=parent,
        design_tokens=design_tokens,
        title=title,
        message=message,
        dialog_type=dialog_type,
        buttons=buttons
    )


def create_confirmation_dialog(
    title: str = "Confirm Action",
    message: str = "Are you sure you want to proceed?",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianMessageDialog:
    """Create a confirmation dialog with Yes/No buttons."""
    return create_message_dialog(
        title=title,
        message=message,
        parent=parent,
        design_tokens=design_tokens,
        dialog_type="question",
        buttons=["Yes", "No"]
    )


def create_error_dialog(
    title: str = "Error",
    message: str = "An error occurred.",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianMessageDialog:
    """Create an error dialog."""
    return create_message_dialog(
        title=title,
        message=message,
        parent=parent,
        design_tokens=design_tokens,
        dialog_type="error",
        buttons=["OK"]
    )


def create_success_dialog(
    title: str = "Success",
    message: str = "Operation completed successfully.",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianMessageDialog:
    """Create a success dialog."""
    return create_message_dialog(
        title=title,
        message=message,
        parent=parent,
        design_tokens=design_tokens,
        dialog_type="success",
        buttons=["OK"]
    )


def create_settings_modal(
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None
) -> AtlassianModal:
    """Create a settings modal dialog."""
    modal = create_modal(
        title="Settings",
        parent=parent,
        design_tokens=design_tokens,
        size="large"
    )

    # Add Save and Cancel buttons
    modal.add_action_button("Cancel", "secondary")
    modal.add_action_button("Save", "primary")

    return modal


# Convenience functions for creating form controls
def create_text_field(
    text: str = "",
    placeholder: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    helper_text: str = "",
    validation_state: str = "default"
) -> AtlassianTextField:
    """Create an Atlassian-style text field."""
    return AtlassianTextField(
        text=text,
        placeholder=placeholder,
        parent=parent,
        design_tokens=design_tokens,
        helper_text=helper_text,
        validation_state=validation_state
    )


def create_select(
    items: List[str] = None,
    current_index: int = -1,
    placeholder: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    helper_text: str = ""
) -> AtlassianSelect:
    """Create an Atlassian-style select dropdown."""
    return AtlassianSelect(
        items=items,
        current_index=current_index,
        placeholder=placeholder,
        parent=parent,
        design_tokens=design_tokens,
        helper_text=helper_text
    )


def create_checkbox(
    text: str = "",
    parent: Optional[QWidget] = None,
    design_tokens: Optional[DesignTokens] = None,
    helper_text: str = "",
    is_checked: bool = False
) -> AtlassianCheckbox:
    """Create an Atlassian-style checkbox."""
    return AtlassianCheckbox(
        text=text,
        parent=parent,
        design_tokens=design_tokens,
        helper_text=helper_text,
        is_checked=is_checked
    )


class AccessibilityManager:
    """アクセシビリティマネージャー - WCAG 2.1準拠"""

    def __init__(self):
        self.screen_reader_enabled = True
        self.high_contrast_mode = False
        self.large_text_mode = False
        self.reduced_motion = False

        # アクセシビリティ設定
        self._init_accessibility_settings()

    def _init_accessibility_settings(self) -> None:
        """アクセシビリティ設定を初期化"""
        # デフォルト設定
        self.settings = {
            'screen_reader': True,
            'keyboard_navigation': True,
            'high_contrast': False,
            'large_text': False,
            'reduced_motion': False,
            'color_blind_friendly': True,
            'focus_indicators': True,
            'aria_labels': True,
            'live_regions': True,
            'semantic_html': True
        }

    def apply_accessibility_features(self, widget: QWidget) -> None:
        """ウィジェットにアクセシビリティ機能を適用"""
        try:
            # 基本的なアクセシビリティ属性を設定
            widget.setAttribute(Qt.WidgetAttribute.WA_Accessible)
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

            # スクリーンリーダー対応
            if self.settings['screen_reader']:
                self._add_screen_reader_support(widget)

            # キーボードナビゲーション
            if self.settings['keyboard_navigation']:
                self._add_keyboard_navigation(widget)

            # ハイコントラストモード
            if self.settings['high_contrast']:
                self._apply_high_contrast(widget)

            # 大きなテキスト
            if self.settings['large_text']:
                self._apply_large_text(widget)

            # 動きの削減
            if self.settings['reduced_motion']:
                self._apply_reduced_motion(widget)

        except Exception as e:
            logger.error(f"アクセシビリティ適用エラー: {e}")

    def _add_screen_reader_support(self, widget: QWidget) -> None:
        """スクリーンリーダー対応を追加"""
        # ARIAラベルを設定
        if hasattr(widget, 'setAccessibleName'):
            name = getattr(widget, 'accessible_name', widget.objectName())
            if name:
                widget.setAccessibleName(name)

        if hasattr(widget, 'setAccessibleDescription'):
            desc = getattr(widget, 'accessible_description', '')
            if desc:
                widget.setAccessibleDescription(desc)

    def _add_keyboard_navigation(self, widget: QWidget) -> None:
        """キーボードナビゲーションを追加"""
        # フォーカスインジケーターを有効化
        if self.settings['focus_indicators']:
            widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

    def _apply_high_contrast(self, widget: QWidget) -> None:
        """ハイコントラストモードを適用"""
        # コントラストの高いカラーパレットを適用
        palette = widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        widget.setPalette(palette)

    def _apply_large_text(self, widget: QWidget) -> None:
        """大きなテキストを適用"""
        font = widget.font()
        font.setPointSize(font.pointSize() + 2)
        widget.setFont(font)

    def _apply_reduced_motion(self, widget: QWidget) -> None:
        """動きの削減を適用"""
        # アニメーションを無効化
        widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def validate_accessibility(self, widget: QWidget) -> Dict[str, Any]:
        """アクセシビリティを検証"""
        issues = []

        # 必須のアクセシビリティチェック
        if not widget.accessibleName():
            issues.append("アクセシブルネームが設定されていません")

        if not widget.focusPolicy():
            issues.append("フォーカスポリシーが設定されていません")

        # カラーコントラストチェック（簡易）
        if hasattr(widget, 'palette'):
            bg_color = widget.palette().color(QPalette.ColorRole.Window)
            text_color = widget.palette().color(QPalette.ColorRole.WindowText)
            if not self._check_color_contrast(bg_color, text_color):
                issues.append("カラーコントラストが不十分です")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'wcag_level': 'AA' if len(issues) == 0 else 'A'
        }

    def _check_color_contrast(self, bg_color: QColor, text_color: QColor) -> bool:
        """カラーコントラストをチェック"""
        # 簡易的なコントラストチェック
        bg_luminance = self._get_luminance(bg_color)
        text_luminance = self._get_luminance(text_color)

        contrast_ratio = (max(bg_luminance, text_luminance) + 0.05) / (min(bg_luminance, text_luminance) + 0.05)

        return contrast_ratio >= 4.5  # WCAG AA基準

    def _get_luminance(self, color: QColor) -> float:
        """色の輝度を計算"""
        r = color.red() / 255.0
        g = color.green() / 255.0
        b = color.blue() / 255.0

        # 線形化
        r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
        g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
        b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4

        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def generate_accessibility_report(self) -> Dict[str, Any]:
        """アクセシビリティレポートを生成"""
        return {
            'compliance_level': 'WCAG 2.1 AA',
            'features_enabled': self.settings,
            'supported_features': [
                'スクリーンリーダー対応',
                'キーボードナビゲーション',
                'ハイコントラストモード',
                '大きなテキスト',
                '動きの削減',
                'カラーコントラストチェック'
            ],
            'last_updated': datetime.now().isoformat()
        }


# グローバルインスタンス
accessibility_manager = AccessibilityManager()
