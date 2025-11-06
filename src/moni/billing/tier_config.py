"""
Tier configuration loader and feature gate enforcement.

Loads billing tier configuration from YAML and provides feature access control.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass(slots=True)
class FeatureConfig:
    """Configuration for a single feature within a tier."""

    enabled: bool = True
    limit: int | None = None
    metered: bool = False
    metered_price_id: str | None = None
    unit_price: float | None = None
    unit_size: int = 1
    included_quantity: int = 0
    overage_price: float | None = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FeatureConfig:
        """Create FeatureConfig from dictionary."""
        if isinstance(data, bool):
            return cls(enabled=data)

        return cls(
            enabled=data.get("enabled", True),
            limit=data.get("limit"),
            metered=data.get("metered", False),
            metered_price_id=data.get("metered_price_id"),
            unit_price=data.get("unit_price"),
            unit_size=data.get("unit_size", 1),
            included_quantity=data.get("included_quantity", 0),
            overage_price=data.get("overage_price"),
            description=data.get("description", ""),
            metadata={k: v for k, v in data.items() if k not in cls.__dataclass_fields__},
        )

    def has_limit(self) -> bool:
        """Check if feature has a usage limit."""
        return self.limit is not None

    def is_unlimited(self) -> bool:
        """Check if feature has unlimited usage."""
        return self.limit is None and self.enabled

    def check_quota(self, current_usage: int) -> tuple[bool, int]:
        """
        Check if usage is within quota.

        Returns:
            (allowed, remaining) tuple
        """
        if not self.enabled:
            return (False, 0)

        if self.limit is None:
            return (True, -1)  # -1 indicates unlimited

        remaining = self.limit - current_usage
        return (remaining > 0, max(0, remaining))


@dataclass(slots=True)
class TierConfig:
    """Configuration for a billing tier."""

    name: str
    display_name: str
    stripe_price_id: str
    description: str
    billing_interval: str
    base_price: float
    trial_period_days: int = 0
    features: Dict[str, FeatureConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> TierConfig:
        """Create TierConfig from dictionary."""
        features = {}
        for feature_id, feature_data in data.get("features", {}).items():
            features[feature_id] = FeatureConfig.from_dict(feature_data)

        return cls(
            name=name,
            display_name=data.get("display_name", name.title()),
            stripe_price_id=data["stripe_price_id"],
            description=data.get("description", ""),
            billing_interval=data.get("billing_interval", "month"),
            base_price=data.get("base_price", 0.0),
            trial_period_days=data.get("trial_period_days", 0),
            features=features,
        )

    def has_feature(self, feature_id: str) -> bool:
        """Check if tier has a feature enabled."""
        feature = self.features.get(feature_id)
        return feature is not None and feature.enabled

    def get_feature(self, feature_id: str) -> FeatureConfig | None:
        """Get feature configuration."""
        return self.features.get(feature_id)

    def get_feature_limit(self, feature_id: str) -> int | None:
        """Get feature usage limit."""
        feature = self.get_feature(feature_id)
        return feature.limit if feature else None


@dataclass(slots=True)
class AddonConfig:
    """Configuration for a billing add-on."""

    addon_id: str
    stripe_price_id: str
    name: str
    description: str
    unit_price: float
    unit_size: int = 1
    billing_interval: str = "month"
    metered: bool = False
    available_for: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, addon_id: str, data: Dict[str, Any]) -> AddonConfig:
        """Create AddonConfig from dictionary."""
        return cls(
            addon_id=addon_id,
            stripe_price_id=data["stripe_price_id"],
            name=data.get("name", addon_id.replace("_", " ").title()),
            description=data.get("description", ""),
            unit_price=data.get("unit_price", 0.0),
            unit_size=data.get("unit_size", 1),
            billing_interval=data.get("billing_interval", "month"),
            metered=data.get("metered", False),
            available_for=data.get("available_for", []),
        )

    def is_available_for_tier(self, tier_name: str) -> bool:
        """Check if add-on is available for a tier."""
        if not self.available_for:
            return True
        return tier_name.lower() in [t.lower() for t in self.available_for]


@dataclass(slots=True)
class BillingConfiguration:
    """Complete billing configuration."""

    currency: str
    tiers: Dict[str, TierConfig]
    addons: Dict[str, AddonConfig]
    tax_enabled: bool = False
    quota_enforcement_enabled: bool = True
    soft_limit_threshold: float = 0.9
    hard_limit_behavior: str = "block"
    grace_period_days: int = 7
    proration_enabled: bool = True

    def get_tier(self, tier_name: str) -> TierConfig | None:
        """Get tier configuration by name."""
        return self.tiers.get(tier_name.lower())

    def get_tier_by_price_id(self, price_id: str) -> TierConfig | None:
        """Get tier configuration by Stripe price ID."""
        for tier in self.tiers.values():
            if tier.stripe_price_id == price_id:
                return tier
        return None

    def get_addon(self, addon_id: str) -> AddonConfig | None:
        """Get add-on configuration."""
        return self.addons.get(addon_id.lower())

    def list_tiers(self) -> List[TierConfig]:
        """List all tiers."""
        return list(self.tiers.values())

    def list_addons_for_tier(self, tier_name: str) -> List[AddonConfig]:
        """List available add-ons for a tier."""
        return [addon for addon in self.addons.values() if addon.is_available_for_tier(tier_name)]


def load_billing_config(config_path: str | Path | None = None) -> BillingConfiguration:
    """
    Load billing configuration from YAML file.

    Args:
        config_path: Path to YAML config file. If None, uses default location.

    Returns:
        BillingConfiguration instance

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If config is invalid
    """
    if config_path is None:
        # Default to configs/billing_tiers.yaml
        config_path = Path(__file__).parent.parent.parent.parent / "configs" / "billing_tiers.yaml"

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Billing config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Parse tiers
    tiers = {}
    for tier_id, tier_data in data.get("tiers", {}).items():
        tiers[tier_id.lower()] = TierConfig.from_dict(tier_id, tier_data)

    # Parse add-ons
    addons = {}
    for addon_id, addon_data in data.get("addons", {}).items():
        addons[addon_id.lower()] = AddonConfig.from_dict(addon_id, addon_data)

    # Parse global settings
    payment_recovery = data.get("payment_recovery", {})
    proration = data.get("proration", {})
    quota = data.get("quota_enforcement", {})

    return BillingConfiguration(
        currency=data.get("currency", "usd"),
        tiers=tiers,
        addons=addons,
        tax_enabled=data.get("tax", {}).get("enabled", False),
        quota_enforcement_enabled=quota.get("enabled", True),
        soft_limit_threshold=quota.get("soft_limit_threshold", 0.9),
        hard_limit_behavior=quota.get("hard_limit_behavior", "block"),
        grace_period_days=payment_recovery.get("grace_period_days", 7),
        proration_enabled=proration.get("enabled", True),
    )


# Global config instance (lazy loaded)
_config: BillingConfiguration | None = None


def get_billing_config(reload: bool = False) -> BillingConfiguration:
    """
    Get global billing configuration instance.

    Args:
        reload: Force reload from file

    Returns:
        BillingConfiguration instance
    """
    global _config
    if _config is None or reload:
        _config = load_billing_config()
    return _config
