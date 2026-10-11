"""Trial kit lifecycle: paid → shipped → delivered → received → checked & refunded.

Each step updates the kit and e-mails the customer. Called from the admin, the task list
and the `send_kit_reminders` command.
"""
from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from apps.core.emails import send_email
from apps.orders import payments

from .models import TrialKitOrder

RETURN_LABEL_SALT = "trialkit.return-label"
COUNTRY_NAMES = {"FR": "France", "BE": "Belgique", "LU": "Luxembourg", "CH": "Suisse", "MC": "Monaco"}


class KitTransitionError(Exception):
    pass


def format_address(kit: TrialKitOrder) -> str:
    address = kit.shipping_address or {}
    lines = [
        kit.full_name,
        address.get("line1", ""),
        address.get("line2", ""),
        " ".join(part for part in (address.get("postal_code", ""), address.get("city", "")) if part),
        COUNTRY_NAMES.get(address.get("country", ""), address.get("country", "")),
    ]
    return "\n".join(line for line in lines if line)


def return_label_url(kit: TrialKitOrder) -> str:
    token = signing.dumps(kit.pk, salt=RETURN_LABEL_SALT)
    return settings.SITE_URL + reverse("trialkit:return_label", args=[token])


def kit_from_token(token: str) -> TrialKitOrder | None:
    try:
        pk = signing.loads(token, salt=RETURN_LABEL_SALT)
    except signing.BadSignature:
        return None
    return TrialKitOrder.objects.filter(pk=pk).first()


def _context(kit: TrialKitOrder, **extra) -> dict:
    return {
        "kit": kit,
        "rings": list(kit.samples.select_related("ring")),
        "address": format_address(kit),
        "return_days": settings.TRIAL_KIT_RETURN_DAYS,
        "return_label_url": return_label_url(kit),
        **extra,
    }


def send_confirmation(kit: TrialKitOrder):
    return send_email("kit_confirmation", kit.email, _context(kit), kit.reference)


def ship(kit: TrialKitOrder, tracking_number: str = ""):
    if kit.status != kit.Status.PAID or kit.fulfillment != kit.Fulfillment.TO_PREPARE:
        raise KitTransitionError(f"Le coffret {kit.reference} n'est pas à préparer.")
    kit.fulfillment = kit.Fulfillment.SHIPPED
    kit.shipped_at = timezone.now()
    if tracking_number:
        kit.tracking_number = tracking_number
    kit.save(update_fields=["fulfillment", "shipped_at", "tracking_number"])
    send_email("kit_shipped", kit.email, _context(kit), kit.reference)


def mark_delivered(kit: TrialKitOrder, when=None):
    if kit.fulfillment != kit.Fulfillment.SHIPPED:
        raise KitTransitionError(f"Le coffret {kit.reference} n'est pas en cours de livraison.")
    kit.fulfillment = kit.Fulfillment.DELIVERED
    kit.delivered_at = when or timezone.now()
    kit.save(update_fields=["fulfillment", "delivered_at"])


def receive(kit: TrialKitOrder):
    if not kit.is_out:
        raise KitTransitionError(f"Le coffret {kit.reference} n'est pas chez le client.")
    kit.fulfillment = kit.Fulfillment.RETURNED
    kit.returned_at = timezone.now()
    kit.save(update_fields=["fulfillment", "returned_at"])


def refund(kit: TrialKitOrder):
    """The team checked the returned kit: refund the refundable part and tell the customer."""
    if not kit.can_be_refunded:
        raise KitTransitionError(f"Le coffret {kit.reference} doit être reçu (et pas déjà remboursé).")
    if kit.refund_amount > 0:
        kit.refund_id = payments.refund_payment(kit.stripe_payment_intent, int(kit.refund_amount * 100), kit)
    kit.fulfillment = kit.Fulfillment.REFUNDED
    kit.refunded_at = timezone.now()
    kit.save(update_fields=["refund_id", "fulfillment", "refunded_at"])
    if kit.refund_amount > 0:
        send_email("kit_refunded", kit.email, _context(kit), kit.reference)


def send_reminder(kit: TrialKitOrder):
    late = bool(kit.return_deadline and timezone.localdate() > kit.return_deadline)
    send_email("kit_reminder", kit.email, _context(kit, late=late), kit.reference)
    kit.reminders_sent += 1
    kit.last_reminder_at = timezone.now()
    kit.save(update_fields=["reminders_sent", "last_reminder_at"])


def kits_needing_reminder():
    out = TrialKitOrder.objects.filter(
        fulfillment__in=[TrialKitOrder.Fulfillment.SHIPPED, TrialKitOrder.Fulfillment.DELIVERED]
    )
    return [kit for kit in out if kit.reminder_due]


def send_due_reminders() -> int:
    kits = kits_needing_reminder()
    for kit in kits:
        send_reminder(kit)
    return len(kits)
