from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Dict, Optional

from .models import SubscriptionRecord, SubscriptionStatus

_STORAGE_FILE = Path.home() / ".config" / "moni" / "stripe_subscriptions.json"
_LOCK = RLock()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _parse_datetime(raw: object) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _serialize_record(record: SubscriptionRecord) -> Dict[str, object]:
    return {
        "subscription_id": record.subscription_id,
        "price_id": record.price_id,
        "status": record.status.value,
        "cancel_at_period_end": record.cancel_at_period_end,
        "email": record.email,
        "tier_name": record.tier_name,
        "current_period_end": record.current_period_end.isoformat() if record.current_period_end else None,
    }


def load_all() -> Dict[str, SubscriptionRecord]:
    with _LOCK:
        if not _STORAGE_FILE.exists():
            return {}
        raw = json.loads(_STORAGE_FILE.read_text(encoding="utf-8"))
        records: Dict[str, SubscriptionRecord] = {}
        for customer_id, payload in raw.items():
            records[customer_id] = SubscriptionRecord(
                customer_id=customer_id,
                subscription_id=payload["subscription_id"],
                price_id=payload["price_id"],
                status=SubscriptionStatus(payload["status"]),
                current_period_end=_parse_datetime(payload.get("current_period_end")),
                cancel_at_period_end=payload.get("cancel_at_period_end", False),
                email=payload.get("email"),
                tier_name=payload.get("tier_name"),
            )
        return records


def save(record: SubscriptionRecord) -> None:
    with _LOCK:
        records = load_all()
        records[record.customer_id] = record
        serializable = {
            customer_id: _serialize_record(r)
            for customer_id, r in records.items()
        }
        _ensure_parent(_STORAGE_FILE)
        _STORAGE_FILE.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")


def get_by_customer(customer_id: str) -> Optional[SubscriptionRecord]:
    return load_all().get(customer_id)


def get_by_subscription(subscription_id: str) -> Optional[SubscriptionRecord]:
    records = load_all()
    for record in records.values():
        if record.subscription_id == subscription_id:
            return record
    return None
