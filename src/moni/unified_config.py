"""
統合設定管理システム - Moni System Monitor

このモジュールは、従来のconfig.py、config_manager.py、secure_config.pyの機能を統合し、
より強力で使いやすい設定管理システムを提供します。

主な機能:
- Pydanticベースの型安全な設定モデル
- 複数設定ソースのサポート（ファイル、環境変数、コマンドライン）
- 設定の暗号化とセキュリティ機能
- 設定変更の監視とホットリロード
- 設定の検証とエラーハンドリング
- 高度なセキュリティ機能統合（secure_config.pyから）
- 設定マネージャーの統合（config_manager.pyから）
"""

from __future__ import annotations

import os
import json
import yaml
import logging
import threading
import hashlib
import secrets
import shlex
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Callable, Type, get_type_hints
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydantic import BaseModel, Field, ValidationError, field_validator
from .enhanced_security import (
    AdvancedInputValidator,
    EnhancedValidationError,
    SecurityMonitor,
    RateLimiter,
    security_monitor
)
from .timeseries_db import TimeSeriesConfig
from .webhook import WebhookConfig
from .network_dependency import DependencyMapConfig
from .advanced_network import AdvancedNetworkConfig


class ConfigFormat(Enum):
    """サポートする設定ファイル形式"""
    JSON = "json"
    YAML = "yaml"
    INI = "ini"
    ENV = "env"


class EncryptionLevel(Enum):
    """暗号化レベル"""
    NONE = "none"
    SENSITIVE_ONLY = "sensitive_only"
    ALL = "all"


@dataclass
class SecurityPolicy:
    """セキュリティポリシー設定"""
    max_config_size_mb: float = 10.0
    max_string_length: int = 1000
    max_array_length: int = 100
    max_nesting_depth: int = 10
    allowed_keys: Optional[Set[str]] = None
    forbidden_values: Set[str] = field(default_factory=lambda: {
        "password", "secret", "token", "key", "credential",
        "api_key", "private", "ssh", "cert"
    })
    require_encryption: bool = True
    require_signature: bool = True
    audit_all_changes: bool = True


class ConfigValidator:
    """設定データのセキュリティ検証"""

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        """セキュリティポリシーでバリデータを初期化"""
        self.policy = policy or SecurityPolicy()
        self._validation_errors = []

    def validate(self, data: Dict[str, Any], depth: int = 0) -> bool:
        """セキュリティポリシーに照らして設定データを検証"""
        self._validation_errors = []

        # ネスト深度チェック
        if depth > self.policy.max_nesting_depth:
            self._validation_errors.append(f"最大ネスト深度を超過: {depth}")
            return False

        # 各キー・値ペアを検証
        for key, value in data.items():
            if not self._validate_key(key):
                return False
            if not self._validate_value(value, depth):
                return False

        return len(self._validation_errors) == 0

    def _validate_key(self, key: str) -> bool:
        """設定キーを検証"""
        # 許可されたキーに対するチェック
        if self.policy.allowed_keys and key not in self.policy.allowed_keys:
            self._validation_errors.append(f"不正なキー: {key}")
            return False

        # 疑わしいパターンチェック
        suspicious_patterns = ["eval", "exec", "import", "__", "system", "shell"]
        for pattern in suspicious_patterns:
            if pattern in key.lower():
                self._validation_errors.append(f"疑わしいキーパターン: {key}")
                return False

        return True

    def _validate_value(self, value: Any, depth: int) -> bool:
        """設定値を検証"""
        if isinstance(value, str):
            return self._validate_string(value)
        elif isinstance(value, (list, tuple)):
            return self._validate_array(value, depth)
        elif isinstance(value, dict):
            return self.validate(value, depth + 1)
        elif isinstance(value, (int, float, bool, type(None))):
            return True
        else:
            self._validation_errors.append(f"無効な値タイプ: {type(value)}")
            return False

    def _validate_string(self, value: str) -> bool:
        """文字列値を検証（強化版）"""
        # 長さチェック
        if len(value) > self.policy.max_string_length:
            self._validation_errors.append(f"文字列が長すぎる: {len(value)} 文字")
            return False

        # 禁止値チェック
        value_lower = value.lower()
        for forbidden in self.policy.forbidden_values:
            if forbidden in value_lower and not value_lower.startswith("encrypted:"):
                self._validation_errors.append("潜在的に機密な値が検出されました")
                return False

        # AdvancedInputValidatorの検出機能を使用
        try:
            # SQLインジェクション検出
            if AdvancedInputValidator.detect_sql_injection(value):
                self._validation_errors.append("SQLインジェクション攻撃の可能性が検出されました")
                security_monitor.log_security_event(
                    "SQL_INJECTION_DETECTED", "SQLインジェクション攻撃の可能性が検出されました",
                    "high", "config_validation", {"input_value": value[:100]}
                )
                return False

            # XSS検出
            if AdvancedInputValidator.detect_xss(value):
                self._validation_errors.append("XSS攻撃の可能性が検出されました")
                security_monitor.log_security_event(
                    "XSS_DETECTED", "XSS攻撃の可能性が検出されました",
                    "high", "config_validation", {"input_value": value[:100]}
                )
                return False

            # パストラバーサル検出
            if AdvancedInputValidator.detect_path_traversal(value):
                self._validation_errors.append("パストラバーサル攻撃の可能性が検出されました")
                security_monitor.log_security_event(
                    "PATH_TRAVERSAL_DETECTED", "パストラバーサル攻撃の可能性が検出されました",
                    "high", "config_validation", {"input_value": value[:100]}
                )
                return False

        except Exception as e:
            logger.warning(f"高度なセキュリティ検証でエラーが発生しました: {e}")

        # インジェクションパターンチェック
        injection_patterns = [
            "<script", "javascript:", "onclick", "onerror",
            "../", "..\\", "%00", "\x00", "${", "#{",
            "'; DROP", "OR 1=1", "<!--", "-->", "<![CDATA["
        ]
        for pattern in injection_patterns:
            if pattern in value:
                self._validation_errors.append(f"潜在的なインジェクションパターン: {pattern}")
                return False

        return True

    def _validate_array(self, value: list, depth: int) -> bool:
        """配列値を検証"""
        if len(value) > self.policy.max_array_length:
            self._validation_errors.append(f"配列が長すぎる: {len(value)} 項目")
            return False

        for item in value:
            if not self._validate_value(item, depth):
                return False

        return True

    def get_errors(self) -> list[str]:
        """検証エラーを取得"""
        return self._validation_errors.copy()


def resolve_config_directory(app_name: str = "moni") -> Path:
    env_key = f"{app_name.upper()}_CONFIG_DIR"
    env_dir = os.environ.get(env_key)
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / ".config" / app_name


DEFAULT_CONFIG_DIR = resolve_config_directory()
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


logger = logging.getLogger(__name__)


# Pydanticベースの設定モデル群
class OverlaySettings(BaseModel):
    visible: bool = Field(default=True, description="Whether the overlay window is visible")
    always_on_top: bool = Field(default=True, description="Keep overlay above other windows")
    refresh_interval_ms: int = Field(default=1000, description="Metric refresh interval in milliseconds (1000ms = smooth updates)")
    opacity: float = Field(default=0.85, ge=0.2, le=1.0, description="Overlay window opacity")
    position_x: int = Field(default=-1, description="X position on screen (-1 = auto)")
    position_y: int = Field(default=-1, description="Y position on screen (-1 = auto)")
    width: int = Field(default=350, ge=200, le=800, description="Overlay width in pixels")
    height: int = Field(default=-1, description="Overlay height (-1 = auto-size)")
    compact_mode: bool = Field(default=False, description="Use compact display mode to save space")
    show_sparklines: bool = Field(default=True, description="Show mini trend graphs for metrics")
    animate_transitions: bool = Field(default=True, description="Smooth animations for value changes")


class LoggingSettings(BaseModel):
    enabled: bool = Field(default=False, description="Enable periodic metric logging")
    file_path: Path = Field(
        default_factory=lambda: DEFAULT_CONFIG_DIR / "logs" / "metrics.jsonl",
        description="Destination file for metrics log entries",
    )
    interval_ms: int = Field(
        default=5000,
        ge=1000,
        le=600_000,
        description="Minimum interval between logged samples in milliseconds",
    )


