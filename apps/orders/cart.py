"""Session-based cart. Prices are never stored: they are recomputed from the live gold spot."""
import uuid
from dataclasses import dataclass
from decimal import Decimal

from apps.catalog.models import Metal, Ring, StoneOption
from apps.pricing.models import GoldPrice
from apps.pricing.services import PriceBreakdown
from apps.trialkit.models import TrialKitOrder

MAX_QUANTITY = 4


@dataclass
class CartLine:
    id: str
    ring: Ring
    size: int
    engraving: str
    quantity: int
    breakdown: PriceBreakdown | None
    metal: Metal | None = None
    stone: StoneOption | None = None
    comment: str = ""

    @property
    def description(self) -> str:
        """Options summary, e.g. "Or jaune · Diamant naturel 0,50 carat · taille 54"."""
        parts = [self.metal.name if self.metal else "", str(self.stone) if self.stone else "", f"taille {self.size}"]
        return " · ".join(part for part in parts if part)

    @property
    def unit_price(self) -> Decimal | None:
        return self.breakdown.price_ttc if self.breakdown else None

    @property
    def total(self) -> Decimal | None:
        return self.unit_price * self.quantity if self.breakdown else None


@dataclass
class TrialKitCredit:
    """Result of applying a trial kit code to the cart."""

    code: str
    kit: TrialKitOrder | None = None
    amount: Decimal = Decimal(0)
    error: str | None = None


class Cart:
    SESSION_KEY = "cart"
    CODE_SESSION_KEY = "trial_kit_code"

    def __init__(self, request):
        self.session = request.session
        self._items = self.session.get(self.SESSION_KEY, [])

    @property
    def trial_kit_code(self) -> str:
        return self.session.get(self.CODE_SESSION_KEY, "")

    def set_trial_kit_code(self, code: str):
        self.session[self.CODE_SESSION_KEY] = code

    def clear_trial_kit_code(self):
        self.session.pop(self.CODE_SESSION_KEY, None)

    def trial_kit_credit(self, subtotal: Decimal | None) -> TrialKitCredit | None:
        """Deduct the trial kit price from the cart if the stored code is valid."""
        code = self.trial_kit_code
        if not code:
            return None
        kit = TrialKitOrder.find_by_code(code)
        if kit is None:
            return TrialKitCredit(code=code, error="Ce code est inconnu.")
        error = kit.credit_unavailable_reason()
        if error:
            return TrialKitCredit(code=code, kit=kit, error=error)
        return TrialKitCredit(code=code, kit=kit, amount=min(kit.credit_amount, subtotal or Decimal(0)))

    def _save(self):
        self.session[self.SESSION_KEY] = self._items
        self.session.modified = True

    def add(
        self, ring: Ring, size: int, engraving: str = "", quantity: int = 1, metal: str = "",
        stone_id: int | None = None, comment: str = "",
    ):
        options = {"size": size, "engraving": engraving, "metal": metal, "stone_id": stone_id, "comment": comment}
        for item in self._items:
            if item["ring_id"] == ring.pk and all(item.get(key, "") == value for key, value in options.items()):
                item["quantity"] = min(item["quantity"] + quantity, MAX_QUANTITY)
                break
        else:
            self._items.append(
                {"id": uuid.uuid4().hex[:12], "ring_id": ring.pk, "quantity": min(quantity, MAX_QUANTITY), **options}
            )
        self._save()

    def remove(self, line_id: str):
        self._items = [item for item in self._items if item["id"] != line_id]
        self._save()

    def clear(self):
        self._items = []
        self._save()
        self.clear_trial_kit_code()

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
            metals = ring.available_metals()
            metal = next((m for m in metals if m.code == item.get("metal")), None) or ring.default_metal()
            options = {option.pk: option for option in ring.stone_options.all()}
            stone = options.get(item.get("stone_id"))
            if options and stone is None:
                continue  # stone option removed since it was added
            lines.append(
                CartLine(
                    id=item["id"],
                    ring=ring,
                    size=item["size"],
                    engraving=item["engraving"],
                    quantity=item["quantity"],
                    breakdown=ring.price(item["size"], spot, stone) if spot else None,
                    metal=metal,
                    stone=stone,
                    comment=item.get("comment", ""),
                )
            )
        return lines

    @staticmethod
    def total(lines: list[CartLine]) -> Decimal | None:
        if any(line.total is None for line in lines):
            return None
        return sum((line.total for line in lines), Decimal(0))
