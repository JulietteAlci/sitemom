"""Thin wrapper around Stripe Checkout, shared by ring orders and trial kits."""
import json
import logging
import secrets
from types import SimpleNamespace
from datetime import timedelta

import stripe
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

SHIPPING_COUNTRIES = ["FR", "BE", "LU", "CH", "MC"]
# Stripe's minimum lifetime for a Checkout Session; also how long the gold price is locked.
CHECKOUT_LIFETIME = timedelta(minutes=30)


DEMO_SESSION_PREFIX = "demo_cs_"


def is_demo_session(session_id: str) -> bool:
    return session_id.startswith(DEMO_SESSION_PREFIX)


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


def create_checkout_session(
    *, kind: str, obj, line_items: list[dict], success_url: str, cancel_url: str, discount_cents: int = 0,
    discount_name: str = "",
):
    """Create a Stripe Checkout Session for `obj` (Order or TrialKitOrder) and store its id.

    In demo mode, no call is made to Stripe: the customer is sent to a local page that
    simulates Stripe Checkout (see views.demo_checkout).
    """
    if settings.STRIPE_DEMO_MODE:
        session_id = f"{DEMO_SESSION_PREFIX}{secrets.token_urlsafe(18)}"
        obj.stripe_session_id = session_id
        obj.save(update_fields=["stripe_session_id"])
        return SimpleNamespace(id=session_id, url=reverse("orders:demo_checkout", args=[session_id]))
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentsNotConfigured("STRIPE_SECRET_KEY is not set")
    metadata = {"kind": kind, "object_id": str(obj.pk), "reference": obj.reference}
    extra = {}
    if discount_cents:
        # One-shot coupon: Stripe line items cannot carry negative amounts.
        coupon = stripe.Coupon.create(
            api_key=settings.STRIPE_SECRET_KEY,
            amount_off=discount_cents,
            currency=settings.CURRENCY,
            duration="once",
            max_redemptions=1,
            name=discount_name or "Déduction",
            metadata=metadata,
        )
        extra["discounts"] = [{"coupon": coupon.id}]
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
        **extra,
    )
    obj.stripe_session_id = session.id
    obj.save(update_fields=["stripe_session_id"])
    return session


def refund_payment(payment_intent: str, amount_cents: int, obj) -> str:
    """Refund part of a payment. Returns the refund id (simulated in demo mode)."""
    if settings.STRIPE_DEMO_MODE or payment_intent.startswith("demo_"):
        return f"demo_re_{secrets.token_hex(6)}"
    if not payment_intent:
        raise PaymentsNotConfigured(f"Aucun paiement Stripe associé à {obj.reference}.")
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentsNotConfigured("STRIPE_SECRET_KEY is not set")
    result = stripe.Refund.create(
        api_key=settings.STRIPE_SECRET_KEY,
        payment_intent=payment_intent,
        amount=amount_cents,
        metadata={"reference": obj.reference},
    )
    return result.id


def parse_webhook(payload: bytes, signature: str) -> dict:
    """Verify the Stripe signature and return the event as a plain dict.

    Raises ValueError or stripe.SignatureVerificationError on invalid input.
    """
    stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    return json.loads(payload)
