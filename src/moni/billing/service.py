from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable

import stripe
from fastapi import HTTPException

from .models import CheckoutSessionResult, SubscriptionRecord, SubscriptionStatus
from .settings import StripeBillingSettings, StripeTier
from .storage import save, get_by_customer
from .tier_config import get_billing_config


class StripeBillingService:
    def __init__(self, settings: StripeBillingSettings) -> None:
        self._settings = settings
        self._config = get_billing_config()
        stripe.api_key = settings.secret_key

    @property
    def publishable_key(self) -> str:
        return self._settings.publishable_key

    @property
    def tiers(self) -> list[StripeTier]:
        return list(self._settings.tiers)

    @property
    def currency(self) -> str:
        return self._settings.currency

    def create_checkout_session(
        self,
        tier_identifier: str,
        customer_email: str | None = None,
        coupon_id: str | None = None,
        trial_from_price: bool = False,
    ) -> CheckoutSessionResult:
        try:
            tier = self._settings.resolve_tier(tier_identifier)
            price_id = tier.stripe_price_id

            subscription_data: Dict[str, Any] = {}
            if not trial_from_price:
                trial_days = tier.trial_period_days
                if trial_days:
                    subscription_data["trial_period_days"] = trial_days

            create_params: Dict[str, Any] = {
                "success_url": self._settings.success_return_url + "?session_id={CHECKOUT_SESSION_ID}",
                "cancel_url": self._settings.cancel_return_url,
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
            }
            if subscription_data:
                create_params["subscription_data"] = subscription_data
            if customer_email:
                create_params["customer_email"] = customer_email
            if coupon_id:
                create_params["discounts"] = [{"coupon": coupon_id}]

            session = stripe.checkout.Session.create(**create_params)
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        expires_at = None
        if session.expires_at:
            expires_at = datetime.fromtimestamp(session.expires_at, tz=timezone.utc)
        return CheckoutSessionResult(
            session_id=session.id,
            url=session.url,
            price_id=price_id,
            tier_name=tier.name,
            expires_at=expires_at,
            customer_id=session.get("customer"),
        )

    def retrieve_subscription(self, subscription_id: str) -> SubscriptionRecord | None:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
        except stripe.error.InvalidRequestError:
            return None
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        record = self._build_subscription_record(subscription)
        if record:
            save(record)
        return record

    def sync_customer_subscription(self, customer_id: str) -> SubscriptionRecord | None:
        try:
            subscriptions = stripe.Subscription.list(customer=customer_id, status="all", limit=1)
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        data: Iterable[dict[str, Any]] = subscriptions.get("data", []) if isinstance(subscriptions, dict) else subscriptions.data
        for subscription in data:
            record = self._build_subscription_record(subscription)
            if record:
                save(record)
                return record
        return None

    def create_billing_portal_session(self, customer_id: str, return_url: str | None = None) -> str:
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url or self._settings.success_return_url,
            )
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return session.url

    @staticmethod
    def _parse_timestamp(raw_ts: Any) -> datetime | None:
        if not raw_ts:
            return None
        if isinstance(raw_ts, (int, float)):
            return datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
        if isinstance(raw_ts, str):
            try:
                parsed = datetime.fromisoformat(raw_ts)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        return None

    def _build_subscription_record(self, subscription: Dict[str, Any]) -> SubscriptionRecord | None:
        if not subscription:
            return None
        items = subscription.get("items", {})
        data = items.get("data", []) if isinstance(items, dict) else []
        if not data:
            return None
        first_item = data[0]
        price = first_item.get("price", {})
        price_id = price.get("id")
        if not price_id:
            return None

        customer_details = subscription.get("customer_details") or {}
        email = customer_details.get("email") or subscription.get("customer_email")

        record = SubscriptionRecord(
            customer_id=subscription["customer"],
            subscription_id=subscription["id"],
            price_id=price_id,
            status=SubscriptionStatus(subscription["status"]),
            current_period_end=self._parse_timestamp(subscription.get("current_period_end")),
            cancel_at_period_end=subscription.get("cancel_at_period_end", False),
            email=email,
        )
        tier = self._settings.get_tier_by_price_id(price_id)
        if tier:
            record.tier_name = tier.name
        return record

    def upgrade_subscription(
        self,
        customer_id: str,
        new_price_id: str,
        prorate: bool = True,
    ) -> SubscriptionRecord:
        """
        Upgrade subscription to a higher tier.

        Args:
            customer_id: Stripe customer ID
            new_price_id: New Stripe price ID
            prorate: Whether to prorate the upgrade

        Returns:
            Updated subscription record

        Raises:
            HTTPException: If upgrade fails
        """
        subscription_record = get_by_customer(customer_id)
        if not subscription_record:
            raise HTTPException(status_code=404, detail="Subscription not found")

        try:
            subscription = stripe.Subscription.retrieve(
                subscription_record.subscription_id,
                expand=["items"],
            )

            # Find the subscription item to update
            items = subscription.get("items", {}).get("data", [])
            if not items:
                raise HTTPException(status_code=400, detail="No subscription items found")

            subscription_item_id = items[0]["id"]

            # Update subscription
            updated_subscription = stripe.Subscription.modify(
                subscription_record.subscription_id,
                proration_behavior="create_prorations" if prorate else "none",
                items=[
                    {
                        "id": subscription_item_id,
                        "price": new_price_id,
                    }
                ],
            )

        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # Update local record
        record = self._build_subscription_record(updated_subscription)
        if record:
            save(record)
        return record

    def downgrade_subscription(
        self,
        customer_id: str,
        new_price_id: str,
        at_period_end: bool = True,
    ) -> SubscriptionRecord:
        """
        Downgrade subscription to a lower tier.

        Args:
            customer_id: Stripe customer ID
            new_price_id: New Stripe price ID
            at_period_end: Whether to apply change at period end (recommended)

        Returns:
            Updated subscription record

        Raises:
            HTTPException: If downgrade fails
        """
        subscription_record = get_by_customer(customer_id)
        if not subscription_record:
            raise HTTPException(status_code=404, detail="Subscription not found")

        try:
            subscription = stripe.Subscription.retrieve(
                subscription_record.subscription_id,
                expand=["items"],
            )

            items = subscription.get("items", {}).get("data", [])
            if not items:
                raise HTTPException(status_code=400, detail="No subscription items found")

            subscription_item_id = items[0]["id"]

            if at_period_end:
                # Schedule downgrade for end of period
                updated_subscription = stripe.Subscription.modify(
                    subscription_record.subscription_id,
                    proration_behavior="none",
                    items=[
                        {
                            "id": subscription_item_id,
                            "price": new_price_id,
                        }
                    ],
                    proration_date=subscription.get("current_period_end"),
                )
            else:
                # Apply immediately with proration
                updated_subscription = stripe.Subscription.modify(
                    subscription_record.subscription_id,
                    proration_behavior="create_prorations",
                    items=[
                        {
                            "id": subscription_item_id,
                            "price": new_price_id,
                        }
                    ],
                )

        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        record = self._build_subscription_record(updated_subscription)
        if record:
            save(record)
        return record

    def change_subscription_plan(
        self,
        customer_id: str,
        new_price_id: str,
        prorate: bool | None = None,
    ) -> SubscriptionRecord:
        """
        Change subscription plan with automatic upgrade/downgrade detection.

        Args:
            customer_id: Stripe customer ID
            new_price_id: New Stripe price ID
            prorate: Proration behavior (None = auto-detect)

        Returns:
            Updated subscription record
        """
        subscription_record = get_by_customer(customer_id)
        if not subscription_record:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Get current and new tier configurations
        current_tier = self._config.get_tier_by_price_id(subscription_record.price_id)
        new_tier = self._config.get_tier_by_price_id(new_price_id)

        if not current_tier or not new_tier:
            raise HTTPException(status_code=400, detail="Invalid price ID")

        # Determine if upgrade or downgrade
        is_upgrade = new_tier.base_price > current_tier.base_price

        if prorate is None:
            # Auto-determine proration based on config
            prorate = self._config.proration_enabled

        if is_upgrade:
            return self.upgrade_subscription(customer_id, new_price_id, prorate=prorate)
        else:
            return self.downgrade_subscription(customer_id, new_price_id, at_period_end=True)

    def preview_subscription_change(
        self,
        customer_id: str,
        new_price_id: str,
    ) -> Dict[str, Any]:
        """
        Preview invoice for subscription change.

        Args:
            customer_id: Stripe customer ID
            new_price_id: New Stripe price ID

        Returns:
            Dictionary with preview information
        """
        subscription_record = get_by_customer(customer_id)
        if not subscription_record:
            raise HTTPException(status_code=404, detail="Subscription not found")

        try:
            subscription = stripe.Subscription.retrieve(
                subscription_record.subscription_id,
                expand=["items"],
            )

            items = subscription.get("items", {}).get("data", [])
            if not items:
                raise HTTPException(status_code=400, detail="No subscription items found")

            subscription_item_id = items[0]["id"]

            # Preview upcoming invoice
            upcoming_invoice = stripe.Invoice.upcoming(
                customer=customer_id,
                subscription=subscription_record.subscription_id,
                subscription_items=[
                    {
                        "id": subscription_item_id,
                        "price": new_price_id,
                    }
                ],
            )

        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # Calculate proration amount
        proration_amount = 0
        proration_lines = []

        for line in upcoming_invoice.get("lines", {}).get("data", []):
            if line.get("proration"):
                proration_amount += line.get("amount", 0)
                proration_lines.append({
                    "description": line.get("description"),
                    "amount": line.get("amount", 0) / 100,  # Convert cents to dollars
                    "period_start": line.get("period", {}).get("start"),
                    "period_end": line.get("period", {}).get("end"),
                })

        return {
            "immediate_charge": upcoming_invoice.get("amount_due", 0) / 100,
            "proration_amount": proration_amount / 100,
            "proration_lines": proration_lines,
            "next_invoice_date": upcoming_invoice.get("period_end"),
            "currency": upcoming_invoice.get("currency", "usd"),
            "total": upcoming_invoice.get("total", 0) / 100,
        }

    def pause_subscription(
        self,
        customer_id: str,
        resumes_at: datetime | None = None,
    ) -> SubscriptionRecord:
        """
        Pause subscription billing.

        Args:
            customer_id: Stripe customer ID
            resumes_at: When to resume (None = indefinite)

        Returns:
            Updated subscription record
        """
        subscription_record = get_by_customer(customer_id)
        if not subscription_record:
            raise HTTPException(status_code=404, detail="Subscription not found")

        try:
            pause_params: Dict[str, Any] = {
                "behavior": "mark_uncollectible",
            }
            if resumes_at:
                pause_params["resumes_at"] = int(resumes_at.timestamp())

            subscription = stripe.Subscription.modify(
                subscription_record.subscription_id,
                pause_collection=pause_params,
            )

        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        record = self._build_subscription_record(subscription)
        if record:
            save(record)
        return record

    def resume_subscription(self, customer_id: str) -> SubscriptionRecord:
        """
        Resume paused subscription.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Updated subscription record
        """
        subscription_record = get_by_customer(customer_id)
        if not subscription_record:
            raise HTTPException(status_code=404, detail="Subscription not found")

        try:
            subscription = stripe.Subscription.modify(
                subscription_record.subscription_id,
                pause_collection="",  # Remove pause
            )

        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        record = self._build_subscription_record(subscription)
        if record:
            save(record)
        return record
