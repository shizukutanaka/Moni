from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Environment variable '{name}' must be set for Stripe billing integration"
        )
    return value


@dataclass(slots=True)
class StripeTier:
    name: str
    stripe_price_id: str
    description: str
    features: List[str] = field(default_factory=list)
    billing_interval: str = "month"
    trial_period_days: int | None = None


@dataclass(slots=True)
class StripeBillingSettings:
    secret_key: str
    publishable_key: str
    webhook_secret: str
    success_return_url: str
    cancel_return_url: str
    currency: str = "usd"
    tiers: List[StripeTier] = field(default_factory=list)

    def get_tier_by_name(self, name: str) -> StripeTier | None:
        lowered = name.lower()
        for tier in self.tiers:
            if tier.name.lower() == lowered:
                return tier
        return None

    def get_tier_by_price_id(self, price_id: str) -> StripeTier | None:
        for tier in self.tiers:
            if tier.stripe_price_id == price_id:
                return tier
        return None

    def resolve_tier(self, identifier: str) -> StripeTier:
        tier = self.get_tier_by_name(identifier)
        if tier is not None:
            return tier
        tier = self.get_tier_by_price_id(identifier)
        if tier is not None:
            return tier
        raise KeyError(f"Tier '{identifier}' is not configured")

    @classmethod
    def load_from_env(cls) -> "StripeBillingSettings":
        secret_key = _require_env("MONI_STRIPE_SECRET_KEY")
        publishable_key = _require_env("MONI_STRIPE_PUBLISHABLE_KEY")
        webhook_secret = _require_env("MONI_STRIPE_WEBHOOK_SECRET")
        success_return_url = _require_env("MONI_STRIPE_SUCCESS_URL")
        cancel_return_url = _require_env("MONI_STRIPE_CANCEL_URL")
        currency = os.getenv("MONI_STRIPE_CURRENCY", "usd").strip().lower() or "usd"

        tiers: List[StripeTier] = []
        tier_prefix = "MONI_STRIPE_TIER_"
        for key, value in os.environ.items():
            if not key.startswith(tier_prefix):
                continue
            tier_name = key[len(tier_prefix) :]
            parts = [segment.strip() for segment in value.split("|") if segment.strip()]
            if not parts:
                continue
            price_id = parts[0]
            description = parts[1] if len(parts) > 1 else tier_name.title()
            features = parts[2].split(",") if len(parts) > 2 else []
            features = [feature.strip() for feature in features if feature.strip()]
            interval = parts[3] if len(parts) > 3 else "month"
            interval = interval if interval in {"month", "year"} else "month"
            trial = None
            if len(parts) > 4:
                try:
                    trial = max(1, min(int(parts[4]), 90))
                except ValueError:
                    trial = None
            tiers.append(
                StripeTier(
                    name=tier_name,
                    stripe_price_id=price_id,
                    description=description,
                    features=features,
                    billing_interval=interval,
                    trial_period_days=trial,
                )
            )

        if not tiers:
            raise RuntimeError(
                "At least one Stripe tier must be provided via MONI_STRIPE_TIER_* environment variables"
            )

        return cls(
            secret_key=secret_key,
            publishable_key=publishable_key,
            webhook_secret=webhook_secret,
            success_return_url=success_return_url,
            cancel_return_url=cancel_return_url,
            currency=currency,
            tiers=tiers,
        )
