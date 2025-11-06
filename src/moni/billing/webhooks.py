from __future__ import annotations

import stripe
from datetime import datetime, timezone

from fastapi import HTTPException

from .models import SubscriptionRecord, SubscriptionStatus
from .settings import StripeBillingSettings
from .storage import get_by_subscription, save


class StripeWebhookHandler:
    def __init__(self, settings: StripeBillingSettings) -> None:
        self._settings = settings

    def parse_event(self, payload: bytes, signature: str) -> stripe.Event:
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=self._settings.webhook_secret,
                tolerance=300,
            )
        except stripe.error.SignatureVerificationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return event

    def handle_event(self, event: stripe.Event) -> None:
        event_type = event["type"]
        if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
            self._handle_subscription_update(event)
        elif event_type == "customer.subscription.deleted":
            self._handle_subscription_deleted(event)
        elif event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
            self._handle_invoice_event(event)

    def _handle_subscription_update(self, event: stripe.Event) -> None:
        subscription = event["data"]["object"]
        record = SubscriptionRecord(
            customer_id=subscription["customer"],
            subscription_id=subscription["id"],
            price_id=subscription["items"]["data"][0]["price"]["id"],
            status=SubscriptionStatus(subscription["status"]),
            current_period_end=self._parse_timestamp(subscription.get("current_period_end")),
            cancel_at_period_end=subscription.get("cancel_at_period_end", False),
            email=subscription.get("customer_email"),
        )
        tier = self._settings.get_tier_by_price_id(record.price_id)
        if tier:
            record.tier_name = tier.name
        save(record)

    def _handle_subscription_deleted(self, event: stripe.Event) -> None:
        subscription = event["data"]["object"]
        record = get_by_subscription(subscription["id"])
        if not record:
            return
        record.status = SubscriptionStatus.CANCELED
        record.cancel_at_period_end = True
        save(record)

    def _handle_invoice_event(self, event: stripe.Event) -> None:
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            return
        record = get_by_subscription(subscription_id)
        if not record:
            return
        status = invoice.get("status")
        if status == "paid":
            record.status = SubscriptionStatus.ACTIVE
            record.cancel_at_period_end = False
            record.current_period_end = self._parse_timestamp(invoice.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end"))
        elif status in {"open", "uncollectible", "past_due"}:
            record.status = SubscriptionStatus.PAST_DUE
        elif status == "void":
            record.status = SubscriptionStatus.CANCELED
            record.cancel_at_period_end = True
        save(record)

    @staticmethod
    def _parse_timestamp(raw_ts: int | None) -> datetime | None:
        if not raw_ts:
            return None
        return datetime.fromtimestamp(raw_ts, tz=timezone.utc)
