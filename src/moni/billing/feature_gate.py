"""
Feature gate enforcement for billing tiers.

Controls access to features based on subscription tier and usage quotas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from .storage import get_by_customer
from .tier_config import BillingConfiguration, FeatureConfig, TierConfig, get_billing_config

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QuotaStatus:
    """Status of a feature quota check."""

    allowed: bool
    remaining: int  # -1 for unlimited
    limit: int | None
    current_usage: int
    warning_threshold: int | None = None
    over_soft_limit: bool = False
    feature_enabled: bool = True

    @property
    def is_unlimited(self) -> bool:
        """Check if quota is unlimited."""
        return self.remaining == -1

    @property
    def percentage_used(self) -> float:
        """Get percentage of quota used (0-100)."""
        if self.is_unlimited or self.limit is None or self.limit == 0:
            return 0.0
        return (self.current_usage / self.limit) * 100


class FeatureGate:
    """
    Feature gate for controlling access to tier-based features.

    Usage:
        gate = FeatureGate(customer_id="cus_abc123")
        if gate.can_add_endpoint():
            add_endpoint()
        else:
            raise QuotaExceededError()
    """

    def __init__(self, customer_id: str, config: BillingConfiguration | None = None) -> None:
        """
        Initialize feature gate.

        Args:
            customer_id: Stripe customer ID
            config: Billing configuration (uses global if None)
        """
        self.customer_id = customer_id
        self.config = config or get_billing_config()
        self._subscription = get_by_customer(customer_id)
        self._tier: TierConfig | None = None
        self._usage_cache: Dict[str, int] = {}

        if self._subscription and self._subscription.tier_name:
            self._tier = self.config.get_tier(self._subscription.tier_name)

    @property
    def tier_name(self) -> str | None:
        """Get current tier name."""
        return self._tier.name if self._tier else None

    @property
    def has_active_subscription(self) -> bool:
        """Check if customer has active subscription."""
        return self._subscription is not None and self._subscription.is_active

    def has_feature(self, feature_id: str) -> bool:
        """
        Check if customer has access to a feature.

        Args:
            feature_id: Feature identifier (e.g., 'rbac', 'compliance_exports')

        Returns:
            True if feature is enabled for this tier
        """
        if not self.has_active_subscription or not self._tier:
            return False

        return self._tier.has_feature(feature_id)

    def get_feature_config(self, feature_id: str) -> FeatureConfig | None:
        """Get feature configuration for current tier."""
        if not self._tier:
            return None
        return self._tier.get_feature(feature_id)

    def check_quota(
        self, feature_id: str, current_usage: int, increment: int = 1
    ) -> QuotaStatus:
        """
        Check if usage is within quota for a feature.

        Args:
            feature_id: Feature identifier
            current_usage: Current usage count
            increment: Planned increment (default: 1)

        Returns:
            QuotaStatus with quota check results
        """
        if not self.has_active_subscription or not self._tier:
            return QuotaStatus(
                allowed=False,
                remaining=0,
                limit=0,
                current_usage=current_usage,
                feature_enabled=False,
            )

        feature = self._tier.get_feature(feature_id)
        if not feature:
            return QuotaStatus(
                allowed=False,
                remaining=0,
                limit=0,
                current_usage=current_usage,
                feature_enabled=False,
            )

        if not feature.enabled:
            return QuotaStatus(
                allowed=False,
                remaining=0,
                limit=0,
                current_usage=current_usage,
                feature_enabled=False,
            )

        # Unlimited features
        if feature.limit is None:
            return QuotaStatus(
                allowed=True,
                remaining=-1,
                limit=None,
                current_usage=current_usage,
                feature_enabled=True,
            )

        # Calculate quota
        limit = feature.limit
        future_usage = current_usage + increment
        remaining = max(0, limit - future_usage)
        allowed = future_usage <= limit

        # Check soft limit
        soft_threshold = int(limit * self.config.soft_limit_threshold)
        over_soft_limit = current_usage >= soft_threshold

        return QuotaStatus(
            allowed=allowed,
            remaining=remaining,
            limit=limit,
            current_usage=current_usage,
            warning_threshold=soft_threshold,
            over_soft_limit=over_soft_limit,
            feature_enabled=True,
        )

    def can_add_endpoint(self, current_count: int) -> bool:
        """Check if customer can add another endpoint."""
        status = self.check_quota("endpoints", current_count, increment=1)
        return status.allowed

    def can_send_alert(self, current_count: int) -> bool:
        """Check if customer can send another alert."""
        status = self.check_quota("alerts_per_month", current_count, increment=1)
        return status.allowed

    def can_make_api_call(self, current_count: int) -> bool:
        """Check if customer can make another API call."""
        status = self.check_quota("api_calls", current_count, increment=1)
        return status.allowed

    def get_endpoint_quota(self, current_count: int) -> QuotaStatus:
        """Get endpoint quota status."""
        return self.check_quota("endpoints", current_count)

    def get_alert_quota(self, current_count: int) -> QuotaStatus:
        """Get alert quota status."""
        return self.check_quota("alerts_per_month", current_count)

    def get_api_quota(self, current_count: int) -> QuotaStatus:
        """Get API call quota status."""
        return self.check_quota("api_calls", current_count)

    def get_retention_days(self) -> int:
        """Get allowed retention days for current tier."""
        if not self._tier:
            return 7  # Default to minimal

        feature = self._tier.get_feature("retention_days")
        if not feature or not feature.enabled:
            return 7

        return feature.limit if feature.limit else 90  # Default to 90 if unlimited

    def enforce_quota(self, feature_id: str, current_usage: int) -> None:
        """
        Enforce quota limits.

        Args:
            feature_id: Feature identifier
            current_usage: Current usage count

        Raises:
            QuotaExceededError: If quota exceeded and hard limit enforced
        """
        if not self.config.quota_enforcement_enabled:
            return

        status = self.check_quota(feature_id, current_usage)

        if not status.allowed:
            if self.config.hard_limit_behavior == "block":
                raise QuotaExceededError(
                    f"Quota exceeded for {feature_id}. "
                    f"Current: {current_usage}, Limit: {status.limit}"
                )
            else:
                logger.warning(
                    "Quota soft limit exceeded",
                    extra={
                        "customer_id": self.customer_id,
                        "feature_id": feature_id,
                        "current_usage": current_usage,
                        "limit": status.limit,
                    },
                )

        if status.over_soft_limit and not status.allowed:
            logger.info(
                "Approaching quota limit",
                extra={
                    "customer_id": self.customer_id,
                    "feature_id": feature_id,
                    "current_usage": current_usage,
                    "limit": status.limit,
                    "percentage": status.percentage_used,
                },
            )


class QuotaExceededError(Exception):
    """Raised when a quota limit is exceeded."""

    pass


class FeatureNotAvailableError(Exception):
    """Raised when a feature is not available for the current tier."""

    pass


def require_feature(feature_id: str) -> callable:
    """
    Decorator to require a feature for a function.

    Usage:
        @require_feature('rbac')
        def create_role(customer_id: str, role_name: str):
            ...
    """

    def decorator(func: callable) -> callable:
        def wrapper(customer_id: str, *args, **kwargs):
            gate = FeatureGate(customer_id)
            if not gate.has_feature(feature_id):
                raise FeatureNotAvailableError(
                    f"Feature '{feature_id}' not available for tier '{gate.tier_name}'"
                )
            return func(customer_id, *args, **kwargs)

        return wrapper

    return decorator


def require_quota(feature_id: str, usage_key: str = "current_usage") -> callable:
    """
    Decorator to check quota before function execution.

    Usage:
        @require_quota('endpoints', usage_key='endpoint_count')
        def add_endpoint(customer_id: str, endpoint_count: int):
            ...
    """

    def decorator(func: callable) -> callable:
        def wrapper(customer_id: str, *args, **kwargs):
            gate = FeatureGate(customer_id)
            current_usage = kwargs.get(usage_key, 0)
            gate.enforce_quota(feature_id, current_usage)
            return func(customer_id, *args, **kwargs)

        return wrapper

    return decorator
