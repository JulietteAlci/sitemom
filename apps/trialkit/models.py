import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, F, Q, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from apps.orders.models import StripeCheckoutMixin

# No 0/O/1/I to avoid typos when the customer copies the code.
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def kit_size_label() -> str:
    """"4" or "4 à 6", for texts."""
    low, high = settings.TRIAL_KIT_MIN, settings.TRIAL_KIT_MAX
    return str(low) if low == high else f"{low} à {high}"


def validate_selection_size(count: int) -> None:
    low, high = settings.TRIAL_KIT_MIN, settings.TRIAL_KIT_MAX
    if not low <= count <= high:
        expected = f"exactement {low}" if low == high else f"entre {low} et {high}"
        raise ValidationError(
            f"Votre coffret doit contenir {expected} alliances (vous en avez choisi {count})."
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


class SampleRingQuerySet(models.QuerySet):
    def with_availability(self):
        """Annotate `in_use` (units reserved or out with customers) and `available`."""
        from apps.orders.payments import CHECKOUT_LIFETIME

        holding = Q(kits__status=TrialKitOrder.Status.PAID, kits__fulfillment__in=TrialKitOrder.HOLDING_STOCK) | Q(
            kits__status=TrialKitOrder.Status.PENDING,
            kits__created_at__gte=timezone.now() - CHECKOUT_LIFETIME,
        )
        return self.annotate(in_use=Count("kits", filter=holding, distinct=True)).annotate(
            available=Greatest(F("quantity") - F("in_use"), Value(0))
        )


class SampleRing(models.Model):
    """A dummy ring sent in trial kits, mirroring a real gold ring. Only dummies have a stock."""

    reference = models.CharField(
        "référence factice", max_length=40, unique=True, help_text="Ex. : FAC-ECL-01 (étiquetée sur le factice)."
    )
    ring = models.ForeignKey(
        "catalog.Ring", on_delete=models.PROTECT, related_name="samples", verbose_name="vraie alliance représentée"
    )
    size = models.PositiveSmallIntegerField("taille du factice", null=True, blank=True)
    quantity = models.PositiveSmallIntegerField("exemplaires possédés", default=1)
    is_active = models.BooleanField("proposé dans les coffrets", default=True)
    notes = models.CharField("notes", max_length=255, blank=True)

    objects = SampleRingQuerySet.as_manager()

    class Meta:
        ordering = ["ring__position", "reference"]
        verbose_name = "alliance factice"
        verbose_name_plural = "alliances factices (stock)"

    def __str__(self):
        return f"{self.reference} — {self.ring.name}"

    @property
    def name(self) -> str:
        return self.ring.name

    def available_count(self) -> int:
        annotated = SampleRing.objects.with_availability().filter(pk=self.pk).first()
        return annotated.available if annotated else 0


class TrialKitOrder(StripeCheckoutMixin):
    """A home try-on kit of dummy rings (see SampleRing).

    Payment = credit (deducted from the ring order with the unique code, never refunded otherwise)
    + refundable part (refunded once the kit is back and checked by the team).
    """

    class Fulfillment(models.TextChoices):
        TO_PREPARE = "to_prepare", "À préparer"
        SHIPPED = "shipped", "Expédié"
        DELIVERED = "delivered", "Livré"
        RETURNED = "returned", "Reçu — à contrôler"
        REFUNDED = "refunded", "Contrôlé et remboursé"

    REFERENCE_PREFIX = "ESS"
    # Logistics states during which the kit's dummies are not on the shelf (back in stock once checked).
    HOLDING_STOCK = [Fulfillment.TO_PREPARE, Fulfillment.SHIPPED, Fulfillment.DELIVERED, Fulfillment.RETURNED]

    samples = models.ManyToManyField(SampleRing, related_name="kits", verbose_name="alliances factices")
    include_sizer = models.BooleanField("baguier inclus", default=True)
    message = models.TextField("message", blank=True)
    price = models.DecimalField("montant payé (€)", max_digits=8, decimal_places=2)
    credit_amount = models.DecimalField(
        "montant déductible (€)", max_digits=8, decimal_places=2, default=0,
        help_text="Déduit de la commande d'alliances avec le code unique.",
    )
    refund_amount = models.DecimalField(
        "montant remboursable (€)", max_digits=8, decimal_places=2, default=0,
        help_text="Remboursé au retour du coffret, après contrôle.",
    )
    credit_code = models.CharField(
        "code de déduction", max_length=20, unique=True, editable=False,
        help_text="À saisir dans le panier pour déduire le prix du coffret de la commande d'alliances.",
    )
    fulfillment = models.CharField(
        "logistique", max_length=12, choices=Fulfillment.choices, default=Fulfillment.TO_PREPARE, db_index=True
    )
    tracking_number = models.CharField("n° de suivi (aller)", max_length=60, blank=True)
    shipped_at = models.DateTimeField("expédié le", null=True, blank=True)
    delivered_at = models.DateTimeField("livré le", null=True, blank=True)
    returned_at = models.DateTimeField("reçu en retour le", null=True, blank=True)
    reminders_sent = models.PositiveSmallIntegerField("relances envoyées", default=0)
    last_reminder_at = models.DateTimeField("dernière relance", null=True, blank=True)
    refunded_at = models.DateTimeField("remboursé le", null=True, blank=True)
    refund_id = models.CharField("référence du remboursement", max_length=255, blank=True)

    class Meta(StripeCheckoutMixin.Meta):
        verbose_name = "coffret d'essai"
        verbose_name_plural = "coffrets d'essai"

    # --- Dates ---
    @property
    def estimated_delivery(self):
        """Actual delivery date, or shipping date + usual transit time."""
        if self.delivered_at:
            return timezone.localdate(self.delivered_at)
        if self.shipped_at:
            return timezone.localdate(self.shipped_at) + timedelta(days=settings.TRIAL_KIT_DELIVERY_DAYS)
        return None

    @property
    def return_deadline(self):
        delivery = self.estimated_delivery
        return delivery + timedelta(days=settings.TRIAL_KIT_RETURN_DAYS) if delivery else None

    @property
    def is_out(self) -> bool:
        """At the customer's (or on its way): reminders apply."""
        return self.fulfillment in (self.Fulfillment.SHIPPED, self.Fulfillment.DELIVERED)

    @property
    def is_return_late(self) -> bool:
        deadline = self.return_deadline
        if not deadline:
            return False
        returned = timezone.localdate(self.returned_at) if self.returned_at else timezone.localdate()
        return returned > deadline

    @property
    def reminder_due(self) -> bool:
        if not self.is_out or not self.email:
            return False
        last_contact = self.last_reminder_at or self.shipped_at
        return timezone.now() - last_contact >= timedelta(days=settings.TRIAL_KIT_REMINDER_EVERY_DAYS)

    @property
    def can_be_refunded(self) -> bool:
        return self.fulfillment == self.Fulfillment.RETURNED and not self.refunded_at

    def mark_paid(self, session: dict) -> bool:
        changed = super().mark_paid(session)
        if changed:
            from .services import send_confirmation

            send_confirmation(self)
        return changed

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
