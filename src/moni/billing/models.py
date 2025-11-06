from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    PAUSED = "paused"


@dataclass(slots=True)
class SubscriptionRecord:
    customer_id: str
    subscription_id: str
    price_id: str
    status: SubscriptionStatus
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    email: Optional[str] = None
    tier_name: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.status in {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE,
        } and not self.cancel_at_period_end

    def seconds_until_expiry(self, now: Optional[datetime] = None) -> Optional[int]:
        if self.current_period_end is None:
            return None
        reference = now or datetime.now(tz=timezone.utc)
        delta = self.current_period_end - reference
        return max(int(delta.total_seconds()), 0)


@dataclass(slots=True)
class CheckoutSessionResult:
    session_id: str
    url: str
    price_id: str
    tier_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    customer_id: Optional[str] = None


BillingMode = Literal["subscription"]
