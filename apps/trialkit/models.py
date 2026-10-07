from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.orders.models import StripeCheckoutMixin


def validate_selection_size(count: int) -> None:
    low, high = settings.TRIAL_KIT_MIN, settings.TRIAL_KIT_MAX
    if not low <= count <= high:
        raise ValidationError(
            f"Votre coffret doit contenir entre {low} et {high} alliances (vous en avez choisi {count})."
        )


class TrialKitOrder(StripeCheckoutMixin):
    """A home try-on box of 8 to 12 sample rings, secured by a refundable deposit."""

    class Fulfillment(models.TextChoices):
        TO_PREPARE = "to_prepare", "À préparer"
        SHIPPED = "shipped", "Expédié"
        RETURNED = "returned", "Retourné"
        REFUNDED = "refunded", "Caution remboursée"
        CONVERTED = "converted", "Converti en commande"

    REFERENCE_PREFIX = "ESS"

    rings = models.ManyToManyField("catalog.Ring", related_name="trial_kits", verbose_name="alliances")
    include_sizer = models.BooleanField("baguier inclus", default=True)
    message = models.TextField("message", blank=True)
    deposit = models.DecimalField("caution (€)", max_digits=8, decimal_places=2)
    fulfillment = models.CharField(
        "logistique", max_length=12, choices=Fulfillment.choices, default=Fulfillment.TO_PREPARE
    )
    shipped_at = models.DateTimeField("expédié le", null=True, blank=True)
    returned_at = models.DateTimeField("retourné le", null=True, blank=True)

    class Meta(StripeCheckoutMixin.Meta):
        verbose_name = "coffret d'essai"
        verbose_name_plural = "coffrets d'essai"
