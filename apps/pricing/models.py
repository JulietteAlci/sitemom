from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

TROY_OUNCE_GRAMS = Decimal("31.1034768")


class GoldPrice(models.Model):
    """A snapshot of the gold spot price (XAU), in EUR per troy ounce of pure gold."""

    price_per_oz_eur = models.DecimalField("cours (€/once troy)", max_digits=12, decimal_places=4)
    source = models.CharField(max_length=64)
    fetched_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-fetched_at"]
        get_latest_by = "fetched_at"
        verbose_name = "cours spot de l'or"
        verbose_name_plural = "cours spot de l'or"

    def __str__(self):
        return f"{self.price_per_oz_eur} €/oz ({self.source}, {self.fetched_at:%d/%m/%Y %H:%M})"

    @property
    def price_per_gram_eur(self) -> Decimal:
        """Price of one gram of pure (24k) gold."""
        return self.price_per_oz_eur / TROY_OUNCE_GRAMS

    @property
    def is_fresh(self) -> bool:
        max_age = timedelta(minutes=settings.GOLD_PRICE_MAX_AGE_MINUTES)
        return timezone.now() - self.fetched_at <= max_age

    @classmethod
    def current(cls):
        return cls.objects.order_by("-fetched_at").first()