class ThemeColors(BaseModel):
    background: str = Field(default="#1E1E1E", description="Main background color", pattern=r'^#[0-9A-Fa-f]{6}$')
    surface: str = Field(default="#252526", description="Surface color for cards/panels", pattern=r'^#[0-9A-Fa-f]{6}$')
    primary: str = Field(default="#0E639C", description="Primary accent color", pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary: str = Field(default="#007ACC", description="Secondary color", pattern=r'^#[0-9A-Fa-f]{6}$')
    text: str = Field(default="#FFFFFF", description="Primary text color", pattern=r'^#[0-9A-Fa-f]{6}$')
    text_secondary: str = Field(default="#D4D4D4", description="Secondary text color", pattern=r'^#[0-9A-Fa-f]{6}$')
    success: str = Field(default="#2EA043", description="Success color", pattern=r'^#[0-9A-Fa-f]{6}$')
    warning: str = Field(default="#D29922", description="Warning color", pattern=r'^#[0-9A-Fa-f]{6}$')
    error: str = Field(default="#F85149", description="Error color", pattern=r'^#[0-9A-Fa-f]{6}$')
    border: str = Field(default="#3C3C3C", description="Border color", pattern=r'^#[0-9A-Fa-f]{6}$')

    @field_validator('background', 'surface', 'primary', 'secondary', 'text', 'text_secondary', 'success', 'warning', 'error', 'border', mode='after')
    @classmethod
    def validate_color_format(cls, v: str) -> str:
        """色値のフォーマット検証"""
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
            raise ValueError(f"Color must be in format #RRGGBB, got: {v}")
        return v


class ThemeSettings(BaseModel):
    name: str = Field(description="Theme display name")
    description: str = Field(description="Theme description")
    colors: ThemeColors = Field(description="Color palette for the theme")
    font_family: str = Field(default="Arial", description="Font family")
    font_size: int = Field(default=10, ge=8, le=16, description="Base font size")
    border_radius: int = Field(default=4, ge=0, le=12, description="Border radius for UI elements")


class ThemeManager(BaseModel):
    themes: dict[str, ThemeSettings] = Field(default_factory=dict)
    current_theme: str = Field(default="default", description="Currently active theme name")

    def get_current_theme(self) -> ThemeSettings | None:
        return self.themes.get(self.current_theme)

    def set_current_theme(self, theme_name: str) -> bool:
        if theme_name in self.themes:
            self.current_theme = theme_name
            return True
        return False

    def create_theme(self, name: str, description: str, base_theme: str | None = None) -> ThemeSettings:
        if base_theme and base_theme in self.themes:
            base = self.themes[base_theme]
            theme = ThemeSettings(
                name=name,
                description=description,
                colors=base.colors.model_copy(),
                font_family=base.font_family,
                font_size=base.font_size,
                border_radius=base.border_radius
            )
        else:
            theme = ThemeSettings(
                name=name,
                description=description,
                colors=ThemeColors(),
                font_family="Arial",
                font_size=10,
                border_radius=4
            )
        self.themes[name] = theme
        return theme


class AlertThresholds(BaseModel):
    cpu_percent: float = Field(default=85.0, ge=0.0, le=100.0, description="CPU usage threshold percentage")
    memory_percent: float = Field(default=90.0, ge=0.0, le=100.0, description="Memory usage threshold percentage")
    gpu_usage_percent: float = Field(default=95.0, ge=0.0, le=100.0, description="GPU usage threshold percentage")
    gpu_memory_percent: float = Field(default=95.0, ge=0.0, le=100.0, description="GPU memory threshold percentage")
    gpu_temperature_celsius: float = Field(default=85.0, ge=0.0, le=150.0, description="GPU temperature threshold in Celsius")
    cpu_temperature_celsius: float = Field(default=80.0, ge=0.0, le=150.0, description="CPU temperature threshold in Celsius")
    disk_usage_percent: float = Field(default=95.0, ge=0.0, le=100.0, description="Disk usage threshold percentage")
    swap_usage_percent: float = Field(default=75.0, ge=0.0, le=100.0, description="Swap usage threshold percentage")
    load_average_per_core: float = Field(default=3.0, ge=0.0, le=10.0, description="Load average per CPU core threshold")
    network_error_rate_percent: float = Field(default=5.0, ge=0.0, le=100.0, description="Network packet error rate threshold")
    battery_percent: float = Field(default=20.0, ge=0.0, le=100.0, description="Battery low threshold percentage")

    @field_validator('gpu_temperature_celsius', 'cpu_temperature_celsius', mode='after')
    @classmethod
    def validate_temperature_thresholds(cls, v: float) -> float:
        """温度閾値の詳細検証"""
        if v < 30.0:
            raise ValueError("Temperature threshold cannot be below 30°C (too low for monitoring)")
        elif v > 120.0:
            raise ValueError("Temperature threshold cannot exceed 120°C (dangerous temperature)")
        return v


class NotificationSettings(BaseModel):
    enabled: bool = Field(default=True, description="Enable desktop notifications")
    show_critical_only: bool = Field(default=False, description="Only show notifications for critical alerts")
    auto_dismiss_seconds: int = Field(default=8, ge=1, le=300, description="Auto-dismiss notifications after seconds")
    persistent_critical: bool = Field(default=True, description="Keep critical alerts visible until acknowledged")
    play_sound: bool = Field(default=True, description="Play notification sound")
    sound_volume: float = Field(default=0.5, ge=0.0, le=1.0, description="Notification sound volume (0.0-1.0)")
    minimize_gaming_mode: bool = Field(default=True, description="Minimize notifications during fullscreen games")


class HistorySettings(BaseModel):
    enabled: bool = Field(default=True, description="Enable metric history tracking")
    max_entries: int = Field(default=1000, ge=100, le=10000, description="Maximum number of history entries to keep")


class NetworkBandwidthSettings(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable HTTPS bandwidth diagnostics (explicit opt-in only)",
    )
    continuous_monitoring: bool = Field(
        default=False,
        description="When enabled, perform bandwidth probes at each refresh interval (can be costly)",
    )
    cooldown_seconds: int = Field(
        default=900,
        ge=60,
        le=86400,
        description="Minimum number of seconds between automated bandwidth probes when not in continuous mode",
    )
    download_endpoint: str = Field(
        default="",
        description="HTTPS endpoint used for download bandwidth tests when enabled (must be valid HTTPS URL or empty)",
    )
    upload_endpoint: str = Field(
        default="",
        description="HTTPS endpoint used for upload bandwidth tests when enabled (must be valid HTTPS URL or empty)",
    )

    def model_post_init(self, __context) -> None:
        """Validate and sanitize URLs after model initialization."""
        validator = AdvancedInputValidator()
        try:
            if self.download_endpoint and self.download_endpoint.strip():
                self.download_endpoint = validator.validate_https_url(self.download_endpoint.strip())
            else:
                self.download_endpoint = ""
        except EnhancedValidationError:
            self.download_endpoint = ""
            self.enabled = False

        try:
            if self.upload_endpoint and self.upload_endpoint.strip():
                self.upload_endpoint = validator.validate_https_url(self.upload_endpoint.strip())
            else:
                self.upload_endpoint = ""
        except EnhancedValidationError:
            self.upload_endpoint = ""

        if self.enabled and not self.download_endpoint:
            self.enabled = False

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "NetworkBandwidthSettings":
        raw_enabled = data.get("enabled", cls.model_fields['enabled'].default)
        if isinstance(raw_enabled, str):
            enabled = raw_enabled.strip().lower() in {"1", "true", "yes", "on"}
        else:
            enabled = bool(raw_enabled)
        raw_continuous = data.get("continuous_monitoring", cls.model_fields['continuous_monitoring'].default)
        if isinstance(raw_continuous, str):
            continuous = raw_continuous.strip().lower() in {"1", "true", "yes", "on"}
        else:
            continuous = bool(raw_continuous)
        raw_cooldown = data.get("cooldown_seconds", cls.model_fields['cooldown_seconds'].default)
        try:
            cooldown = int(raw_cooldown)
        except (TypeError, ValueError):
            cooldown = cls.model_fields['cooldown_seconds'].default
        cooldown = max(60, min(cooldown, 86400))
        download = data.get("download_endpoint", cls.model_fields['download_endpoint'].default)
        upload = data.get("upload_endpoint", cls.model_fields['upload_endpoint'].default)
        return cls(
            enabled=enabled,
            continuous_monitoring=continuous,
            cooldown_seconds=cooldown,
            download_endpoint=download,
            upload_endpoint=upload,
        )


class NetworkQualitySettings(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable outbound network quality probes",
    )
    hosts: List[str] = Field(
        default_factory=list,
        description="List of IP addresses or hostnames to probe. Leave empty to disable ping tests.",
    )
    attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of ICMP ping attempts per host",
    )
    timeout_ms: int = Field(
        default=800,
        ge=100,
        le=5000,
        description="Timeout per ICMP attempt in milliseconds",
    )
    cooldown_seconds: int = Field(
        default=120,
        ge=10,
        le=3600,
        description="Minimum seconds between successive network quality sweeps",
    )

    def model_post_init(self, __context) -> None:
        """Validate and sanitize quality test hosts after initialization."""
        import ipaddress
        validated_hosts = []
        for host in self.hosts:
            if not host or not isinstance(host, str):
                continue
            candidate = host.strip()
            if not candidate:
                continue
            try:
                ipaddress.ip_address(candidate)
                validated_hosts.append(candidate)
            except ValueError:
                if len(candidate) <= 255 and all(c.isalnum() or c in '.-' for c in candidate):
                    validated_hosts.append(candidate)
        self.hosts = validated_hosts
        if self.enabled and not self.hosts:
            self.enabled = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NetworkQualitySettings":
        enabled_raw = data.get("enabled", cls.model_fields['enabled'].default)
        if isinstance(enabled_raw, str):
            enabled = enabled_raw.strip().lower() in {"1", "true", "yes", "on"}
        else:
            enabled = bool(enabled_raw)
        hosts_raw = data.get("hosts", cls.model_fields['hosts'].default_factory())
        if isinstance(hosts_raw, str):
            hosts = [item.strip() for item in hosts_raw.split(",") if item.strip()]
        elif isinstance(hosts_raw, (list, tuple)):
            hosts = [str(item).strip() for item in hosts_raw if str(item).strip()]
        else:
            hosts = []
        attempts_raw = data.get("attempts", cls.model_fields['attempts'].default)
        try:
            attempts = int(attempts_raw)
        except (TypeError, ValueError):
            attempts = cls.model_fields['attempts'].default
        attempts = max(1, min(attempts, 10))
        timeout_raw = data.get("timeout_ms", cls.model_fields['timeout_ms'].default)
        try:
            timeout_ms = int(timeout_raw)
        except (TypeError, ValueError):
            timeout_ms = cls.model_fields['timeout_ms'].default
        timeout_ms = max(100, min(timeout_ms, 5000))
        cooldown_raw = data.get("cooldown_seconds", cls.model_fields['cooldown_seconds'].default)
        try:
            cooldown = int(cooldown_raw)
        except (TypeError, ValueError):
            cooldown = cls.model_fields['cooldown_seconds'].default
        cooldown = max(10, min(cooldown, 3600))
        return cls(
            enabled=enabled,
            hosts=hosts,
            attempts=attempts,
            timeout_ms=timeout_ms,
            cooldown_seconds=cooldown,
        )


