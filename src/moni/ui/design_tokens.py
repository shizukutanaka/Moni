from __future__ import annotations
from typing import Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class ColorScheme(Enum):
    """Color scheme variants."""
    LIGHT = "light"
    DARK = "dark"


@dataclass
class ColorTokens:
    """Color design tokens aligned with Atlassian design system."""
    # Background colors (Atlassian neutrals)
    background: str = "#FFFFFF"  # N0 - Primary background
    surface: str = "#FAFBFC"     # N10 - Secondary background (cards, dialogs)
    surface_sunken: str = "#F4F5F7"  # N20 - Tertiary background (inputs, buttons)
    surface_raised: str = "#EBECF0"   # N30 - Raised surface

    # Text colors (Atlassian neutrals with high contrast)
    text: str = "#172B4D"         # N800 - Primary text (WCAG AA compliant)
    text_subtle: str = "#42526E"  # N600 - Secondary text
    text_subtler: str = "#5E6C84" # N500 - Tertiary text
    text_disabled: str = "#8993A4" # N400 - Disabled text
    text_on_primary: str = "#FFFFFF" # Text on primary color background

    # Border and divider (Atlassian neutrals)
    border: str = "#DFE1E6"       # N40 - Border color
    border_focused: str = "#4C9AFF"  # B200 - Focused border (high contrast blue)
    border_subtle: str = "#EBECF0"   # N30 - Subtle border

    # Interactive colors (Atlassian brand and semantic colors)
    primary: str = "#0052CC"      # B400 - Primary actions (buttons, links)
    primary_hover: str = "#0065FF"  # B300 - Primary hover state
    primary_pressed: str = "#0747A6"  # B500 - Primary pressed state

    # Status colors (Atlassian semantic colors)
    success: str = "#36B37E"      # G400 - Success state
    success_hover: str = "#57D9A3"  # G300 - Success hover
    success_bold: str = "#006644"     # G500
    warning: str = "#FFAB00"     # Y400 - Warning state
    warning_hover: str = "#FFC400"  # Y300 - Warning hover
    warning_bold: str = "#FF8B00"     # Y500
    error: str = "#FF5630"       # R400 - Error state
    error_hover: str = "#FF7452"   # R300 - Error hover
    error_bold: str = "#DE350B"      # R500
    information: str = "#00B8D9"  # T400 - Info state
    information_hover: str = "#00C7E6"  # T300 - Info hover
    information_bold: str = "#00A3BF"    # T500

    # Discovery/purple
    discovery: str = "#6554C0"   # P400 - Discovery/purple
    discovery_hover: str = "#8777D9"  # P300 - Discovery hover
    discovery_bold: str = "#5243AA"    # P500

    # Overlay colors (for dark theme compatibility)
    overlay_background: str = "rgba(9, 30, 66, 0.54)"  # Semi-transparent overlay
    blanket: str = "rgba(9, 30, 66, 0.54)" # N700A
    blanket_selected: str = "rgba(56, 139, 255, 0.1)" # B100A
    blanket_danger: str = "rgba(255, 86, 48, 0.1)" # R100A


