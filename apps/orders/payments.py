"""Thin wrapper around Stripe Checkout, shared by ring orders and trial kits."""
import json
import logging
from datetime import timedelta

import stripe
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SHIPPING_COUNTRIES = ["FR", "BE", "LU", "CH", "MC"]
# Stripe's minimum lifetime for a Checkout Session; also how long the gold price is locked.
CHECKOUT_LIFETIME = timedelta(minutes=30)


class PaymentsNotConfigured(Exception):
    pass


def line_item(name: str, amount_cents: int, quantity: int = 1, description: str = "") -> dict:
    product_data = {"name": name}
    if description:
        product_data["description"] = description
    return {
        "quantity": quantity,
        "price_data": {
            "currency": settings.CURRENCY,
            "unit_amount": amount_cents,
            "product_data": product_data,
        },
    }


def create_checkout_session(*, kind: str, obj, line_items: list[dict], success_url: str, cancel_url: str):
    """Create a Stripe Checkout Session for `obj` (Order or TrialKitOrder) and store its id."""
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentsNotConfigured("STRIPE_SECRET_KEY is not set")
    metadata = {"kind": kind, "object_id": str(obj.pk), "reference": obj.reference}
    session = stripe.checkout.Session.create(
        api_key=settings.STRIPE_SECRET_KEY,
        mode="payment",
        line_items=line_items,
        client_reference_id=obj.reference,
        metadata=metadata,
        payment_intent_data={"metadata": metadata},
        shipping_address_collection={"allowed_countries": SHIPPING_COUNTRIES},
        phone_number_collection={"enabled": True},
        locale="fr",
        expires_at=int((timezone.now() + CHECKOUT_LIFETIME).timestamp()),
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
    )
    obj.stripe_session_id = session.id
    obj.save(update_fields=["stripe_session_id"])
    return session


def parse_webhook(payload: bytes, signature: str) -> dict:
    """Verify the Stripe signature and return the event as a plain dict.

    Raises ValueError or stripe.SignatureVerificationError on invalid input.
    """
    stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    return json.loads(payload)
