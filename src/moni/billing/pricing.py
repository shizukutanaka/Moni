from __future__ import annotations

import os

# Minimum unit amounts (smallest currency unit) accepted by Stripe per currency.
# Reference: https://stripe.com/docs/currencies#minimum-and-maximum-charge-amounts
_MINIMUM_MINOR_UNITS: dict[str, int] = {
    "usd": 50,
    "eur": 50,
    "gbp": 30,
    "aud": 50,
    "cad": 50,
    "nzd": 50,
    "sgd": 50,
    "hkd": 400,
    "jpy": 50,
    "chf": 50,
    "dkk": 250,
    "nok": 300,
    "sek": 300,
    "czk": 1500,
    "pln": 200,
    "mxn": 1000,
}

_ENV_OVERRIDE = "MONI_STRIPE_LOCAL_MIN_MINOR"


def get_minimum_minor_units(currency: str) -> int:
    currency_code = currency.lower()
    override = os.getenv(_ENV_OVERRIDE)
    if override:
        try:
            value = int(override)
            if value > 0:
                return value
        except ValueError:
            pass
    if currency_code in _MINIMUM_MINOR_UNITS:
        return _MINIMUM_MINOR_UNITS[currency_code]
    raise RuntimeError(
        "Unsupported currency for automatic minimum pricing. "
        "Set environment variable MONI_STRIPE_LOCAL_MIN_MINOR with the minimum charge in minor units."
    )
