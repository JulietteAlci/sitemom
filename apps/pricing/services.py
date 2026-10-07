import logging
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from django.conf import settings

from .models import GoldPrice
from .providers import fetch_spot_eur_per_oz

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")

# A new quote deviating more than this from the previous one is rejected as suspicious
# (an API glitch must never reprice the whole catalogue).
MAX_SPOT_VARIATION = Decimal("0.15")


class SuspiciousGoldPrice(Exception):
    pass


def refresh_gold_price(provider: str | None = None, force: bool = False) -> GoldPrice:
    price, source = fetch_spot_eur_per_oz(provider)
    previous = GoldPrice.current()
    if previous and not force:
        variation = abs(price - previous.price_per_oz_eur) / previous.price_per_oz_eur
        if variation > MAX_SPOT_VARIATION:
            raise SuspiciousGoldPrice(
                f"New quote {price:.2f} €/oz deviates {variation:.1%} from {previous.price_per_oz_eur:.2f} €/oz"
            )
    quote = GoldPrice.objects.create(price_per_oz_eur=price.quantize(Decimal("0.0001")), source=source)
    logger.info("Gold spot updated: %s", quote)
    return quote


@dataclass(frozen=True)
class PriceBreakdown:
    """Detailed price of a ring for a given size, indexed on the gold spot price."""

    weight_g: Decimal
    fine_gold_g: Decimal
    gold_value: Decimal
    price_ht: Decimal
    vat: Decimal
    price_ttc: Decimal
    spot: GoldPrice

    @property
    def amount_cents(self) -> int:
        return int(self.price_ttc * 100)


def compute_ring_price(ring, size: int | None = None, spot: GoldPrice | None = None) -> PriceBreakdown | None:
    """Price = ((fine gold weight × spot €/g) × (1 + gold markup) + labour + stones) × (1 + margin), + VAT.

    The TTC price is rounded up to the euro. Returns None if no spot price is known.
    """
    spot = spot or GoldPrice.current()
    if spot is None:
        return None
    weight = ring.weight_for_size(size or ring.reference_size)
    fine_gold = weight * Decimal(ring.purity) / Decimal(1000)
    gold_value = fine_gold * spot.price_per_gram_eur
    cost = gold_value * (1 + ring.gold_markup_rate) + ring.labor_cost + ring.stone_cost
    price_ht = cost * (1 + ring.margin_rate)
    vat_rate = Decimal(settings.VAT_RATE)
    price_ttc = (price_ht * (1 + vat_rate)).quantize(Decimal(1), rounding=ROUND_CEILING)
    price_ht = (price_ttc / (1 + vat_rate)).quantize(CENT, rounding=ROUND_HALF_UP)
    return PriceBreakdown(
        weight_g=weight.quantize(CENT),
        fine_gold_g=fine_gold.quantize(CENT),
        gold_value=gold_value.quantize(CENT),
        price_ht=price_ht,
        vat=price_ttc - price_ht,
        price_ttc=price_ttc,
        spot=spot,
    )
