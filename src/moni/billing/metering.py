"""
Usage-based metering system for Stripe billing.

Tracks customer usage metrics and reports to Stripe for metered billing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import stripe

from .storage import get_by_customer
from .tier_config import get_billing_config

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UsageEvent:
    """
    A single usage event for metering.

    Attributes:
        customer_id: Stripe customer ID
        metric_name: Name of the metric being tracked
        quantity: Usage quantity
        timestamp: When the usage occurred
        metadata: Additional event metadata
    """

    customer_id: str
    metric_name: str
    quantity: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "customer_id": self.customer_id,
            "metric_name": self.metric_name,
            "quantity": self.quantity,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class UsageRecord:
    """
    Aggregated usage record for Stripe reporting.

    Attributes:
        subscription_item_id: Stripe subscription item ID
        quantity: Aggregated usage quantity
        timestamp: When the usage is reported
        action: How to aggregate ('set', 'increment')
    """

    subscription_item_id: str
    quantity: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    action: str = "increment"  # 'set' or 'increment'


class UsageMeter:
    """
    Tracks and reports usage metrics for billing.

    Usage:
        meter = UsageMeter()
        meter.record_endpoint_usage("cus_abc123", endpoint_count=5)
        meter.record_api_call("cus_abc123")
        meter.flush_to_stripe()  # Report all pending usage
    """

    def __init__(self) -> None:
        """Initialize usage meter."""
        self._config = get_billing_config()
        self._pending_events: List[UsageEvent] = []

    def record_event(
        self,
        customer_id: str,
        metric_name: str,
        quantity: int = 1,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        """
        Record a usage event.

        Args:
            customer_id: Stripe customer ID
            metric_name: Metric identifier (e.g., 'endpoints', 'api_calls')
            quantity: Usage quantity
            metadata: Additional event metadata
        """
        event = UsageEvent(
            customer_id=customer_id,
            metric_name=metric_name,
            quantity=quantity,
            metadata=metadata or {},
        )
        self._pending_events.append(event)

        logger.debug(
            "Recorded usage event",
            extra={
                "customer_id": customer_id,
                "metric": metric_name,
                "quantity": quantity,
            },
        )

    def record_endpoint_usage(self, customer_id: str, endpoint_count: int) -> None:
        """Record endpoint usage."""
        self.record_event(customer_id, "endpoints", quantity=endpoint_count)

    def record_api_call(self, customer_id: str, call_count: int = 1) -> None:
        """Record API call usage."""
        self.record_event(customer_id, "api_calls", quantity=call_count)

    def record_alert(self, customer_id: str, alert_count: int = 1) -> None:
        """Record alert usage."""
        self.record_event(customer_id, "alerts_per_month", quantity=alert_count)

    def record_security_scan(self, customer_id: str, scan_count: int = 1) -> None:
        """Record security scan usage."""
        self.record_event(customer_id, "security_scans", quantity=scan_count)

    def record_retention_extension(
        self, customer_id: str, additional_days: int
    ) -> None:
        """Record extended retention usage."""
        # Convert days to units (90-day blocks)
        units = (additional_days + 89) // 90  # Round up
        self.record_event(customer_id, "extended_retention", quantity=units)

    def get_pending_events(self) -> List[UsageEvent]:
        """Get all pending usage events."""
        return list(self._pending_events)

    def clear_pending_events(self) -> None:
        """Clear all pending events."""
        self._pending_events.clear()

    def flush_to_stripe(self, idempotency_key_prefix: str | None = None) -> Dict[str, int]:
        """
        Report all pending usage to Stripe.

        Args:
            idempotency_key_prefix: Prefix for idempotency keys

        Returns:
            Dictionary with success/failure counts
        """
        if not self._pending_events:
            logger.debug("No pending usage events to report")
            return {"success": 0, "failed": 0}

        # Group events by customer and metric
        aggregated = self._aggregate_events(self._pending_events)

        success_count = 0
        failed_count = 0

        for key, events in aggregated.items():
            customer_id, metric_name = key
            total_quantity = sum(e.quantity for e in events)

            try:
                self._report_usage_to_stripe(
                    customer_id=customer_id,
                    metric_name=metric_name,
                    quantity=total_quantity,
                    idempotency_key_prefix=idempotency_key_prefix,
                )
                success_count += 1
                logger.info(
                    "Reported usage to Stripe",
                    extra={
                        "customer_id": customer_id,
                        "metric": metric_name,
                        "quantity": total_quantity,
                    },
                )
            except Exception as exc:
                failed_count += 1
                logger.error(
                    "Failed to report usage to Stripe",
                    exc_info=True,
                    extra={
                        "customer_id": customer_id,
                        "metric": metric_name,
                        "error": str(exc),
                    },
                )

        # Clear successfully reported events
        if success_count > 0:
            self.clear_pending_events()

        return {"success": success_count, "failed": failed_count}

    def _aggregate_events(
        self, events: List[UsageEvent]
    ) -> Dict[tuple[str, str], List[UsageEvent]]:
        """
        Aggregate events by customer and metric.

        Returns:
            Dictionary keyed by (customer_id, metric_name)
        """
        aggregated: Dict[tuple[str, str], List[UsageEvent]] = {}

        for event in events:
            key = (event.customer_id, event.metric_name)
            if key not in aggregated:
                aggregated[key] = []
            aggregated[key].append(event)

        return aggregated

    def _report_usage_to_stripe(
        self,
        customer_id: str,
        metric_name: str,
        quantity: int,
        idempotency_key_prefix: str | None = None,
    ) -> None:
        """
        Report usage to Stripe for a specific metric.

        Args:
            customer_id: Stripe customer ID
            metric_name: Metric identifier
            quantity: Usage quantity
            idempotency_key_prefix: Prefix for idempotency key
        """
        # Get customer subscription
        subscription_record = get_by_customer(customer_id)
        if not subscription_record:
            logger.warning(
                "No subscription found for customer",
                extra={"customer_id": customer_id},
            )
            return

        # Get tier configuration
        tier = self._config.get_tier(subscription_record.tier_name or "")
        if not tier:
            logger.warning(
                "No tier configuration found",
                extra={"tier_name": subscription_record.tier_name},
            )
            return

        # Get feature configuration
        feature = tier.get_feature(metric_name)
        if not feature or not feature.metered:
            logger.debug(
                "Feature is not metered",
                extra={"metric": metric_name, "tier": tier.name},
            )
            return

        # Get metered price ID
        if not feature.metered_price_id:
            logger.warning(
                "No metered price ID configured",
                extra={"metric": metric_name, "tier": tier.name},
            )
            return

        # Find subscription item for this price
        try:
            subscription = stripe.Subscription.retrieve(
                subscription_record.subscription_id,
                expand=["items"],
            )
        except stripe.error.StripeError as exc:
            logger.error("Failed to retrieve subscription", exc_info=True)
            raise

        subscription_item_id = None
        for item in subscription.get("items", {}).get("data", []):
            if item.get("price", {}).get("id") == feature.metered_price_id:
                subscription_item_id = item["id"]
                break

        if not subscription_item_id:
            logger.warning(
                "No subscription item found for metered price",
                extra={
                    "price_id": feature.metered_price_id,
                    "metric": metric_name,
                },
            )
            return

        # Calculate usage (subtract included quantity if applicable)
        billable_quantity = max(0, quantity - feature.included_quantity)
        if billable_quantity == 0:
            logger.debug(
                "Usage within included quantity",
                extra={"quantity": quantity, "included": feature.included_quantity},
            )
            return

        # Create idempotency key
        timestamp = int(datetime.now(tz=timezone.utc).timestamp())
        idempotency_key = (
            f"{idempotency_key_prefix or 'usage'}_{customer_id}_{metric_name}_{timestamp}"
        )

        # Report usage to Stripe
        stripe.SubscriptionItem.create_usage_record(
            subscription_item_id,
            quantity=billable_quantity,
            timestamp=timestamp,
            action="set",  # Use 'set' to replace, 'increment' to add
            idempotency_key=idempotency_key,
        )


class UsageTracker:
    """
    Tracks current usage for quota enforcement.

    Separate from UsageMeter which handles Stripe reporting.
    This class tracks current period usage for local quota checks.
    """

    def __init__(self, customer_id: str) -> None:
        """
        Initialize usage tracker.

        Args:
            customer_id: Stripe customer ID
        """
        self.customer_id = customer_id
        self._usage_cache: Dict[str, int] = {}

    def get_usage(self, metric_name: str) -> int:
        """
        Get current usage for a metric.

        Args:
            metric_name: Metric identifier

        Returns:
            Current usage count
        """
        # In production, this would query a database or cache
        # For now, return cached value or 0
        return self._usage_cache.get(metric_name, 0)

    def increment_usage(self, metric_name: str, quantity: int = 1) -> int:
        """
        Increment usage for a metric.

        Args:
            metric_name: Metric identifier
            quantity: Amount to increment

        Returns:
            New usage count
        """
        current = self.get_usage(metric_name)
        new_usage = current + quantity
        self._usage_cache[metric_name] = new_usage

        logger.debug(
            "Incremented usage",
            extra={
                "customer_id": self.customer_id,
                "metric": metric_name,
                "quantity": quantity,
                "new_total": new_usage,
            },
        )

        return new_usage

    def reset_usage(self, metric_name: str) -> None:
        """
        Reset usage for a metric (e.g., at billing period start).

        Args:
            metric_name: Metric identifier
        """
        self._usage_cache[metric_name] = 0
        logger.info(
            "Reset usage counter",
            extra={"customer_id": self.customer_id, "metric": metric_name},
        )

    def get_all_usage(self) -> Dict[str, int]:
        """Get all tracked usage metrics."""
        return dict(self._usage_cache)
