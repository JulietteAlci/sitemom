"""Gold spot price providers.

Each provider returns the price of one troy ounce of pure gold, in EUR.
Select one with the GOLD_PRICE_PROVIDER setting.
"""
import logging
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 10


class GoldPriceUnavailable(Exception):
    pass


def _get_json(url, **kwargs):
    try:
        response = requests.get(url, timeout=TIMEOUT, **kwargs)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GoldPriceUnavailable(f"{url}: {exc}") from exc


def _positive_decimal(value, label):
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise GoldPriceUnavailable(f"{label}: invalid value {value!r}") from exc
    if not result.is_finite() or result <= 0:
        raise GoldPriceUnavailable(f"{label}: invalid value {value!r}")
    return result


def fetch_goldapi_io() -> Decimal:
    """goldapi.io — requires GOLDAPI_KEY, quotes directly in EUR."""
    if not settings.GOLDAPI_KEY:
        raise GoldPriceUnavailable("GOLDAPI_KEY is not configured")
    data = _get_json(
        "https://www.goldapi.io/api/XAU/EUR",
        headers={"x-access-token": settings.GOLDAPI_KEY},
    )
    return _positive_decimal(data.get("price"), "goldapi.io price")


def fetch_gold_api_com() -> Decimal:
    """gold-api.com (free, USD) converted to EUR with the ECB rate (frankfurter.app)."""
    usd_per_oz = _positive_decimal(
        _get_json("https://api.gold-api.com/price/XAU").get("price"), "gold-api.com price"
    )
    rates = _get_json("https://api.frankfurter.app/latest?from=USD&to=EUR").get("rates", {})
    usd_to_eur = _positive_decimal(rates.get("EUR"), "frankfurter USD→EUR")
    return usd_per_oz * usd_to_eur


PROVIDERS = {
    "goldapi": fetch_goldapi_io,
    "goldapicom": fetch_gold_api_com,
}


def fetch_spot_eur_per_oz(provider: str | None = None) -> tuple[Decimal, str]:
    name = provider or settings.GOLD_PRICE_PROVIDER
    if name not in PROVIDERS:
        raise GoldPriceUnavailable(
            f"Provider {name!r} cannot fetch automatically (use the admin to enter a manual price)."
        )
    return PROVIDERS[name](), name
