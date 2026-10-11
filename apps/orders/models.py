import secrets
from datetime import timedelta

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
    status = models.CharField(
        "statut", max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    email = models.EmailField(blank=True)
    full_name = models.CharField("nom", max_length=200, blank=True)
    phone = models.CharField("téléphone", max_length=40, blank=True)
    shipping_address = models.JSONField("adresse de livraison", default=dict, blank=True)
    stripe_session_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    paid_at = models.DateTimeField("payée le", null=True, blank=True)

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
    class Fulfillment(models.TextChoices):
        TO_MAKE = "to_make", "À fabriquer"
        IN_PRODUCTION = "in_production", "En fabrication"
        SHIPPED = "shipped", "Expédiée"
        DELIVERED = "delivered", "Livrée"

    # Days between shipping and delivery, used to compute the "ship by" date.
    SHIPPING_DAYS = 2
    DEFAULT_LEAD_TIME_DAYS = 21

    fulfillment = models.CharField(
        "fabrication", max_length=14, choices=Fulfillment.choices, default=Fulfillment.TO_MAKE, db_index=True
    )
    shipped_at = models.DateTimeField("expédiée le", null=True, blank=True)
    total = models.DecimalField("total payé TTC (€)", max_digits=10, decimal_places=2)
    discount = models.DecimalField("déduction coffret (€)", max_digits=8, decimal_places=2, default=0)
    trial_kit = models.ForeignKey(
        "trialkit.TrialKitOrder", on_delete=models.PROTECT, null=True, blank=True, related_name="orders",
        verbose_name="coffret d'essai déduit",
    )
    gold_spot_eur_per_oz = models.DecimalField(
        "cours de l'or appliqué (€/oz)", max_digits=12, decimal_places=4,
        help_text="Cours figé au moment de la commande.",
    )

    class Meta(StripeCheckoutMixin.Meta):
        verbose_name = "commande"

    @property
    def subtotal(self):
        return self.total + self.discount

    @property
    def delivery_deadline(self):
        """Latest delivery date promised on the product pages (payment date + longest lead time)."""
        if not self.paid_at:
            return None
        lead_times = [item.ring.lead_time_days for item in self.items.all() if item.ring]
        days = max(lead_times, default=self.DEFAULT_LEAD_TIME_DAYS)
        return timezone.localdate(self.paid_at) + timedelta(days=days)

    @property
    def ship_by(self):
        deadline = self.delivery_deadline
        return deadline - timedelta(days=self.SHIPPING_DAYS) if deadline else None

    def mark_paid(self, session: dict) -> bool:
        changed = super().mark_paid(session)
        if changed and self.trial_kit_id:
            kit = self.trial_kit
            kit.fulfillment = kit.Fulfillment.CONVERTED
            kit.save(update_fields=["fulfillment"])
        return changed


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    ring = models.ForeignKey("catalog.Ring", on_delete=models.SET_NULL, null=True)
    ring_name = models.CharField(max_length=120)
    size = models.PositiveSmallIntegerField("taille")
    metal = models.CharField("métal", max_length=40, blank=True)
    stone = models.CharField("pierre", max_length=120, blank=True)
    engraving = models.CharField("gravure", max_length=100, blank=True)
    comment = models.TextField("commentaire client", blank=True)
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