class NetworkAutomationSettings(BaseModel):
    bandwidth_test: NetworkBandwidthSettings = Field(
        default_factory=NetworkBandwidthSettings,
        description="Configuration for HTTP-based bandwidth tests",
    )
    quality_test: NetworkQualitySettings = Field(
        default_factory=NetworkQualitySettings,
        description="Configuration for outbound network quality probes",
    )


class AlertSettings(BaseModel):
    enabled: bool = Field(default=True, description="Enable threshold-based alerts")
    show_overlay_banner: bool = Field(
        default=True,
        description="Display alert banner within overlay when alerts trigger",
    )
    cooldown_seconds: int = Field(
        default=60,
        ge=5,
        le=3600,
        description="Cooldown period in seconds before repeating the same alert",
    )
    thresholds: AlertThresholds = Field(default_factory=AlertThresholds)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


class ExportSettings(BaseModel):
    json_compact: bool = Field(
        default=False,
        description="Emit compact JSON exports instead of pretty-printed output",
    )


class AutomationSettings(BaseModel):
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    alerts: AlertSettings = Field(default_factory=AlertSettings)
    history: HistorySettings = Field(default_factory=HistorySettings)
    network: NetworkAutomationSettings = Field(default_factory=NetworkAutomationSettings)
    export: ExportSettings = Field(default_factory=ExportSettings)


class InternationalizationSettings(BaseModel):
    """国際化設定"""
    locale: str = Field(default="en", description="Current locale (e.g., 'en', 'ja', 'zh-CN')")
    fallback_locale: str = Field(default="en", description="Fallback locale when translation is missing")
    auto_detect: bool = Field(default=True, description="Automatically detect system locale")
    enable_rtl: bool = Field(default=False, description="Enable right-to-left text support")
    date_format: str = Field(default="short", description="Date format style (short, medium, long, full)")
    time_format: str = Field(default="24h", description="Time format (12h, 24h)")
    number_format: str = Field(default="default", description="Number format style")
    currency_format: str = Field(default="default", description="Currency format style")
    first_day_of_week: int = Field(default=1, ge=1, le=7, description="First day of week (1=Monday, 7=Sunday)")
    text_direction: str = Field(default="ltr", description="Text direction (ltr, rtl)")

    @field_validator('locale', mode='after')
    @classmethod
    def validate_locale(cls, v: str) -> str:
        """ロケールの形式を検証"""
        if not v or not isinstance(v, str):
            return "en"

        # 言語コードの形式を検証 (e.g., 'en', 'ja', 'zh-CN', 'pt-BR')
        import re
        if re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
            return v
        elif re.match(r'^[a-z]{2,3}$', v):
            return v
        else:
            return "en"

    @field_validator('date_format', mode='after')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """日付フォーマットの検証"""
        valid_formats = ['short', 'medium', 'long', 'full', 'custom']
        return v if v in valid_formats else 'short'

    @field_validator('time_format', mode='after')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """時刻フォーマットの検証"""
        return v if v in ['12h', '24h'] else '24h'

    @field_validator('text_direction', mode='after')
    @classmethod
    def validate_text_direction(cls, v: str) -> str:
        """テキスト方向の検証"""
        return v if v in ['ltr', 'rtl'] else 'ltr'


class ProfileManager(BaseModel):
    profiles: dict[str, ProfileSettings] = Field(default_factory=dict)
    current_profile: str = Field(default="default", description="Currently active profile name")

    def get_current_profile(self) -> ProfileSettings | None:
        return self.profiles.get(self.current_profile)

    def set_current_profile(self, profile_name: str) -> bool:
        if profile_name in self.profiles:
            self.current_profile = profile_name
            return True
        return False

    def create_profile(self, name: str, description: str, base_profile: str | None = None) -> ProfileSettings:
        if base_profile and base_profile in self.profiles:
            base = self.profiles[base_profile]
            profile = ProfileSettings(
                name=name,
                description=description,
                metrics=base.metrics.copy(),
                overlay=base.overlay.model_copy(),
                automation=base.automation.model_copy()
            )
        else:
            profile = ProfileSettings(
                name=name,
                description=description,
                metrics=[
                    "cpu_usage",
                    "memory_usage",
                    "gpu_usage",
                    "system_temperatures"
                ],
                overlay=OverlaySettings(),
                automation=AutomationSettings()
            )
        self.profiles[name] = profile
        return profile


