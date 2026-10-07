import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.orders.models import StripeCheckoutMixin

# No 0/O/1/I to avoid typos when the customer copies the code.
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def validate_selection_size(count: int) -> None:
    low, high = settings.TRIAL_KIT_MIN, settings.TRIAL_KIT_MAX
    if not low <= count <= high:
        raise ValidationError(
            f"Votre coffret doit contenir entre {low} et {high} alliances (vous en avez choisi {count})."
        )


def generate_credit_code() -> str:
    while True:
        raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        code = f"ESSAI-{raw[:4]}-{raw[4:]}"
        if not TrialKitOrder.objects.filter(credit_code=code).exists():
            return code


def normalize_code(value: str) -> str:
    """Accept 'essai-abcd-efgh', 'ABCDEFGH', 'ESSAI ABCD EFGH'… and return 'ESSAI-ABCD-EFGH'."""
    raw = "".join(ch for ch in (value or "").upper() if ch.isalnum())
    raw = raw.removeprefix("ESSAI")
    return f"ESSAI-{raw[:4]}-{raw[4:]}" if len(raw) == 8 else ""


class TrialKitOrder(StripeCheckoutMixin):
    """A home try-on box of 8 to 12 sample rings.

    The kit is paid up front; its price is deducted from the ring order through a unique
    credit code. It is not refunded if the customer never orders.
    """

    class Fulfillment(models.TextChoices):
        TO_PREPARE = "to_prepare", "À préparer"
        SHIPPED = "shipped", "Expédié"
        RETURNED = "returned", "Retourné"
        CONVERTED = "converted", "Converti en commande"

    REFERENCE_PREFIX = "ESS"

    rings = models.ManyToManyField("catalog.Ring", related_name="trial_kits", verbose_name="alliances")
    include_sizer = models.BooleanField("baguier inclus", default=True)
    message = models.TextField("message", blank=True)
    price = models.DecimalField("prix du coffret (€)", max_digits=8, decimal_places=2)
    credit_code = models.CharField(
        "code de déduction", max_length=20, unique=True, editable=False,
        help_text="À saisir dans le panier pour déduire le prix du coffret de la commande d'alliances.",
    )
    fulfillment = models.CharField(
        "logistique", max_length=12, choices=Fulfillment.choices, default=Fulfillment.TO_PREPARE
    )
    shipped_at = models.DateTimeField("expédié le", null=True, blank=True)
    returned_at = models.DateTimeField("retourné le", null=True, blank=True)

    class Meta(StripeCheckoutMixin.Meta):
        verbose_name = "coffret d'essai"
        verbose_name_plural = "coffrets d'essai"

    def save(self, *args, **kwargs):
        if not self.credit_code:
            self.credit_code = generate_credit_code()
        super().save(*args, **kwargs)

    @property
    def redeemed_order(self):
        return self.orders.filter(status=self.orders.model.Status.PAID).first()

    def credit_unavailable_reason(self) -> str | None:
        """Why the credit code cannot be used right now, or None if it can."""
        from apps.orders.payments import CHECKOUT_LIFETIME

        if self.status != self.Status.PAID:
            return "Ce code sera actif dès la confirmation du paiement de votre coffret."
        if self.redeemed_order:
            return "Ce code a déjà été utilisé pour une commande."
        recent_checkout = self.orders.filter(
            status=self.orders.model.Status.PENDING, created_at__gte=timezone.now() - CHECKOUT_LIFETIME
        )
        if recent_checkout.exists():
            return "Ce code est en cours d'utilisation pour un paiement. Réessayez dans 30 minutes."
        return None

    @classmethod
    def find_by_code(cls, code: str):
        return cls.objects.filter(credit_code=normalize_code(code)).first()