@dataclass
class TypographyTokens:
    """Typography design tokens aligned with Atlassian design system."""
    # Font families (Atlassian system fonts)
    font_family: str = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Noto Sans', 'Ubuntu', 'Droid Sans', 'Helvetica Neue', sans-serif"
    font_family_mono: str = "'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', 'Source Code Pro', 'Droid Sans Mono', 'Courier New', monospace"

    # Heading font sizes (Atlassian scale)
    font_size_h1: int = 28     # XXL heading
    font_size_h2: int = 24     # XL heading
    font_size_h3: int = 20     # Large heading
    font_size_h4: int = 16     # Medium heading
    font_size_h5: int = 14     # Small heading
    font_size_h6: int = 12     # XS heading

    # Body font sizes (Atlassian scale)
    font_size_body_large: int = 16   # Large body text
    font_size_body: int = 14         # Regular body text
    font_size_body_small: int = 12   # Small body text

    # UI font sizes (for buttons, labels, etc.)
    font_size_ui_large: int = 16     # Large UI elements
    font_size_ui: int = 14           # Regular UI elements
    font_size_ui_small: int = 12     # Small UI elements

    # Legacy sizes for backward compatibility
    font_size_xs: int = 12
    font_size_sm: int = 14
    font_size_md: int = 16
    font_size_lg: int = 20
    font_size_xl: int = 24
    font_size_xxl: int = 28

    # Line heights (Atlassian ratios)
    line_height_heading: float = 1.2     # Tight for headings
    line_height_body: float = 1.5        # Comfortable for body text
    line_height_ui: float = 1.4          # Standard for UI elements

    # Legacy line heights
    line_height_tight: float = 1.2
    line_height_normal: float = 1.4
    line_height_relaxed: float = 1.6

    # Font weights (Atlassian scale)
    font_weight_regular: int = 400
    font_weight_medium: int = 500
    font_weight_semibold: int = 600
    font_weight_bold: int = 700

    # Legacy weights
    font_weight_normal: int = 400
    font_weight_semibold: int = 600
    font_weight_bold: int = 700


@dataclass
class SpacingTokens:
    """Spacing design tokens."""
    # Base spacing scale (in px)
    space_0: int = 0
    space_025: int = 2      # 2px
    space_050: int = 4      # 4px
    space_075: int = 6      # 6px
    space_100: int = 8      # 8px
    space_150: int = 12     # 12px
    space_200: int = 16     # 16px
    space_250: int = 20     # 20px
    space_300: int = 24     # 24px
    space_400: int = 32     # 32px
    space_500: int = 40     # 40px
    space_600: int = 48     # 48px
    space_800: int = 64     # 64px
    space_1000: int = 80    # 80px


@dataclass
class BorderTokens:
    """Border and shadow design tokens."""
    # Border radius (in px)
    border_radius: int = 6      # Default border radius
    border_radius_small: int = 3  # Small border radius
    border_radius_large: int = 8  # Large border radius

    # Border width (in px)
    border_width: int = 1
    border_width_focused: int = 2

    # Box shadows
    shadow_small: str = "0 1px 2px 0 rgba(23, 43, 77, 0.12)"  # Small shadow
    shadow_medium: str = "0 4px 8px -2px rgba(23, 43, 77, 0.32)"  # Medium shadow
    shadow_large: str = "0 8px 16px -4px rgba(23, 43, 77, 0.32)"  # Large shadow


@dataclass
class ResponsiveTokens:
    """Responsive design tokens."""
    # Breakpoints
    breakpoints: Dict[str, int] = field(default_factory=lambda: {
        "mobile": 480,
        "tablet": 768,
        "desktop": 1024,
        "large_desktop": 1440
    })

    # Responsive font sizes (using clamp for fluid scaling)
    font_size_responsive_xs: str = "clamp(10px, 2vw, 12px)"
    font_size_responsive_sm: str = "clamp(12px, 2.5vw, 14px)"
    font_size_responsive_md: str = "clamp(14px, 3vw, 16px)"
    font_size_responsive_lg: str = "clamp(18px, 4vw, 20px)"
    font_size_responsive_xl: str = "clamp(20px, 5vw, 24px)"
    font_size_responsive_xxl: str = "clamp(24px, 6vw, 28px)"

    # Responsive spacing
    spacing_responsive_050: str = "clamp(2px, 0.5vw, 4px)"
    spacing_responsive_100: str = "clamp(4px, 1vw, 8px)"
    spacing_responsive_200: str = "clamp(8px, 2vw, 16px)"
    spacing_responsive_300: str = "clamp(12px, 3vw, 24px)"
    spacing_responsive_400: str = "clamp(16px, 4vw, 32px)"
    spacing_responsive_500: str = "clamp(20px, 5vw, 40px)"
    spacing_responsive_600: str = "clamp(24px, 6vw, 48px)"

    def get_current_breakpoint(self, screen_width: int) -> str:
        """Determine current breakpoint based on screen width."""
        if screen_width <= self.breakpoints["mobile"]:
            return "mobile"
        elif screen_width <= self.breakpoints["tablet"]:
            return "tablet"
        elif screen_width <= self.breakpoints["desktop"]:
            return "desktop"
        else:
            return "large_desktop"