class MoniConfig(BaseModel):
    """統合設定クラス - Moni System Monitorのメイン設定"""
    metrics: List[str] = Field(
        default_factory=lambda: [
            "cpu_usage",
            "memory_usage",
            "swap_usage",
            "network_io",
            "disk_io",
            "system_uptime",
        ],
        description="Ordered list of metric identifiers to display",
        min_items=1,
        max_items=50
    )
    overlay: OverlaySettings = Field(default_factory=OverlaySettings)
    automation: AutomationSettings = Field(default_factory=AutomationSettings)
    internationalization: InternationalizationSettings = Field(default_factory=InternationalizationSettings)
    themes: ThemeManager = Field(default_factory=ThemeManager)
    profiles: ProfileManager = Field(default_factory=ProfileManager)
    timeseries: TimeSeriesConfig = Field(default_factory=TimeSeriesConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    dependency_map: DependencyMapConfig = Field(default_factory=DependencyMapConfig)
    advanced_network: AdvancedNetworkConfig = Field(default_factory=AdvancedNetworkConfig)

    @field_validator('metrics', mode='after')
    @classmethod
    def validate_metrics(cls, v: List[str]) -> List[str]:
        """メトリクスリストの詳細検証"""
        if not v:
            raise ValueError("metrics cannot be empty")

        valid_metrics = {
            "cpu_usage", "memory_usage", "swap_usage", "network_io", "disk_io",
            "system_uptime", "gpu_usage", "gpu_memory", "system_temperatures",
            "top_cpu_processes", "top_memory_processes", "battery_status",
            "network_connections", "disk_smart", "cpu_frequency", "memory_details"
        }

        invalid_metrics = set(v) - valid_metrics
        if invalid_metrics:
            raise ValueError(f"Invalid metrics: {invalid_metrics}")

        # 重複チェック
        if len(v) != len(set(v)):
            raise ValueError("metrics contains duplicates")

        return v

    @field_validator('internationalization', mode='after')
    @classmethod
    def validate_internationalization_settings(cls, v: InternationalizationSettings) -> InternationalizationSettings:
        """国際化設定の詳細検証"""
        # ロケールの検証
        if not v.locale:
            v.locale = "en"

        # フォールバックロケールの検証
        if not v.fallback_locale:
            v.fallback_locale = "en"

        # RTL言語の場合はテキスト方向を自動設定
        rtl_languages = {'ar', 'he', 'fa', 'ur'}
        if v.locale.split('-')[0] in rtl_languages:
            v.text_direction = "rtl"
            v.enable_rtl = True

        # 週の開始日の地域対応
        if v.locale.startswith('en') and v.locale.endswith('US'):
            v.first_day_of_week = 7  # Sunday
        elif v.locale.startswith('en') and not v.locale.endswith('US'):
            v.first_day_of_week = 1  # Monday

        return v
    @classmethod
    def validate_overlay_settings(cls, v: OverlaySettings) -> OverlaySettings:
        """オーバーレイ設定の詳細検証"""
        # 位置が自動の場合、サイズも自動であるべき
        if v.position_x == -1 and v.position_y == -1:
            pass  # 自動位置はOK
        elif v.position_x < 0 or v.position_y < 0:
            raise ValueError("position_x and position_y must both be >= 0 or both be -1 (auto)")

        # 高さが自動の場合のみ幅が200-800の範囲
        if v.height == -1:
            if not (200 <= v.width <= 800):
                raise ValueError("width must be between 200 and 800 when height is auto")
        else:
            if not (200 <= v.width <= 800 and 100 <= v.height <= 600):
                raise ValueError("width must be 200-800 and height must be 100-600 when height is not auto")

        # リフレッシュ間隔の妥当性チェック
        if v.refresh_interval_ms < 100:
            raise ValueError("refresh_interval_ms must be at least 100ms")
        elif v.refresh_interval_ms > 30000:  # 30秒
            raise ValueError("refresh_interval_ms cannot exceed 30000ms")

        return v

    @field_validator('automation', mode='after')
    @classmethod
    def validate_automation_settings(cls, v: AutomationSettings) -> AutomationSettings:
        """自動化設定の詳細検証"""
        # ログ設定の検証
        logging_settings = v.logging
        if logging_settings.enabled:
            if logging_settings.interval_ms < 1000:
                raise ValueError("logging interval_ms must be at least 1000ms when enabled")
            if logging_settings.interval_ms > 3600000:  # 1時間
                raise ValueError("logging interval_ms cannot exceed 3600000ms")

        # アラート設定の検証
        alert_settings = v.alerts
        if alert_settings.enabled:
            cooldown = alert_settings.cooldown_seconds
            if cooldown < 5:
                raise ValueError("alert cooldown_seconds must be at least 5")
            if cooldown > 3600:
                raise ValueError("alert cooldown_seconds cannot exceed 3600")

            # 閾値の検証
            thresholds = alert_settings.thresholds
            if thresholds.cpu_percent > 100 or thresholds.cpu_percent < 0:
                raise ValueError("cpu_percent threshold must be between 0 and 100")
            if thresholds.memory_percent > 100 or thresholds.memory_percent < 0:
                raise ValueError("memory_percent threshold must be between 0 and 100")
            if thresholds.disk_usage_percent > 100 or thresholds.disk_usage_percent < 0:
                raise ValueError("disk_usage_percent threshold must be between 0 and 100")

        return v

    @field_validator('profiles', mode='after')
    @classmethod
    def validate_profiles(cls, v: ProfileManager) -> ProfileManager:
        """プロファイル設定の詳細検証"""
        if not v.profiles:
            raise ValueError("at least one profile must be defined")

        # デフォルトプロファイルが存在するかチェック
        if "default" not in v.profiles:
            raise ValueError("default profile must be defined")

        # 各プロファイルの検証
        for profile_name, profile in v.profiles.items():
            if not profile_name or len(profile_name) > 50:
                raise ValueError(f"profile name '{profile_name}' must be 1-50 characters")

            if not profile.metrics:
                raise ValueError(f"profile '{profile_name}' must have at least one metric")

            # メトリクスの重複チェック
            if len(profile.metrics) != len(set(profile.metrics)):
                raise ValueError(f"profile '{profile_name}' contains duplicate metrics")

        return v

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize default profiles if not present
        self._initialize_default_profiles()
        # Initialize default themes if not present
        self._initialize_default_themes()
        # Initialize default internationalization settings
        self._initialize_default_internationalization()

    def _sanitize_before_save(self) -> List[str]:
        warnings: List[str] = []
        warnings.extend(self._sanitize_webhook_config())
        warnings.extend(self._sanitize_network_settings())
        return warnings

    def _sanitize_webhook_config(self) -> List[str]:
        warnings: List[str] = []
        original = copy.deepcopy(self.webhook)
        self.webhook.sanitize()

        if original.enabled and not self.webhook.enabled:
            warnings.append("Webhook configuration disabled due to invalid URL or headers")
        if original.url and not self.webhook.url:
            warnings.append("Removed invalid webhook URL from configuration")
        removed_headers = set((original.headers or {}).keys()) - set((self.webhook.headers or {}).keys())
        if removed_headers:
            warnings.append("Removed invalid webhook headers: " + ", ".join(sorted(removed_headers)))

        return warnings

    def _sanitize_network_settings(self) -> List[str]:
        warnings: List[str] = []

        network_settings = self.automation.network
        old_bandwidth = network_settings.bandwidth_test
        old_quality = network_settings.quality_test

        sanitized_network = NetworkAutomationSettings.model_validate(network_settings.model_dump())
        new_bandwidth = sanitized_network.bandwidth_test
        new_quality = sanitized_network.quality_test

        if old_bandwidth.download_endpoint and not new_bandwidth.download_endpoint:
            warnings.append("Removed invalid bandwidth download endpoint")
        if old_bandwidth.upload_endpoint and not new_bandwidth.upload_endpoint:
            warnings.append("Removed invalid bandwidth upload endpoint")
        if old_bandwidth.enabled and not new_bandwidth.enabled:
            warnings.append("Bandwidth testing disabled due to missing valid endpoints")

        removed_hosts = set(old_quality.hosts) - set(new_quality.hosts)
        if removed_hosts:
            warnings.append("Removed invalid network quality hosts: " + ", ".join(sorted(removed_hosts)))
        if old_quality.enabled and not new_quality.enabled:
            warnings.append("Network quality testing disabled due to missing valid hosts")

        if sanitized_network != network_settings:
            self.automation = self.automation.model_copy(update={"network": sanitized_network})

        return warnings

    def _initialize_default_themes(self):
        if not self.themes.themes:
            # Default light theme
            default_theme = ThemeSettings(
                name="Default Light",
                description="Clean light theme with blue accents",
                colors=ThemeColors(
                    background="#ffffff",
                    surface="#f8f9fa",
                    primary="#4a90e2",
                    secondary="#6c757d",
                    text="#212529",
                    text_secondary="#6c757d",
                    success="#28a745",
                    warning="#ffc107",
                    error="#dc3545",
                    border="#dee2e6"
                ),
                font_family="Arial",
                font_size=10,
                border_radius=4
            )
            self.themes.themes["default"] = default_theme

            # Dark theme
            dark_theme = ThemeSettings(
                name="Dark",
                description="Modern dark theme for low-light environments",
                colors=ThemeColors(
                    background="#1a1a1a",
                    surface="#2d2d2d",
                    primary="#5bc0de",
                    secondary="#adb5bd",
                    text="#ffffff",
                    text_secondary="#adb5bd",
                    success="#5cb85c",
                    warning="#f0ad4e",
                    error="#d9534f",
                    border="#404040"
                ),
                font_family="Arial",
                font_size=10,
                border_radius=6
            )
            self.themes.themes["dark"] = dark_theme

            # Blue theme
            blue_theme = ThemeSettings(
                name="Ocean Blue",
                description="Calming blue theme with oceanic colors",
                colors=ThemeColors(
                    background="#f0f8ff",
                    surface="#e6f3ff",
                    primary="#0077be",
                    secondary="#5a9fd4",
                    text="#003d66",
                    text_secondary="#0066cc",
                    success="#28a745",
                    warning="#ffc107",
                    error="#dc3545",
                    border="#b3d9ff"
                ),
                font_family="Arial",
                font_size=10,
                border_radius=8
            )
            self.themes.themes["blue"] = blue_theme

            # Green theme
            green_theme = ThemeSettings(
                name="Forest Green",
                description="Natural green theme inspired by nature",
                colors=ThemeColors(
                    background="#f5fff5",
                    surface="#e8f5e8",
                    primary="#2e7d32",
                    secondary="#4caf50",
                    text="#1b5e20",
                    text_secondary="#388e3c",
                    success="#4caf50",
                    warning="#ff9800",
                    error="#d32f2f",
                    border="#c8e6c9"
                ),
                font_family="Arial",
                font_size=10,
                border_radius=6
            )
            self.themes.themes["green"] = green_theme

            # High Contrast theme
            contrast_theme = ThemeSettings(
                name="High Contrast",
                description="High contrast theme for accessibility",
                colors=ThemeColors(
                    background="#000000",
                    surface="#1a1a1a",
                    primary="#ffff00",
                    secondary="#ffffff",
                    text="#ffffff",
                    text_secondary="#ffff00",
                    success="#00ff00",
                    warning="#ff8000",
                    error="#ff0000",
                    border="#ffffff"
                ),
                font_family="Arial",
                font_size=11,
                border_radius=2
            )
            self.themes.themes["contrast"] = contrast_theme

    def _initialize_default_internationalization(self):
        """デフォルトの国際化設定を初期化"""
        import locale

        # システムロケールを検出して自動設定
        if self.internationalization.auto_detect:
            try:
                system_locale = locale.getlocale()[0]
                if system_locale:
                    # 言語コードを抽出 (e.g., 'ja_JP' -> 'ja')
                    lang_code = system_locale.split('_')[0].lower()
                    if lang_code in ['en', 'ja', 'zh', 'es', 'fr', 'de', 'ko', 'pt', 'ru', 'ar', 'he', 'fa', 'ur']:
                        self.internationalization.locale = lang_code
            except Exception:
                pass  # ロケール検出に失敗した場合はデフォルトを使用

        # 地域別設定の調整
        if self.internationalization.locale.startswith('zh'):
            self.internationalization.date_format = "medium"
            self.internationalization.number_format = "default"
        elif self.internationalization.locale.startswith('ja'):
            self.internationalization.date_format = "long"
            self.internationalization.time_format = "24h"
        elif self.internationalization.locale.startswith('en'):
            if 'US' in self.internationalization.locale:
                self.internationalization.first_day_of_week = 7  # Sunday
                self.internationalization.time_format = "12h"
            else:
                self.internationalization.first_day_of_week = 1  # Monday

    def _initialize_default_profiles(self):
        if not self.profiles.profiles:
            # Default profile
            default_profile = ProfileSettings(
                name="Default",
                description="Standard system monitoring",
                metrics=self.metrics.copy(),
                overlay=self.overlay.model_copy(),
                automation=self.automation.model_copy()
            )
            self.profiles.profiles["default"] = default_profile

            # Gaming profile - focus on performance metrics
            gaming_profile = ProfileSettings(
                name="Gaming",
                description="Optimized for gaming performance monitoring",
                metrics=[
                    "cpu_usage",
                    "memory_usage",
                    "gpu_usage",
                    "system_temperatures",
                    "network_io"
                ],
                overlay=OverlaySettings(
                    visible=True,
                    always_on_top=True,
                    refresh_interval_ms=500,
                    opacity=0.8
                ),
                automation=AutomationSettings(
                    alerts=AlertSettings(
                        enabled=True,
                        show_overlay_banner=True,
                        thresholds=AlertThresholds(
                            cpu_percent=90.0,
                            memory_percent=95.0
                        )
                    )
                )
            )
            self.profiles.profiles["gaming"] = gaming_profile

            # Recording profile - focus on system resources during recording
            recording_profile = ProfileSettings(
                name="Recording",
                description="Optimized for video/audio recording sessions",
                metrics=[
                    "cpu_usage",
                    "memory_usage",
                    "disk_io",
                    "network_io",
                    "system_temperatures",
                    "top_cpu_processes",
                    "top_memory_processes"
                ],
                overlay=OverlaySettings(
                    visible=True,
                    always_on_top=True,
                    refresh_interval_ms=1000,
                    opacity=0.9
                ),
                automation=AutomationSettings(
                    logging=LoggingSettings(
                        enabled=True,
                        interval_ms=2000
                    ),
                    alerts=AlertSettings(
                        enabled=True,
                        show_overlay_banner=True,
                        thresholds=AlertThresholds(
                            cpu_percent=80.0,
                            memory_percent=85.0
                        )
                    )
                )
            )
            self.profiles.profiles["recording"] = recording_profile

            # Development profile - comprehensive monitoring for developers
            dev_profile = ProfileSettings(
                name="Development",
                description="Comprehensive monitoring for development work",
                metrics=[
                    "cpu_usage",
                    "memory_usage",
                    "swap_usage",
                    "disk_io",
                    "network_io",
                    "system_uptime",
                    "top_cpu_processes",
                    "top_memory_processes",
                    "system_temperatures"
                ],
                overlay=OverlaySettings(
                    visible=True,
                    always_on_top=False,
                    refresh_interval_ms=2000,
                    opacity=0.9
                ),
                automation=AutomationSettings(
                    logging=LoggingSettings(
                        enabled=True,
                        interval_ms=5000
                    ),
                    alerts=AlertSettings(
                        enabled=True,
                        show_overlay_banner=False,
                        thresholds=AlertThresholds(
                            cpu_percent=85.0,
                            memory_percent=90.0
                        )
                    )
                )
            )
            self.profiles.profiles["development"] = dev_profile

            # Minimal profile - only essential metrics
            minimal_profile = ProfileSettings(
                name="Minimal",
                description="Minimal set of essential metrics",
                metrics=[
                    "cpu_usage",
                    "memory_usage",
                    "system_uptime"
                ],
                overlay=OverlaySettings(
                    visible=True,
                    always_on_top=True,
                    refresh_interval_ms=2000,
                    opacity=0.7
                ),
                automation=AutomationSettings(
                    alerts=AlertSettings(
                        enabled=True,
                        show_overlay_banner=True,
                        thresholds=AlertThresholds(
                            cpu_percent=90.0,
                            memory_percent=95.0
                        )
                    )
                )
            )
            self.profiles.profiles["minimal"] = minimal_profile

    def apply_theme(self, theme_name: str) -> bool:
        if theme := self.themes.themes.get(theme_name):
            self.themes.current_theme = theme_name
            return True
        return False

    def apply_profile(self, profile_name: str) -> bool:
        if profile := self.profiles.profiles.get(profile_name):
            self.metrics = profile.metrics.copy()
            self.overlay = profile.overlay.model_copy()
            self.automation = profile.automation.model_copy()
            self.profiles.current_profile = profile_name
            return True
        return False

    _BACKUP_SUFFIX: str = ".bak"

    @classmethod
    def load(cls, path: Path | None = None) -> "MoniConfig":
        """Load configuration from disk with enhanced security validation."""
        target = path or DEFAULT_CONFIG_PATH
        if not target.is_file():
            logger.debug("Config file not found; loading defaults", extra={"target": str(target)})
            return cls()

        try:
            # Read and validate file size
            file_size = target.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                raise Exception("Config file too large")

            data = target.read_text(encoding="utf-8")

            # Parse JSON with security validation
            try:
                raw_config = json.loads(data)
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON in config file: {e}")

            # Basic validation
            if not isinstance(raw_config, dict):
                raise Exception("Config must be a JSON object")

            # Create config object with validated data
            return cls.model_validate(raw_config)

        except Exception as e:
            logger.warning(f"Failed to load config; falling back to defaults: {e}")
            backup_path = target.with_suffix(target.suffix + cls._BACKUP_SUFFIX)
            if backup_path.is_file():
                try:
                    backup_data = backup_path.read_text(encoding="utf-8")
                    raw_backup = json.loads(backup_data)
                    if isinstance(raw_backup, dict):
                        return cls.model_validate(raw_backup)
                except Exception:
                    pass
            logger.error("No valid config available; loading defaults")
            return cls()

    def save(self, path: Path | None = None) -> None:
        """Persist configuration atomically while preserving a backup copy."""
        target = path or DEFAULT_CONFIG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)

        # Validate configuration before saving
        validation_warnings = []

        sanitization_warnings = self._sanitize_before_save()
        validation_warnings.extend(sanitization_warnings)

        # Check bandwidth endpoints
        bandwidth_settings = self.automation.network.bandwidth_test
        if bandwidth_settings.enabled and not bandwidth_settings.download_endpoint:
            validation_warnings.append("Bandwidth testing enabled but no download endpoint configured")
            bandwidth_settings.enabled = False

        # Check network quality hosts
        quality_settings = self.automation.network.quality_test
        if quality_settings.enabled and not quality_settings.hosts:
            validation_warnings.append("Network quality testing enabled but no hosts configured")
            quality_settings.enabled = False

        # Log validation warnings
        for warning in validation_warnings:
            logger.warning(f"Configuration validation: {warning}")

        serialized = self.model_dump_json(indent=2)
        backup_path = target.with_suffix(target.suffix + self._BACKUP_SUFFIX)

        if target.exists():
            try:
                target.replace(backup_path)
                logger.debug("Config backup written")
            except OSError:
                pass

        target.write_text(serialized, encoding="utf-8")
        logger.debug("Configuration saved")


