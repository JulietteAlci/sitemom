import secrets

from django.db import models
from django.utils import timezone


def generate_reference(prefix: str) -> str:
    return f"{prefix}-{timezone.now():%y%m}-{secrets.token_hex(3).upper()}"


class StripeCheckoutMixin(models.Model):
    """Fields shared by everything paid through a Stripe Checkout Session."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente de paiement"
        PAID = "paid", "Payée"
        CANCELLED = "cancelled", "Annulée / expirée"

    reference = models.CharField("référence", max_length=24, unique=True, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    email = models.EmailField(blank=True)
    full_name = models.CharField("nom", max_length=200, blank=True)
    phone = models.CharField("téléphone", max_length=40, blank=True)
    shipping_address = models.JSONField("adresse de livraison", default=dict, blank=True)
    stripe_session_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    REFERENCE_PREFIX = "CMD"

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_reference(self.REFERENCE_PREFIX)
        super().save(*args, **kwargs)

    def mark_paid(self, session: dict) -> bool:
        """Idempotently record a completed Stripe Checkout Session. Returns True on state change."""
        if self.status == self.Status.PAID:
            return False
        details = session.get("customer_details") or {}
        shipping = (session.get("collected_information") or {}).get("shipping_details") or session.get(
            "shipping_details"
        ) or {}
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.email = details.get("email") or self.email
        self.full_name = shipping.get("name") or details.get("name") or self.full_name
        self.phone = details.get("phone") or self.phone
        self.shipping_address = shipping.get("address") or details.get("address") or {}
        self.stripe_payment_intent = session.get("payment_intent") or ""
        self.save()
        return True

    def mark_cancelled(self) -> bool:
        if self.status != self.Status.PENDING:
            return False
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status"])
        return True


class Order(StripeCheckoutMixin):
    total = models.DecimalField("total TTC (€)", max_digits=10, decimal_places=2)
    gold_spot_eur_per_oz = models.DecimalField(
        "cours de l'or appliqué (€/oz)", max_digits=12, decimal_places=4,
        help_text="Cours figé au moment de la commande.",
    )

    class Meta(StripeCheckoutMixin.Meta):
        verbose_name = "commande"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    ring = models.ForeignKey("catalog.Ring", on_delete=models.SET_NULL, null=True)
    ring_name = models.CharField(max_length=120)
    size = models.PositiveSmallIntegerField("taille")
    engraving = models.CharField("gravure", max_length=40, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.DecimalField("prix unitaire TTC", max_digits=10, decimal_places=2)
    weight_g = models.DecimalField("poids (g)", max_digits=6, decimal_places=2)

    class Meta:
        verbose_name = "ligne de commande"

    def __str__(self):
        return f"{self.quantity} × {self.ring_name} (T{self.size})"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