@dataclass
class DesignTokens:
    """Complete design tokens collection."""
    colors: ColorTokens
    typography: TypographyTokens
    spacing: SpacingTokens
    borders: BorderTokens
    responsive: ResponsiveTokens = field(default_factory=ResponsiveTokens)

    # Theme variant
    scheme: ColorScheme = ColorScheme.LIGHT

    def get_dark_theme_tokens(self) -> DesignTokens:
        """Return dark theme variant of these tokens using Atlassian dark colors."""
        dark_colors = ColorTokens(
            background="#091E42",          # DN10 - Dark background
            surface="#161A1D",             # DN0 - Dark surface
            surface_sunken="#22272B",      # DN20 - Dark sunken
            surface_raised="#1D2125",      # DN30 - Dark raised surface
            text="#B6C2CF",                # DN800 - Light text (high contrast)
            text_subtle="#9FADBC",         # DN600 - Secondary text
            text_subtler="#8C9BAB",        # DN500 - Tertiary text
            text_disabled="#738496",      # DN400 - Disabled text
            text_on_primary="#FFFFFF",
            border="#454F59",              # DN40 - Dark border
            border_focused="#85B8FF",      # B100
            border_subtle="#303841",
            primary="#579DFF",             # B100
            primary_hover="#85B8FF",       # B75
            primary_pressed="#388BFF",     # B200
            success="#4BCE97",             # G200
            success_hover="#7EE2B8",       # G100
            success_bold="#21A366",        # G300
            warning="#E2B203",            # Y200
            warning_hover="#F5CD47",      # Y100
            warning_bold="#CF9F02",        # Y300
            error="#F87462",              # R200
            error_hover="#FF9C8F",         # R100
            error_bold="#E14B31",         # R300
            information="#60C6D2",         # T200
            information_hover="#8BDBE5",   # T100
            information_bold="#35A8B1",        # T300
            discovery="#9F8FEF",           # P200
            discovery_hover="#B8ACF6",     # P100
            discovery_bold="#8270DB",        # P300
            overlay_background="rgba(23, 43, 77, 0.9)",  # Dark overlay
            blanket="rgba(23, 43, 77, 0.9)",
            blanket_selected="rgba(87, 157, 255, 0.15)",
            blanket_danger="rgba(248, 116, 98, 0.15)"
        )

        return DesignTokens(
            colors=dark_colors,
            typography=self.typography,
            spacing=self.spacing,
            borders=self.borders,
            responsive=self.responsive,
            scheme=ColorScheme.DARK
        )


# Default design tokens (light theme)
DEFAULT_TOKENS = DesignTokens(
    colors=ColorTokens(),
    typography=TypographyTokens(),
    spacing=SpacingTokens(),
    borders=BorderTokens()
)


