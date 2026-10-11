"""Resolve the options chosen on a product page (métal, type de pierre, poids carat, taille).

Each choice is a plain link (?metal=…&pierre=…&carat=…&taille=…) so the gold-indexed price is
always computed server-side and the page works without JavaScript.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from .models import Metal, Ring, StoneOption


@dataclass
class Selection:
    ring: Ring
    metal: Metal | None
    stone: StoneOption | None
    size: int

    def params(self, **overrides) -> dict:
        params = {
            "metal": self.metal.code if self.metal else None,
            "pierre": self.stone.stone_type if self.stone else None,
            "carat": f"{self.stone.carat:.2f}" if self.stone else None,
            "taille": self.size,
        }
        params.update(overrides)
        return {key: value for key, value in params.items() if value is not None}

    def url(self, **overrides) -> str:
        return f"{self.ring.get_absolute_url()}?{urlencode(self.params(**overrides))}"


def _parse_carat(value) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def pick_stone(options: list[StoneOption], stone_type=None, carat=None) -> StoneOption | None:
    if not options:
        return None
    types = list(dict.fromkeys(option.stone_type for option in options))
    stone_type = stone_type if stone_type in types else types[0]
    candidates = [option for option in options if option.stone_type == stone_type]
    carat = _parse_carat(carat)
    return next((option for option in candidates if option.carat == carat), candidates[0])


def resolve_selection(ring: Ring, params) -> Selection:
    metals = ring.available_metals()
    metal = next((m for m in metals if m.code == params.get("metal")), None) or ring.default_metal()
    stone = pick_stone(list(ring.stone_options.all()), params.get("pierre"), params.get("carat"))
    try:
        size = int(params.get("taille"))
    except (TypeError, ValueError):
        size = ring.reference_size
    if not ring.is_valid_size(size):
        size = ring.reference_size
    return Selection(ring=ring, metal=metal, stone=stone, size=size)


def selectors(selection: Selection) -> list[dict]:
    """Rows of the option panel: label, current value and the choices (as links)."""
    ring = selection.ring
    rows = [
        {
            "key": "metal",
            "label": "Métal",
            "value": selection.metal.name if selection.metal else "",
            "swatch": selection.metal.swatch if selection.metal else "",
            "choices": [
                {"label": m.name, "swatch": m.swatch, "url": selection.url(metal=m.code), "selected": m == selection.metal}
                for m in ring.available_metals()
            ],
        }
    ]
    options = list(ring.stone_options.all())
    if options:
        types = list(dict.fromkeys(option.stone_type for option in options))
        rows.append(
            {
                "key": "pierre",
                "label": "Type de pierre",
                "value": selection.stone.type_label,
                "choices": [
                    {
                        "label": pick_stone(options, stone_type).type_label,
                        "url": selection.url(pierre=stone_type),
                        "selected": stone_type == selection.stone.stone_type,
                    }
                    for stone_type in types
                ],
            }
        )
        rows.append(
            {
                "key": "carat",
                "label": "Poids carat",
                "value": selection.stone.carat_label,
                "choices": [
                    {
                        "label": option.carat_label,
                        "url": selection.url(carat=f"{option.carat:.2f}"),
                        "selected": option == selection.stone,
                    }
                    for option in options
                    if option.stone_type == selection.stone.stone_type
                ],
            }
        )
    rows.append(
        {
            "key": "taille",
            "label": "Taille",
            "value": str(selection.size),
            "choices": [
                {"label": str(size), "url": selection.url(taille=size), "selected": size == selection.size}
                for size in ring.sizes
            ],
        }
    )
    return rows
