import logging

import stripe
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.catalog.models import Ring
from apps.pricing.models import GoldPrice
from apps.trialkit.models import TrialKitOrder

from . import payments
from .cart import Cart
from .forms import AddToCartForm
from .models import Order, OrderItem

logger = logging.getLogger(__name__)

# Stripe metadata "kind" → model handling the payment.
CHECKOUT_MODELS = {"order": Order, "trial_kit": TrialKitOrder}


def cart_detail(request):
    cart = Cart(request)
    lines = cart.lines()
    return render(request, "orders/cart.html", {"lines": lines, "total": Cart.total(lines)})


@require_POST
def cart_add(request, slug):
    ring = get_object_or_404(Ring, slug=slug, is_active=True)
    form = AddToCartForm(request.POST, ring=ring)
    if not form.is_valid():
        messages.error(request, "Merci de vérifier la taille et la gravure choisies.")
        return redirect(ring)
    Cart(request).add(
        ring,
        size=form.cleaned_data["size"],
        engraving=form.cleaned_data.get("engraving", ""),
        quantity=form.cleaned_data["quantity"],
    )
    messages.success(request, f"« {ring.name} » a été ajoutée à votre panier.")
    return redirect("orders:cart")


@require_POST
def cart_remove(request, line_id):
    Cart(request).remove(line_id)
    return redirect("orders:cart")


@require_POST
def checkout(request):
    cart = Cart(request)
    spot = GoldPrice.current()
    if spot is None or not spot.is_fresh:
        messages.error(
            request,
            "Le cours de l'or est momentanément indisponible : les commandes reprendront dans quelques instants.",
        )
        return redirect("orders:cart")
    lines = cart.lines(spot)
    if not lines:
        return redirect("orders:cart")

    with transaction.atomic():
        order = Order.objects.create(total=Cart.total(lines), gold_spot_eur_per_oz=spot.price_per_oz_eur)
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                ring=line.ring,
                ring_name=line.ring.name,
                size=line.size,
                engraving=line.engraving,
                quantity=line.quantity,
                unit_price=line.unit_price,
                weight_g=line.breakdown.weight_g,
            )
            for line in lines
        )
    items = [
        payments.line_item(
            name=f"{line.ring.name} — taille {line.size}",
            amount_cents=line.breakdown.amount_cents,
            quantity=line.quantity,
            description=f"Gravure : {line.engraving}" if line.engraving else "",
        )
        for line in lines
    ]
    try:
        session = payments.create_checkout_session(
            kind="order",
            obj=order,
            line_items=items,
            success_url=request.build_absolute_uri(reverse("orders:success")),
            cancel_url=request.build_absolute_uri(reverse("orders:cart")),
        )
    except (payments.PaymentsNotConfigured, stripe.StripeError):
        logger.exception("Unable to create Stripe session for order %s", order.reference)
        order.mark_cancelled()
        messages.error(request, "Le paiement est momentanément indisponible. Merci de réessayer.")
        return redirect("orders:cart")
    return redirect(session.url, permanent=False)


def checkout_success(request):
    order = Order.objects.filter(stripe_session_id=request.GET.get("session_id", "")).first()
    if order is not None:
        Cart(request).clear()
    return render(request, "orders/success.html", {"order": order})


@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        event = payments.parse_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponseBadRequest("invalid payload")

    event_type = event.get("type", "")
    session = (event.get("data") or {}).get("object") or {}
    metadata = session.get("metadata") or {}
    model = CHECKOUT_MODELS.get(metadata.get("kind"))
    if model is None or event_type not in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
    }:
        return HttpResponse(status=200)

    obj = model.objects.filter(pk=metadata.get("object_id"), stripe_session_id=session.get("id")).first()
    if obj is None:
        logger.warning("Stripe webhook for unknown %s %s", metadata.get("kind"), metadata.get("object_id"))
        return HttpResponse(status=200)

    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        if session.get("payment_status") == "paid":
            obj.mark_paid(session)
    else:
        obj.mark_cancelled()
    return HttpResponse(status=200)