def get_css_variables(tokens: DesignTokens) -> Dict[str, str]:
    """
    Convert design tokens to CSS custom properties.

    This allows easy integration with QSS (Qt Style Sheets).
    """
    css_vars = {}

    # Colors
    color_map = {
        'ds-background': tokens.colors.background,
        'ds-surface': tokens.colors.surface,
        'ds-surface-sunken': tokens.colors.surface_sunken,
        'ds-surface-raised': tokens.colors.surface_raised,
        'ds-text': tokens.colors.text,
        'ds-text-subtle': tokens.colors.text_subtle,
        'ds-text-subtler': tokens.colors.text_subtler,
        'ds-text-disabled': tokens.colors.text_disabled,
        'ds-text-on-primary': tokens.colors.text_on_primary,
        'ds-border': tokens.colors.border,
        'ds-border-focused': tokens.colors.border_focused,
        'ds-border-subtle': tokens.colors.border_subtle,
        'ds-primary': tokens.colors.primary,
        'ds-primary-hover': tokens.colors.primary_hover,
        'ds-primary-pressed': tokens.colors.primary_pressed,
        'ds-success': tokens.colors.success,
        'ds-success-hover': tokens.colors.success_hover,
        'ds-success-bold': tokens.colors.success_bold,
        'ds-warning': tokens.colors.warning,
        'ds-warning-hover': tokens.colors.warning_hover,
        'ds-warning-bold': tokens.colors.warning_bold,
        'ds-error': tokens.colors.error,
        'ds-error-hover': tokens.colors.error_hover,
        'ds-error-bold': tokens.colors.error_bold,
        'ds-information': tokens.colors.information,
        'ds-information-hover': tokens.colors.information_hover,
        'ds-information-bold': tokens.colors.information_bold,
        'ds-discovery': tokens.colors.discovery,
        'ds-discovery-hover': tokens.colors.discovery_hover,
        'ds-discovery-bold': tokens.colors.discovery_bold,
        'ds-overlay-background': tokens.colors.overlay_background,
        'ds-blanket': tokens.colors.blanket,
        'ds-blanket-selected': tokens.colors.blanket_selected,
        'ds-blanket-danger': tokens.colors.blanket_danger,
    }
    css_vars.update(color_map)

    # Typography
    typo_map = {
        'ds-font-family': tokens.typography.font_family,
        'ds-font-family-mono': tokens.typography.font_family_mono,
        'ds-font-size-h1': f"{tokens.typography.font_size_h1}px",
        'ds-font-size-h2': f"{tokens.typography.font_size_h2}px",
        'ds-font-size-h3': f"{tokens.typography.font_size_h3}px",
        'ds-font-size-h4': f"{tokens.typography.font_size_h4}px",
        'ds-font-size-h5': f"{tokens.typography.font_size_h5}px",
        'ds-font-size-h6': f"{tokens.typography.font_size_h6}px",
        'ds-font-size-body-large': f"{tokens.typography.font_size_body_large}px",
        'ds-font-size-body': f"{tokens.typography.font_size_body}px",
        'ds-font-size-body-small': f"{tokens.typography.font_size_body_small}px",
        'ds-font-size-ui-large': f"{tokens.typography.font_size_ui_large}px",
        'ds-font-size-ui': f"{tokens.typography.font_size_ui}px",
        'ds-font-size-ui-small': f"{tokens.typography.font_size_ui_small}px",
        'ds-line-height-heading': str(tokens.typography.line_height_heading),
        'ds-line-height-body': str(tokens.typography.line_height_body),
        'ds-line-height-ui': str(tokens.typography.line_height_ui),
        'ds-font-weight-regular': str(tokens.typography.font_weight_regular),
        'ds-font-weight-medium': str(tokens.typography.font_weight_medium),
        'ds-font-weight-semibold': str(tokens.typography.font_weight_semibold),
        'ds-font-weight-bold': str(tokens.typography.font_weight_bold),
        # Legacy support
        'ds-font-size-xs': f"{tokens.typography.font_size_xs}px",
        'ds-font-size-sm': f"{tokens.typography.font_size_sm}px",
        'ds-font-size-md': f"{tokens.typography.font_size_md}px",
        'ds-font-size-lg': f"{tokens.typography.font_size_lg}px",
        'ds-font-size-xl': f"{tokens.typography.font_size_xl}px",
        'ds-font-size-xxl': f"{tokens.typography.font_size_xxl}px",
        'ds-font-weight-normal': str(tokens.typography.font_weight_normal),
    }
    css_vars.update(typo_map)

    # Spacing
    space_map = {
        f'ds-space-{k.split("_")[1]}': f"{v}px"
        for k, v in tokens.spacing.__dict__.items()
        if k.startswith('space_')
    }
    css_vars.update(space_map)

    # Borders
    border_map = {
        'ds-border-radius': f"{tokens.borders.border_radius}px",
        'ds-border-radius-small': f"{tokens.borders.border_radius_small}px",
        'ds-border-radius-large': f"{tokens.borders.border_radius_large}px",
        'ds-border-width': f"{tokens.borders.border_width}px",
        'ds-border-width-focused': f"{tokens.borders.border_width_focused}px",
        'ds-shadow-small': tokens.borders.shadow_small,
        'ds-shadow-medium': tokens.borders.shadow_medium,
        'ds-shadow-large': tokens.borders.shadow_large,
    }
    css_vars.update(border_map)

    return css_vars


