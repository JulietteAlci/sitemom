"""Session-based cart. Prices are never stored: they are recomputed from the live gold spot."""
import uuid
from dataclasses import dataclass
from decimal import Decimal

from apps.catalog.models import Ring
from apps.pricing.models import GoldPrice
from apps.pricing.services import PriceBreakdown

MAX_QUANTITY = 4


@dataclass
class CartLine:
    id: str
    ring: Ring
    size: int
    engraving: str
    quantity: int
    breakdown: PriceBreakdown | None

    @property
    def unit_price(self) -> Decimal | None:
        return self.breakdown.price_ttc if self.breakdown else None

    @property
    def total(self) -> Decimal | None:
        return self.unit_price * self.quantity if self.breakdown else None


class Cart:
    SESSION_KEY = "cart"

    def __init__(self, request):
        self.session = request.session
        self._items = self.session.get(self.SESSION_KEY, [])

    def _save(self):
        self.session[self.SESSION_KEY] = self._items
        self.session.modified = True

    def add(self, ring: Ring, size: int, engraving: str = "", quantity: int = 1):
        for item in self._items:
            if item["ring_id"] == ring.pk and item["size"] == size and item["engraving"] == engraving:
                item["quantity"] = min(item["quantity"] + quantity, MAX_QUANTITY)
                break
        else:
            self._items.append(
                {
                    "id": uuid.uuid4().hex[:12],
                    "ring_id": ring.pk,
                    "size": size,
                    "engraving": engraving,
                    "quantity": min(quantity, MAX_QUANTITY),
                }
            )
        self._save()

    def remove(self, line_id: str):
        self._items = [item for item in self._items if item["id"] != line_id]
        self._save()

    def clear(self):
        self._items = []
        self._save()

    def __len__(self):
        return sum(item["quantity"] for item in self._items)

    def lines(self, spot: GoldPrice | None = None) -> list[CartLine]:
        spot = spot or GoldPrice.current()
        rings = Ring.objects.filter(is_active=True).in_bulk([item["ring_id"] for item in self._items])
        lines = []
        for item in self._items:
            ring = rings.get(item["ring_id"])
            if ring is None or not ring.is_valid_size(item["size"]):
                continue  # product removed or size range changed since it was added
            lines.append(
                CartLine(
                    id=item["id"],
                    ring=ring,
                    size=item["size"],
                    engraving=item["engraving"],
                    quantity=item["quantity"],
                    breakdown=ring.price(item["size"], spot) if spot else None,
                )
            )
        return lines

    @staticmethod
    def total(lines: list[CartLine]) -> Decimal | None:
        if any(line.total is None for line in lines):
            return None
        return sum((line.total for line in lines), Decimal(0))