@dataclass
class ConfigSource:
    """設定ソース定義"""
    path: Path
    format: ConfigFormat
    environment: str
    priority: int = 50  # 優先度（高いほど優先）
    encrypted: bool = False
    watch_for_changes: bool = True
    last_modified: Optional[float] = None
    checksum: Optional[str] = None


@dataclass
class ConfigChange:
    """設定変更イベント"""
    timestamp: datetime
    source_path: Path
    field_path: str
    old_value: Any
    new_value: Any
    change_type: str  # 'added', 'modified', 'removed'


class ConfigFileWatcher(FileSystemEventHandler):
    """設定ファイル変更監視クラス"""

    def __init__(self, config_manager: 'UnifiedConfigManager'):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__ + '.ConfigFileWatcher')

    def on_modified(self, event):
        """ファイル変更イベントの処理"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # 監視対象の設定ファイルかチェック
        for source in self.config_manager.config_sources:
            if source.path == file_path and source.watch_for_changes:
                self.logger.info(f"設定ファイルが変更されました: {file_path}")
                self.config_manager._reload_config_source(source)
                break


class AES256GCMEncryption:
    """AES-256-GCM暗号化クラス"""

    KEY_SIZE = 32  # 256 bits
    NONCE_SIZE = 12  # 96 bits for GCM

    def __init__(self, key: Optional[bytes] = None):
        """AES-256-GCM暗号化の初期化"""
        if key:
            if len(key) != self.KEY_SIZE:
                raise ValueError(f"Key must be {self.KEY_SIZE} bytes, got {len(key)}")
            self._key = key
        else:
            self._key = self._generate_key()

    @classmethod
    def _generate_key(cls) -> bytes:
        """AES-256鍵を生成"""
        return os.urandom(cls.KEY_SIZE)

    def encrypt(self, plaintext: bytes) -> bytes:
        """AES-256-GCMでデータを暗号化"""
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = Cipher(
            algorithms.AES(self._key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        # nonce + tag + ciphertext を返す
        return nonce + encryptor.tag + ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        """AES-256-GCMでデータを復号化"""
        if len(ciphertext) < self.NONCE_SIZE + 16:  # nonce + tag minimum
            raise ValueError("Ciphertext too short")

        nonce = ciphertext[:self.NONCE_SIZE]
        tag = ciphertext[self.NONCE_SIZE:self.NONCE_SIZE + 16]
        encrypted_data = ciphertext[self.NONCE_SIZE + 16:]

        cipher = Cipher(
            algorithms.AES(self._key),
            modes.GCM(nonce, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(encrypted_data) + decryptor.finalize()

        return plaintext

    def derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """パスワードからAES-256鍵を導出"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))

    def get_key(self) -> bytes:
        """暗号化鍵を取得（デバッグ用）"""
        return self._key