class ThemeManager:
    """Manages application themes."""

    def __init__(self):
        self.themes: Dict[str, DesignTokens] = {}
        self.current_theme: str = "light"
        self._initialize_themes()

    def _initialize_themes(self):
        """Initialize built-in themes."""
        # Light theme
        self.themes["light"] = DEFAULT_TOKENS

        # Dark theme
        self.themes["dark"] = DEFAULT_TOKENS.get_dark_theme_tokens()

        # High contrast theme
        high_contrast_colors = ColorTokens(
            background="#000000",          # Pure black for maximum contrast
            surface="#1A1A1A",             # Dark surface
            surface_sunken="#333333",      # Dark sunken
            surface_raised="#0D0D0D",      # Very dark raised
            text="#FFFFFF",                # Pure white text
            text_subtle="#E0E0E0",         # Light gray secondary
            text_subtler="#C0C0C0",        # Medium gray tertiary
            text_disabled="#808080",       # Gray disabled text
            text_on_primary="#000000",
            border="#FFFFFF",              # White borders for high contrast
            border_focused="#FFFF00",      # Yellow focus for visibility
            border_subtle="#808080",
            primary="#FFFF00",             # Yellow primary
            primary_hover="#FFFF80",       # Light yellow hover
            primary_pressed="#CCCC00",     # Dark yellow pressed
            success="#00FF00",             # Pure green success
            success_hover="#80FF80",       # Light green hover
            success_bold="#00CC00",
            warning="#FFFF00",             # Yellow warning
            warning_hover="#FFFF80",       # Light yellow hover
            warning_bold="#CCCC00",
            error="#FF0000",               # Pure red error
            error_hover="#FF8080",         # Light red hover
            error_bold="#CC0000",
            information="#00FFFF",         # Cyan info
            information_hover="#80FFFF",   # Light cyan hover
            information_bold="#00CCCC",
            discovery="#FF00FF",           # Magenta discovery
            discovery_hover="#FF80FF",     # Light magenta hover
            discovery_bold="#CC00CC",
            overlay_background="rgba(0, 0, 0, 0.95)",  # Very dark overlay
            blanket="rgba(0, 0, 0, 0.95)",
            blanket_selected="rgba(255, 255, 0, 0.2)",
            blanket_danger="rgba(255, 0, 0, 0.2)"
        )
        self.themes["high_contrast"] = DesignTokens(
            colors=high_contrast_colors,
            typography=DEFAULT_TOKENS.typography,
            spacing=DEFAULT_TOKENS.spacing,
            borders=DEFAULT_TOKENS.borders,
            scheme=ColorScheme.DARK
        )

    def get_current_theme(self) -> Optional[DesignTokens]:
        """Get the current active theme."""
        return self.themes.get(self.current_theme)

    def set_theme(self, theme_name: str) -> bool:
        """Set the current theme by name."""
        if theme_name in self.themes:
            self.current_theme = theme_name
            return True
        return False

    def get_available_themes(self) -> List[str]:
        """Get list of available theme names."""
        return list(self.themes.keys())

    def add_custom_theme(self, name: str, tokens: DesignTokens):
        """Add a custom theme."""
        self.themes[name] = tokens

    def remove_theme(self, name: str) -> bool:
        """Remove a custom theme."""
        if name in self.themes and name not in ["light", "dark", "high_contrast"]:
            del self.themes[name]
            return True
        return False
