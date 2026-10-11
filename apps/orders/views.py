import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.catalog.models import Ring
from apps.pricing.models import GoldPrice
from apps.trialkit.models import TrialKitOrder, normalize_code

from . import payments
from .cart import Cart
from .forms import AddToCartForm, DemoCheckoutForm
from .models import Order, OrderItem

logger = logging.getLogger(__name__)

# Stripe metadata "kind" → model handling the payment.
CHECKOUT_MODELS = {"order": Order, "trial_kit": TrialKitOrder}
# kind → (success URL name, cancel URL name), used by the demo checkout.
CHECKOUT_URLS = {"order": ("orders:success", "orders:cart"), "trial_kit": ("trialkit:success", "trialkit:start")}


PENDING_ORDER_SESSION_KEY = "pending_order_id"


def cart_detail(request):
    cart = Cart(request)
    lines = cart.lines()
    subtotal = Cart.total(lines)
    credit = cart.trial_kit_credit(subtotal)
    total = subtotal - credit.amount if subtotal is not None and credit else subtotal
    return render(
        request,
        "orders/cart.html",
        {"lines": lines, "subtotal": subtotal, "credit": credit, "total": total},
    )


@require_POST
def cart_trial_kit_code(request):
    cart = Cart(request)
    if "remove" in request.POST:
        cart.clear_trial_kit_code()
        return redirect("orders:cart")
    code = normalize_code(request.POST.get("code", ""))
    if not code or TrialKitOrder.find_by_code(code) is None:
        messages.error(request, "Ce code de coffret d'essai est inconnu.")
        return redirect("orders:cart")
    cart.set_trial_kit_code(code)
    return redirect("orders:cart")


def _abandon_previous_checkout(request):
    """A customer starting a new checkout gives up the previous one: expire it so that
    a trial kit code it reserved becomes usable again (and cannot be paid twice)."""
    order = Order.objects.filter(
        pk=request.session.pop(PENDING_ORDER_SESSION_KEY, None), status=Order.Status.PENDING
    ).first()
    if order is None:
        return
    if order.stripe_session_id and not payments.is_demo_session(order.stripe_session_id):
        try:
            stripe.checkout.Session.expire(order.stripe_session_id, api_key=settings.STRIPE_SECRET_KEY)
        except stripe.StripeError:
            logger.warning("Could not expire Stripe session of order %s", order.reference, exc_info=True)
            return  # keep it pending: the session may still be paid
    order.mark_cancelled()


@require_POST
def cart_add(request, slug):
    ring = get_object_or_404(Ring, slug=slug, is_active=True)
    form = AddToCartForm(request.POST, ring=ring)
    if not form.is_valid():
        messages.error(request, "Merci de vérifier les options choisies (métal, pierre, taille, gravure).")
        return redirect(ring)
    data = form.cleaned_data
    Cart(request).add(
        ring,
        size=data["size"],
        engraving=data.get("engraving", ""),
        quantity=data["quantity"] or 1,
        metal=data["metal"],
        stone_id=data.get("stone"),
        comment=data.get("comment", ""),
    )
    messages.success(request, f"« {ring.name} » a été ajouté à votre panier.")
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

    _abandon_previous_checkout(request)
    subtotal = Cart.total(lines)
    credit = cart.trial_kit_credit(subtotal)
    if credit and credit.error:
        messages.error(request, credit.error)
        return redirect("orders:cart")
    discount = credit.amount if credit else Decimal(0)

    with transaction.atomic():
        order = Order.objects.create(
            total=subtotal - discount,
            discount=discount,
            trial_kit=credit.kit if credit else None,
            gold_spot_eur_per_oz=spot.price_per_oz_eur,
        )
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                ring=line.ring,
                ring_name=line.ring.name,
                size=line.size,
                metal=line.metal.name if line.metal else "",
                stone=str(line.stone) if line.stone else "",
                engraving=line.engraving,
                comment=line.comment,
                quantity=line.quantity,
                unit_price=line.unit_price,
                weight_g=line.breakdown.weight_g,
            )
            for line in lines
        )
    items = [
        payments.line_item(
            name=f"{line.ring.name} — {line.description}",
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
            discount_cents=int(discount * 100),
            discount_name=f"Coffret d'essai {credit.kit.credit_code}" if credit else "",
        )
    except (payments.PaymentsNotConfigured, stripe.StripeError):
        logger.exception("Unable to create Stripe session for order %s", order.reference)
        order.mark_cancelled()
        messages.error(request, "Le paiement est momentanément indisponible. Merci de réessayer.")
        return redirect("orders:cart")
    request.session[PENDING_ORDER_SESSION_KEY] = order.pk
    return redirect(session.url, permanent=False)


def checkout_success(request):
    order = Order.objects.filter(stripe_session_id=request.GET.get("session_id", "")).first()
    if order is not None:
        Cart(request).clear()
        request.session.pop(PENDING_ORDER_SESSION_KEY, None)
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


def _find_demo_checkout(session_id):
    for kind, model in CHECKOUT_MODELS.items():
        obj = model.objects.filter(stripe_session_id=session_id).first()
        if obj is not None:
            return kind, obj
    raise Http404


def demo_checkout(request, session_id):
    """Simulated Stripe Checkout page, available in demo mode only. Nothing is charged."""
    if not settings.STRIPE_DEMO_MODE or not payments.is_demo_session(session_id):
        raise Http404
    kind, obj = _find_demo_checkout(session_id)
    success_name, cancel_name = CHECKOUT_URLS[kind]
    expired = timezone.now() - obj.created_at > payments.CHECKOUT_LIFETIME

    if obj.status == obj.Status.PAID:
        return redirect(f"{reverse(success_name)}?session_id={session_id}")
    if obj.status == obj.Status.CANCELLED or expired:
        obj.mark_cancelled()
        messages.error(request, "Cette session de paiement a expiré. Merci de recommencer.")
        return redirect(cancel_name)

    form = DemoCheckoutForm(request.POST or None)
    if request.method == "POST" and "cancel" in request.POST:
        obj.mark_cancelled()
        return redirect(cancel_name)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        # Same shape as a Stripe Checkout Session, handled exactly like the webhook would.
        obj.mark_paid(
            {
                "id": session_id,
                "payment_status": "paid",
                "payment_intent": f"demo_pi_{obj.pk}",
                "customer_details": {"email": data["email"], "name": data["name"], "phone": data["phone"]},
                "collected_information": {
                    "shipping_details": {
                        "name": data["name"],
                        "address": {
                            "line1": data["line1"],
                            "postal_code": data["postal_code"],
                            "city": data["city"],
                            "country": data["country"],
                        },
                    }
                },
            }
        )
        return redirect(f"{reverse(success_name)}?session_id={session_id}")

    if kind == "order":
        lines = [(f"{item.ring_name} — taille {item.size}", item.quantity, item.line_total) for item in obj.items.all()]
        amount, discount = obj.total, obj.discount
    else:
        lines = [(f"Coffret d'essai — {obj.samples.count()} alliances", 1, obj.price)]
        amount, discount = obj.price, 0
    return render(
        request,
        "orders/demo_checkout.html",
        {"obj": obj, "form": form, "lines": lines, "amount": amount, "discount": discount},
    )