class AdaptiveEncryption:
    """適応型暗号化システム"""

    def __init__(self, primary_key: Optional[bytes] = None):
        self.aes_gcm = AES256GCMEncryption(primary_key)
        self.fernet_fallback = Fernet(primary_key) if primary_key else Fernet.generate_key()

    def encrypt_sensitive_data(self, data: str, algorithm: str = "auto") -> str:
        """機密データを適応的に暗号化"""
        if algorithm == "auto":
            # データサイズに基づいてアルゴリズムを選択
            if len(data.encode('utf-8')) > 1024:  # 1KB以上
                algorithm = "aes256gcm"
            else:
                algorithm = "fernet"

        if algorithm == "aes256gcm":
            encrypted = self.aes_gcm.encrypt(data.encode('utf-8'))
            return f"AES256GCM:{base64.b64encode(encrypted).decode()}"
        else:  # fernet
            encrypted = self.fernet_fallback.encrypt(data.encode('utf-8'))
            return f"Fernet:{base64.b64encode(encrypted).decode()}"

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """暗号化データを復号化"""
        if not encrypted_data.startswith(("AES256GCM:", "Fernet:")):
            return encrypted_data  # 未暗号化

        try:
            prefix, encoded_data = encrypted_data.split(":", 1)
            raw_data = base64.b64decode(encoded_data)

            if prefix == "AES256GCM":
                decrypted = self.aes_gcm.decrypt(raw_data)
            elif prefix == "Fernet":
                decrypted = self.fernet_fallback.decrypt(raw_data)
            else:
                raise ValueError(f"Unknown encryption algorithm: {prefix}")

            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data  # 復号化失敗時は元のデータを返す

    def is_encrypted(self, data: str) -> bool:
        """データが暗号化されているかチェック"""
        return data.startswith(("AES256GCM:", "Fernet:"))

    def rotate_keys(self) -> None:
        """暗号化鍵をローテーション"""
        new_key = AES256GCMEncryption._generate_key()
        self.aes_gcm = AES256GCMEncryption(new_key)
        self.fernet_fallback = Fernet(Fernet.generate_key())


