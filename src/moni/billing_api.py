from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .billing.service import StripeBillingService
from .billing.settings import StripeBillingSettings
from .billing.storage import get_by_customer
from .billing.webhooks import StripeWebhookHandler

logger = logging.getLogger(__name__)
app = FastAPI(title="Moni Billing API", version="1.0.0")


class _ServiceContainer:
    def __init__(self) -> None:
        self._settings: StripeBillingSettings | None = None
        self._service: StripeBillingService | None = None
        self._webhooks: StripeWebhookHandler | None = None

    def get_service(self) -> StripeBillingService:
        if not self._service:
            settings = self.get_settings()
            self._service = StripeBillingService(settings)
        return self._service

    def get_webhooks(self) -> StripeWebhookHandler:
        if not self._webhooks:
            self._webhooks = StripeWebhookHandler(self.get_settings())
        return self._webhooks

    def get_settings(self) -> StripeBillingSettings:
        if not self._settings:
            try:
                self._settings = StripeBillingSettings.load_from_env()
            except RuntimeError as exc:
                logger.error("Billing configuration error", exc_info=True)
                raise HTTPException(status_code=500, detail=str(exc)) from exc
        return self._settings


_container = _ServiceContainer()


def get_billing_service() -> StripeBillingService:
    return _container.get_service()


def get_webhook_handler() -> StripeWebhookHandler:
    return _container.get_webhooks()


def get_billing_settings() -> StripeBillingSettings:
    return _container.get_settings()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/tiers")
def list_tiers(settings: StripeBillingSettings = Depends(get_billing_settings)) -> Dict[str, Any]:
    return {
        "currency": settings.currency,
        "tiers": [
            {
                "name": tier.name,
                "price_id": tier.stripe_price_id,
                "description": tier.description,
                "features": tier.features,
                "billing_interval": tier.billing_interval,
                "trial_period_days": tier.trial_period_days,
            }
            for tier in settings.tiers
        ],
        "publishable_key": settings.publishable_key,
    }


@app.post("/checkout")
def create_checkout_session(
    payload: Dict[str, Any],
    service: StripeBillingService = Depends(get_billing_service),
) -> Dict[str, str]:
    tier_identifier = payload.get("tier") or payload.get("price_id")
    if not tier_identifier:
        raise HTTPException(status_code=400, detail="tier or price_id is required")

    customer_email = payload.get("email")
    coupon_id = payload.get("coupon")
    trial_from_price = bool(payload.get("trial_from_price", False))

    result = service.create_checkout_session(
        tier_identifier=tier_identifier,
        customer_email=customer_email,
        coupon_id=coupon_id,
        trial_from_price=trial_from_price,
    )
    return {
        "checkout_url": result.url,
        "session_id": result.session_id,
        "expires_at": _serialize_datetime(result.expires_at),
        "price_id": result.price_id,
        "tier_name": result.tier_name,
        "customer_id": result.customer_id,
        "publishable_key": service.publishable_key,
        "currency": service.currency,
    }


@app.get("/subscription/{customer_id}")
def get_subscription(customer_id: str) -> Dict[str, Any]:
    record = get_by_customer(customer_id)
    if not record:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {
        "customer_id": record.customer_id,
        "subscription_id": record.subscription_id,
        "price_id": record.price_id,
        "status": record.status.value,
        "cancel_at_period_end": record.cancel_at_period_end,
        "email": record.email,
        "tier_name": record.tier_name,
        "current_period_end": _serialize_datetime(record.current_period_end),
        "is_active": record.is_active,
        "seconds_until_expiry": record.seconds_until_expiry(),
    }


@app.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
    handler: StripeWebhookHandler = Depends(get_webhook_handler),
) -> JSONResponse:
    payload = await request.body()
    event = handler.parse_event(payload, stripe_signature)
    handler.handle_event(event)
    logger.info("Processed Stripe webhook", extra={"event_type": event["type"]})
    return JSONResponse(status_code=200, content={"received": True})


@app.post("/portal")
def create_billing_portal(
    payload: Dict[str, Any],
    service: StripeBillingService = Depends(get_billing_service),
) -> Dict[str, str]:
    customer_id = payload.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required")
    return_url = payload.get("return_url")
    portal_url = service.create_billing_portal_session(customer_id=customer_id, return_url=return_url)
    return {"portal_url": portal_url}


@app.post("/subscription/{customer_id}/upgrade")
def upgrade_subscription(
    customer_id: str,
    payload: Dict[str, Any],
    service: StripeBillingService = Depends(get_billing_service),
) -> Dict[str, Any]:
    """Upgrade subscription to a higher tier."""
    new_price_id = payload.get("price_id")
    if not new_price_id:
        raise HTTPException(status_code=400, detail="price_id is required")

    prorate = payload.get("prorate", True)
    record = service.upgrade_subscription(customer_id, new_price_id, prorate=prorate)

    return {
        "customer_id": record.customer_id,
        "subscription_id": record.subscription_id,
        "price_id": record.price_id,
        "tier_name": record.tier_name,
        "status": record.status.value,
        "message": f"Subscription upgraded to {record.tier_name}",
    }


@app.post("/subscription/{customer_id}/downgrade")
def downgrade_subscription(
    customer_id: str,
    payload: Dict[str, Any],
    service: StripeBillingService = Depends(get_billing_service),
) -> Dict[str, Any]:
    """Downgrade subscription to a lower tier."""
    new_price_id = payload.get("price_id")
    if not new_price_id:
        raise HTTPException(status_code=400, detail="price_id is required")

    at_period_end = payload.get("at_period_end", True)
    record = service.downgrade_subscription(customer_id, new_price_id, at_period_end=at_period_end)

    message = (
        f"Subscription will downgrade to {record.tier_name} at end of billing period"
        if at_period_end
        else f"Subscription downgraded to {record.tier_name}"
    )

    return {
        "customer_id": record.customer_id,
        "subscription_id": record.subscription_id,
        "price_id": record.price_id,
        "tier_name": record.tier_name,
        "status": record.status.value,
        "message": message,
    }


@app.post("/subscription/{customer_id}/change-plan")
def change_subscription_plan(
    customer_id: str,
    payload: Dict[str, Any],
    service: StripeBillingService = Depends(get_billing_service),
) -> Dict[str, Any]:
    """Change subscription plan with automatic upgrade/downgrade handling."""
    new_price_id = payload.get("price_id")
    if not new_price_id:
        raise HTTPException(status_code=400, detail="price_id is required")

    prorate = payload.get("prorate")
    record = service.change_subscription_plan(customer_id, new_price_id, prorate=prorate)

    return {
        "customer_id": record.customer_id,
        "subscription_id": record.subscription_id,
        "price_id": record.price_id,
        "tier_name": record.tier_name,
        "status": record.status.value,
    }


@app.get("/subscription/{customer_id}/preview-change")
def preview_subscription_change(
    customer_id: str,
    new_price_id: str,
    service: StripeBillingService = Depends(get_billing_service),
) -> Dict[str, Any]:
    """Preview invoice for subscription change."""
    preview = service.preview_subscription_change(customer_id, new_price_id)
    return preview


@app.post("/subscription/{customer_id}/pause")
def pause_subscription(
    customer_id: str,
    payload: Dict[str, Any],
    service: StripeBillingService = Depends(get_billing_service),
) -> Dict[str, Any]:
    """Pause subscription billing."""
    resumes_at_str = payload.get("resumes_at")
    resumes_at = None
    if resumes_at_str:
        from datetime import datetime
        resumes_at = datetime.fromisoformat(resumes_at_str)

    record = service.pause_subscription(customer_id, resumes_at=resumes_at)

    return {
        "customer_id": record.customer_id,
        "subscription_id": record.subscription_id,
        "status": record.status.value,
        "message": "Subscription paused",
    }


@app.post("/subscription/{customer_id}/resume")
def resume_subscription(
    customer_id: str,
    service: StripeBillingService = Depends(get_billing_service),
) -> Dict[str, Any]:
    """Resume paused subscription."""
    record = service.resume_subscription(customer_id)

    return {
        "customer_id": record.customer_id,
        "subscription_id": record.subscription_id,
        "status": record.status.value,
        "message": "Subscription resumed",
    }


def main() -> None:
    import uvicorn

    uvicorn.run("moni.billing_api:app", host="0.0.0.0", port=8080)


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()