class UnifiedConfigManager:
    """統合設定マネージャー"""

    def __init__(self, app_name: str = "moni", security_policy: Optional[SecurityPolicy] = None):
        self.app_name = app_name
        self.config_data: Dict[str, Any] = {}
        self.config_sources: List[ConfigSource] = []
        self.change_callbacks: List[Callable[[ConfigChange], None]] = []
        self.config_history: List[ConfigChange] = []

        # セキュリティポリシーと検証
        self.security_policy = security_policy or SecurityPolicy()
        self.validator = ConfigValidator(self.security_policy)

        # セキュリティと暗号化
        self.encryption_handler = AdaptiveEncryption()
        self._audit_log: List[Dict[str, Any]] = []
        self._key_path = DEFAULT_CONFIG_DIR / ".encryption_key"

        # 高度なセキュリティ対策
        self.csrf_protection = CSRFProtection()
        self.command_protection = CommandInjectionProtection()

        # ファイル監視
        self.file_observer: Optional[Observer] = None
        self.watch_enabled = False

        # スレッド安全性
        self._config_lock = threading.RLock()

        # デフォルト設定パスのセットアップ
        self._setup_default_paths()

        # 機密フィールドの定義
        self._sensitive_fields = {
            'password', 'secret', 'key', 'token', 'api_key',
            'private_key', 'credential', 'auth', 'webhook_secret'
        }

    def _setup_default_paths(self) -> None:
        """デフォルト設定ファイルパスのセットアップ"""
        config_dir = Path.home() / ".config" / self.app_name

        # デフォルト設定ソース（優先度順）
        default_sources = [
            # 環境変数（最優先）
            ConfigSource(
                path=Path("env://"),
                format=ConfigFormat.ENV,
                environment="env",
                priority=100,
                encrypted=False,
                watch_for_changes=False
            ),
            # ユーザー設定
            ConfigSource(
                path=config_dir / "config.json",
                format=ConfigFormat.JSON,
                environment="user",
                priority=80,
                encrypted=True,
                watch_for_changes=True
            ),
            # システム設定
            ConfigSource(
                path=Path("/etc") / self.app_name / "config.json",
                format=ConfigFormat.JSON,
                environment="system",
                priority=60,
                encrypted=False,
                watch_for_changes=True
            ),
            # デフォルト設定
            ConfigSource(
                path=Path(__file__).parent / "default_config.json",
                format=ConfigFormat.JSON,
                environment="default",
                priority=40,
                encrypted=False,
                watch_for_changes=False
            )
        ]

        for source in default_sources:
            if source.path.name != "env://" and source.path.exists():
                self.add_config_source(source)

    def add_config_source(self, source: ConfigSource) -> None:
        """設定ソースを追加"""
        with self._config_lock:
            # 同じパスの既存ソースを削除
            self.config_sources = [s for s in self.config_sources if s.path != source.path]

            # 新しいソースを追加
            self.config_sources.append(source)

            # 優先度順にソート（高い順）
            self.config_sources.sort(key=lambda s: s.priority, reverse=True)

            logger.info(f"設定ソースを追加しました: {source.path} (優先度: {source.priority})")

    def add_change_callback(self, callback: Callable[[ConfigChange], None]) -> None:
        """設定変更コールバックを追加"""
        self.change_callbacks.append(callback)

    def start_file_watching(self) -> None:
        """設定ファイルの変更監視を開始"""
        if self.watch_enabled:
            return

        self.file_observer = Observer()

        # 監視対象ディレクトリを収集
        watched_dirs = set()
        for source in self.config_sources:
            if source.watch_for_changes and source.path.name != "env://":
                config_dir = source.path.parent
                if config_dir not in watched_dirs and config_dir.exists():
                    self.file_observer.schedule(
                        ConfigFileWatcher(self),
                        str(config_dir),
                        recursive=False
                    )
                    watched_dirs.add(config_dir)

        if watched_dirs:
            self.file_observer.start()
            self.watch_enabled = True
            logger.info(f"{len(watched_dirs)}個の設定ディレクトリの監視を開始しました")

    def stop_file_watching(self) -> None:
        """設定ファイルの変更監視を停止"""
        if self.file_observer:
            self.file_observer.stop()
            self.file_observer.join()
            self.watch_enabled = False
            logger.info("設定ファイルの監視を停止しました")

    def load_all_configs(self) -> None:
        """全設定ソースを読み込み"""
        with self._config_lock:
            # 既存設定をクリア
            self.config_data.clear()

            # 優先度逆順で読み込み（低いものから高いものへ）
            for source in reversed(self.config_sources):
                try:
                    config_data = self._load_config_source(source)
                    if config_data:
                        self._merge_config(config_data)
                        logger.debug(f"{source.path}から設定を読み込みました")
                except Exception as e:
                    logger.error(f"{source.path}からの設定読み込みに失敗しました: {e}")

            # 環境変数の読み込み
            self._load_environment_variables()

            # 機密値の復号化
            self._decrypt_sensitive_values()

            # 監査ログ記録
            self._log_audit_event("CONFIG_LOADED", {
                "sources_count": len(self.config_sources),
                "total_fields": len(self._flatten_config()),
                "encrypted_fields": self._count_encrypted_fields()
            })

            logger.info(f"{len(self.config_sources)}個の設定ソースから設定を読み込みました")

    def _load_config_source(self, source: ConfigSource) -> Optional[Dict[str, Any]]:
        """単一設定ソースからの読み込み"""
        if source.path.name == "env://":
            return self._load_environment_variables()

        if not source.path.exists():
            return None

        try:
            # ファイル変更チェック
            current_mtime = source.path.stat().st_mtime
            if source.last_modified and current_mtime == source.last_modified:
                return None

            # コンテンツ読み込み
            with open(source.path, 'r', encoding='utf-8') as f:
                content = f.read()

            # チェックサム計算
            current_checksum = hashlib.sha256(content.encode()).hexdigest()
            if source.checksum and current_checksum == source.checksum:
                return None

            # フォーマットに応じてパース
            if source.format == ConfigFormat.JSON:
                config_data = json.loads(content)
            elif source.format == ConfigFormat.YAML:
                config_data = yaml.safe_load(content)
            else:
                raise ValueError(f"未対応の設定フォーマットです: {source.format}")

            # セキュリティ検証
            if not self.validator.validate(config_data):
                errors = self.validator.get_errors()
                raise ValueError(f"設定セキュリティ検証に失敗しました: {errors}")

            # 署名検証（改ざん検知）
            if not self._verify_config_signature(config_data):
                raise ValueError("設定ファイルの署名が無効です（改ざん検知）")

            # メタデータ更新
            source.last_modified = current_mtime
            source.checksum = current_checksum

            return config_data

        except Exception as e:
            logger.error(f"{source.path}からの設定読み込みに失敗しました: {e}")
            return None

    def _load_environment_variables(self) -> Dict[str, Any]:
        """環境変数から設定を読み込み"""
        env_config = {}
        prefix = f"{self.app_name.upper()}_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                # FOO_BAR_BAZ -> foo.bar.baz
                config_path = config_key.replace('_', '.')
                self._set_nested_value(env_config, config_path, value)

        return env_config

    def _merge_config(self, new_config: Dict[str, Any]) -> None:
        """新しい設定を既存設定にマージ"""
        def merge_dict(target: Dict[str, Any], source: Dict[str, Any]) -> None:
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    merge_dict(target[key], value)
                else:
                    target[key] = value

        merge_dict(self.config_data, new_config)

    def _set_nested_value(self, config: Dict[str, Any], path: str, value: str) -> None:
        """ドット表記のパスでネストした値を設定"""
        keys = path.split('.')
        current = config

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # 値を適切な型に変換
        final_key = keys[-1]
        current[final_key] = self._convert_env_value(value)

    def _convert_env_value(self, value: str) -> Union[str, int, float, bool, None]:
        """環境変数文字列を適切な型に変換"""
        # ブール値変換
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False

        # None変換
        if value.lower() in ('null', 'none', ''):
            return None

        # 数値変換
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass

        # 文字列（デフォルト）
        return value

    def _decrypt_sensitive_values(self) -> None:
        """機密値を復号化"""
        def decrypt_recursive(data: Any) -> Any:
            if isinstance(data, dict):
                return {key: decrypt_recursive(value) for key, value in data.items()}
            elif isinstance(data, list):
                return [decrypt_recursive(item) for item in data]
            elif isinstance(data, str) and self.encryption_handler.is_encrypted(data):
                return self.encryption_handler.decrypt_value(data)
            else:
                return data

        self.config_data = decrypt_recursive(self.config_data)

    def get(self, path: str, default: Any = None) -> Any:
        """パスで設定値を取得"""
        with self._config_lock:
            keys = path.split('.')
            current = self.config_data

            try:
                for key in keys:
                    current = current[key]
                return current
            except (KeyError, TypeError):
                return default

    def set(self, path: str, value: Any, encrypt: bool = False) -> None:
        """パスで設定値を設定"""
        with self._config_lock:
            keys = path.split('.')
            current = self.config_data

            # 親ディレクトリまでナビゲート
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # 機密フィールドかチェックして暗号化
            if encrypt or (keys[-1].lower() in self._sensitive_fields and isinstance(value, str)):
                value = self.encryption_handler.encrypt_value(str(value))

            # 値を設定
            current[keys[-1]] = value

            # 監査ログ記録（機密フィールドの場合）
            if keys[-1].lower() in self._sensitive_fields:
                self._log_audit_event("SENSITIVE_CONFIG_SET", {
                    "field_path": path,
                    "encrypted": encrypt or (isinstance(value, str) and self.encryption_handler.is_encrypted(value))
                })

    def get_all(self) -> Dict[str, Any]:
        """全設定データを取得"""
        with self._config_lock:
            return self.config_data.copy()

    def save_to_file(self, file_path: Path, format: ConfigFormat = ConfigFormat.JSON,
                    encryption_level: EncryptionLevel = EncryptionLevel.SENSITIVE_ONLY) -> None:
        """設定をファイルに保存"""
        with self._config_lock:
            try:
                # セキュリティ検証
                if not self.validator.validate(self.config_data):
                    errors = self.validator.get_errors()
                    raise ValueError(f"設定セキュリティ検証に失敗しました: {errors}")

                # 署名を追加（改ざん検知のため）
                save_data = self._sign_config(self.config_data.copy())

                # 暗号化レベルの適用
                if encryption_level != EncryptionLevel.NONE:
                    save_data = self._encrypt_for_save(save_data, encryption_level)

                # ディレクトリの確保
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # 一時ファイルに書き込み
                temp_file = file_path.with_suffix(file_path.suffix + '.tmp')

                with open(temp_file, 'w', encoding='utf-8') as f:
                    if format == ConfigFormat.JSON:
                        json.dump(save_data, f, indent=2, ensure_ascii=False)
                    elif format == ConfigFormat.YAML:
                        yaml.dump(save_data, f, default_flow_style=False, allow_unicode=True)
                    else:
                        raise ValueError(f"未対応の保存フォーマットです: {format}")

                # アトミックに移動
                shutil.move(str(temp_file), str(file_path))

                # ファイル権限の設定
                try:
                    os.chmod(file_path, 0o600)
                except (OSError, NotImplementedError):
                    pass  # Windowsではchmodがサポートされない場合がある

                # 監査ログ記録
                self._log_audit_event("CONFIG_SAVED", {
                    "path": str(file_path),
                    "format": format.value,
                    "encryption_level": encryption_level.value,
                    "field_count": len(self._flatten_config())
                })

                logger.info(f"設定を{file_path}に保存しました")

            except Exception as e:
                logger.error(f"設定の保存に失敗しました: {file_path}: {e}")
                self._log_audit_event("CONFIG_SAVE_FAILED", {
                    "path": str(file_path),
                    "error": str(e)
                }, "ERROR")
                if temp_file.exists():
                    temp_file.unlink()
                raise

    def _encrypt_for_save(self, data: Dict[str, Any], level: EncryptionLevel) -> Dict[str, Any]:
        """保存時の暗号化処理"""
        def encrypt_recursive(obj: Any, path: str = "") -> Any:
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if level == EncryptionLevel.ALL:
                        if isinstance(value, str):
                            result[key] = self.encryption_handler.encrypt_value(value)
                        else:
                            result[key] = encrypt_recursive(value, current_path)
                    elif level == EncryptionLevel.SENSITIVE_ONLY:
                        if any(field in key.lower() for field in self._sensitive_fields):
                            if isinstance(value, str) and not self.encryption_handler.is_encrypted(value):
                                result[key] = self.encryption_handler.encrypt_value(value)
                            else:
                                result[key] = value
                        else:
                            result[key] = encrypt_recursive(value, current_path)
                    else:
                        result[key] = value
                return result
            elif isinstance(obj, list):
                return [encrypt_recursive(item, path) for item in obj]
            else:
                return obj

        return encrypt_recursive(data)

    def _reload_config_source(self, source: ConfigSource) -> None:
        """特定の設定ソースをリロード"""
        with self._config_lock:
            try:
                old_config = self.config_data.copy()
                config_data = self._load_config_source(source)

                if config_data:
                    # 全設定をリロードして適切な優先度を維持
                    self.load_all_configs()

                    # 変更を検出
                    changes = self._detect_changes(old_config, self.config_data)
                    for change in changes:
                        self.config_history.append(change)
                        for callback in self.change_callbacks:
                            try:
                                callback(change)
                            except Exception as e:
                                logger.error(f"変更コールバックでエラーが発生しました: {e}")

                    logger.info(f"{source.path}から設定をリロードしました ({len(changes)}個の変更を検出)")

            except Exception as e:
                logger.error(f"設定ソースのリロードに失敗しました: {source.path}: {e}")

    def _detect_changes(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> List[ConfigChange]:
        """古い設定と新しい設定の変更を検出"""
        changes = []

        def compare_values(path: str, old_val: Any, new_val: Any) -> None:
            if old_val != new_val:
                if old_val is None:
                    change_type = 'added'
                elif new_val is None:
                    change_type = 'removed'
                else:
                    change_type = 'modified'

                changes.append(ConfigChange(
                    timestamp=datetime.now(),
                    source_path=Path("unknown"),  # 複数のソースの場合
                    field_path=path,
                    old_value=old_val,
                    new_value=new_val,
                    change_type=change_type
                ))

        def compare_dicts(path: str, old_dict: Dict[str, Any], new_dict: Dict[str, Any]) -> None:
            all_keys = set(old_dict.keys()) | set(new_dict.keys())
            for key in all_keys:
                current_path = f"{path}.{key}" if path else key
                old_val = old_dict.get(key)
                new_val = new_dict.get(key)

                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    compare_dicts(current_path, old_val, new_val)
                else:
                    compare_values(current_path, old_val, new_val)

        compare_dicts("", old_config, new_config)
        return changes

    def export_config_schema(self) -> Dict[str, Any]:
        """設定スキーマをエクスポート"""
        # 機密フィールドを特定するための簡単なスキーマ生成
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }

        # 基本的なスキーマ構造を定義（実際の運用ではより詳細な定義が必要）
        schema["properties"] = {
            "monitoring": {
                "type": "object",
                "properties": {
                    "interval_ms": {"type": "integer", "minimum": 100, "maximum": 10000},
                    "enabled": {"type": "boolean"}
                }
            },
            "security": {
                "type": "object",
                "properties": {
                    "encryption_enabled": {"type": "boolean"}
                }
            }
        }

        return schema

    def get_config_status(self) -> Dict[str, Any]:
        """設定の包括的なステータスを取得"""
        with self._config_lock:
            return {
                "sources_count": len(self.config_sources),
                "config_fields_count": len(self._flatten_config()),
                "file_watching_enabled": self.watch_enabled,
                "last_reload": max(
                    (source.last_modified for source in self.config_sources if source.last_modified),
                    default=None
                ),
                "recent_changes": len([
                    change for change in self.config_history
                    if (datetime.now() - change.timestamp).seconds < 3600
                ]),
                "encrypted_fields": self._count_encrypted_fields(),
                "sources": [
                    {
                        "path": str(source.path),
                        "format": source.format.value,
                        "environment": source.environment,
                        "priority": source.priority,
                        "encrypted": source.encrypted,
                        "watching": source.watch_for_changes,
                        "last_modified": source.last_modified
                    }
                    for source in self.config_sources
                ]
            }

    def _flatten_config(self, data: Optional[Dict[str, Any]] = None, prefix: str = "") -> Dict[str, Any]:
        """設定ディクショナリをフラット化"""
        if data is None:
            data = self.config_data

        flattened = {}
        for key, value in data.items():
            current_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flattened.update(self._flatten_config(value, current_key))
            else:
                flattened[current_key] = value

        return flattened

    def _sign_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """HMAC署名を追加して設定データの完全性を保証"""
        config_copy = {k: v for k, v in config.items() if k != '_signature'}
        config_str = json.dumps(config_copy, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self._encryption_key,
            config_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        config_copy['_signature'] = signature
        return config_copy

    def _verify_config_signature(self, config: Dict[str, Any]) -> bool:
        """設定データのHMAC署名を検証"""
        if '_signature' not in config:
            return False

        provided_signature = config['_signature']
        config_copy = {k: v for k, v in config.items() if k != '_signature'}
        config_str = json.dumps(config_copy, sort_keys=True, separators=(',', ':'))

        expected_signature = hmac.new(
            self._encryption_key,
            config_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(provided_signature, expected_signature)

    def detect_config_tampering(self, config_path: Path) -> Dict[str, Any]:
        """設定ファイルの改ざん検知"""
        result = {
            "tampered": False,
            "reason": None,
            "details": {}
        }

        try:
            if not config_path.exists():
                result["tampered"] = True
                result["reason"] = "Config file does not exist"
                return result

            # ファイルサイズチェック
            file_size = config_path.stat().st_size
            if file_size > self.security_policy.max_config_size_mb * 1024 * 1024:
                result["tampered"] = True
                result["reason"] = f"Config file too large: {file_size} bytes"
                return result

            # コンテンツ読み込みとパース
            content = config_path.read_text(encoding='utf-8')
            config_data = json.loads(content)

            # 署名検証
            if not self._verify_config_signature(config_data):
                result["tampered"] = True
                result["reason"] = "Invalid HMAC signature"
                result["details"]["signature_mismatch"] = True
                return result

            # セキュリティ検証
            if not self.validator.validate(config_data):
                result["tampered"] = True
                result["reason"] = "Security validation failed"
                result["details"]["validation_errors"] = self.validator.get_errors()
                return result

            result["details"]["file_size"] = file_size
            result["details"]["field_count"] = len(self._flatten_config(config_data))

        except (json.JSONDecodeError, OSError) as e:
            result["tampered"] = True
            result["reason"] = f"File read/parse error: {str(e)}"

        return result

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """監査ログを取得"""
        return self._audit_log[-limit:] if limit > 0 else self._audit_log.copy()

    def rotate_encryption_key(self) -> None:
        """暗号化キーをローテーション"""
        try:
            # 既存の設定を保存
            existing_config = self.config_data.copy()

            # 新しい暗号化ハンドラを生成
            self.encryption_handler.rotate_keys()

            # 既存の設定を新しいキーで再保存
            if existing_config:
                self.save_to_file(DEFAULT_CONFIG_PATH)

            self._log_audit_event(
                "ENCRYPTION_KEY_ROTATED",
                {
                    "key_path": str(self._key_path),
                    "config_path": str(DEFAULT_CONFIG_PATH),
                    "algorithm": "AES256GCM+Fernet"
                }
            )

            logger.info("暗号化キーのローテーションが完了しました")

        except Exception as e:
            logger.error(f"暗号化キーのローテーションに失敗しました: {e}")
            self._log_audit_event(
                "KEY_ROTATION_FAILED",
                {"error": str(e)},
                "ERROR"
            )
            raise


class CSRFProtection:
    """CSRF対策システム"""

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.tokens: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.token_expiry = 3600  # 1時間

    def generate_token(self, session_id: str) -> str:
        """CSRFトークンを生成"""
        with self._lock:
            token = secrets.token_urlsafe(32)
            expiry = datetime.now() + timedelta(seconds=self.token_expiry)

            self.tokens[token] = {
                'session_id': session_id,
                'expiry': expiry,
                'used': False
            }

            # 期限切れトークンのクリーンアップ
            self._cleanup_expired_tokens()

            return token

    def validate_token(self, token: str, session_id: str) -> bool:
        """CSRFトークンを検証"""
        with self._lock:
            if token not in self.tokens:
                security_monitor.log_security_event(
                    "CSRF_TOKEN_INVALID", "無効なCSRFトークンが使用されました",
                    "medium", "csrf_protection", {"token": token[:16]}
                )
                return False

            token_data = self.tokens[token]

            # セッションIDチェック
            if token_data['session_id'] != session_id:
                security_monitor.log_security_event(
                    "CSRF_SESSION_MISMATCH", "CSRFトークンのセッションIDが一致しません",
                    "high", "csrf_protection", {"token": token[:16]}
                )
                return False

            # 有効期限チェック
            if datetime.now() > token_data['expiry']:
                security_monitor.log_security_event(
                    "CSRF_TOKEN_EXPIRED", "期限切れのCSRFトークンが使用されました",
                    "medium", "csrf_protection", {"token": token[:16]}
                )
                del self.tokens[token]
                return False

            # 使用済みチェック
            if token_data['used']:
                security_monitor.log_security_event(
                    "CSRF_TOKEN_REUSED", "再利用されたCSRFトークンが検出されました",
                    "high", "csrf_protection", {"token": token[:16]}
                )
                return False

            # トークンを使用済みにマーク
            token_data['used'] = True
            return True

    def invalidate_token(self, token: str) -> None:
        """CSRFトークンを無効化"""
        with self._lock:
            if token in self.tokens:
                del self.tokens[token]

    def _cleanup_expired_tokens(self) -> None:
        """期限切れトークンをクリーンアップ"""
        now = datetime.now()
        expired_tokens = [
            token for token, data in self.tokens.items()
            if now > data['expiry']
        ]

        for token in expired_tokens:
            del self.tokens[token]

    def get_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """トークン情報を取得（デバッグ用）"""
        with self._lock:
            if token in self.tokens:
                return {
                    'session_id': self.tokens[token]['session_id'],
                    'expiry': self.tokens[token]['expiry'].isoformat(),
                    'used': self.tokens[token]['used']
                }
            return None


class CommandInjectionProtection:
    """コマンドインジェクション対策"""

    DANGEROUS_PATTERNS = [
        re.compile(r'[;&|`$()<>]'),  # シェルメタ文字
        re.compile(r'\$\{.*\}'),     # 変数展開
        re.compile(r'`.*`'),         # コマンド置換
        re.compile(r'\$\(.*\)'),     # コマンド置換（代替）
        re.compile(r'\\x[0-9a-fA-F]{2}'),  # 16進エスケープ
        re.compile(r'\\u[0-9a-fA-F]{4}'),  # Unicodeエスケープ
    ]

    SAFE_COMMANDS = {
        'echo', 'cat', 'grep', 'find', 'ls', 'pwd', 'date', 'uptime',
        'ps', 'top', 'htop', 'df', 'du', 'free', 'vmstat', 'iostat',
        'netstat', 'ss', 'ping', 'traceroute', 'nslookup', 'dig'
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.CommandInjectionProtection')

    def validate_command(self, command: str) -> bool:
        """コマンドの安全性を検証"""
        if not command or not isinstance(command, str):
            return False

        command = command.strip()

        # 危険パターンチェック
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.search(command):
                security_monitor.log_security_event(
                    "COMMAND_INJECTION_DETECTED", "危険なコマンドパターンが検出されました",
                    "critical", "command_validation", {"command": command[:100]}
                )
                return False

        # コマンド名の抽出と検証
        command_parts = shlex.split(command, posix=False)
        if not command_parts:
            return False

        base_command = command_parts[0].lower()

        # 危険コマンドチェック
        dangerous_commands = {
            'rm', 'del', 'format', 'fdisk', 'mkfs', 'dd', 'shred',
            'sudo', 'su', 'passwd', 'usermod', 'userdel', 'chmod', 'chown',
            'mount', 'umount', 'systemctl', 'service', 'kill', 'killall',
            'pkill', 'xkill', 'shutdown', 'reboot', 'halt', 'poweroff'
        }

        if base_command in dangerous_commands:
            security_monitor.log_security_event(
                "DANGEROUS_COMMAND_DETECTED", f"危険なコマンドが使用されました: {base_command}",
                "critical", "command_validation", {"command": command[:100]}
            )
            return False

        # 安全コマンドの場合は許可
        if base_command in self.SAFE_COMMANDS:
            return True

        # その他のコマンドは警告をログに記録
        self.logger.warning(f"未知のコマンドが使用されました: {base_command}")
        security_monitor.log_security_event(
            "UNKNOWN_COMMAND_USED", f"未知のコマンドが使用されました: {base_command}",
            "low", "command_validation", {"command": command[:100]}
        )

        return True

    def sanitize_command_args(self, args: List[str]) -> List[str]:
        """コマンド引数をサニタイズ"""
        sanitized = []

        for arg in args:
            # 危険文字をエスケープ
            safe_arg = re.sub(r'([;&|`$()<>])', r'\\\1', arg)
            sanitized.append(safe_arg)

            # 引数に危険パターンが含まれる場合は警告
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern.search(arg):
                    security_monitor.log_security_event(
                        "DANGEROUS_ARG_DETECTED", "コマンド引数に危険なパターンが検出されました",
                        "high", "command_validation", {"arg": arg[:50]}
                    )

        return sanitized


# グローバル設定マネージャーインスタンス
unified_config_manager = UnifiedConfigManager()

# グローバルセキュリティインスタンス
csrf_protection = CSRFProtection()
command_protection = CommandInjectionProtection()
