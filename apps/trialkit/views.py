import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.catalog.models import Ring
from apps.orders import payments

from .forms import TrialKitForm
from . import services
from .models import TrialKitOrder, kit_size_label

logger = logging.getLogger(__name__)


def cents(value: int) -> Decimal:
    return Decimal(value) / 100


def trial_kit(request):
    form = TrialKitForm(request.POST or None, initial={"samples": request.GET.getlist("factice")})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            kit = TrialKitOrder.objects.create(
                price=cents(settings.TRIAL_KIT_PRICE_CENTS),
                credit_amount=cents(settings.TRIAL_KIT_CREDIT_CENTS),
                refund_amount=cents(settings.TRIAL_KIT_REFUND_CENTS),
                include_sizer=form.cleaned_data["include_sizer"],
                message=form.cleaned_data["message"],
            )
            kit.samples.set(form.cleaned_data["samples"])
        names = ", ".join(sample.ring.name for sample in form.cleaned_data["samples"])
        try:
            session = payments.create_checkout_session(
                kind="trial_kit",
                obj=kit,
                line_items=[
                    payments.line_item(
                        name=f"Coffret d'essai — {kit.samples.count()} alliances",
                        amount_cents=settings.TRIAL_KIT_PRICE_CENTS,
                        description=(
                            f"{names}. {kit.refund_amount:.0f} € remboursés au retour du coffret, "
                            f"{kit.credit_amount:.0f} € déduits de votre commande d'alliances."
                        ),
                    )
                ],
                success_url=request.build_absolute_uri(reverse("trialkit:success")),
                cancel_url=request.build_absolute_uri(reverse("trialkit:start")),
            )
        except (payments.PaymentsNotConfigured, stripe.StripeError):
            logger.exception("Unable to create Stripe session for trial kit %s", kit.reference)
            kit.mark_cancelled()
            messages.error(request, "Le paiement est momentanément indisponible. Merci de réessayer.")
        else:
            return redirect(session.url, permanent=False)

    samples = list(form.fields["samples"].queryset)
    selected = {str(pk) for pk in (form["samples"].value() or [])}
    groups = [
        (label, [sample for sample in samples if sample.ring.gender == gender])
        for gender, label in Ring.Gender.choices
    ]
    return render(
        request,
        "trialkit/trial_kit.html",
        {
            "form": form,
            "groups": [(label, items) for label, items in groups if items],
            "selected": selected,
            "kit_min": settings.TRIAL_KIT_MIN,
            "kit_max": settings.TRIAL_KIT_MAX,
            "kit_size": kit_size_label(),
            "price": cents(settings.TRIAL_KIT_PRICE_CENTS),
            "credit": cents(settings.TRIAL_KIT_CREDIT_CENTS),
            "refund": cents(settings.TRIAL_KIT_REFUND_CENTS),
            "return_days": settings.TRIAL_KIT_RETURN_DAYS,
        },
    )


def trial_kit_success(request):
    kit = TrialKitOrder.objects.filter(stripe_session_id=request.GET.get("session_id", "")).first()
    return render(request, "trialkit/success.html", {"kit": kit})


# --- Printable documents -------------------------------------------------------------------

def _print_context(kit):
    return {
        "kit": kit,
        "samples": list(kit.samples.select_related("ring")),
        "address": services.format_address(kit),
        "shop_address": settings.SHOP_ADDRESS,
        "return_days": settings.TRIAL_KIT_RETURN_DAYS,
        "return_label_url": services.return_label_url(kit),
        "SITE_NAME": settings.SITE_NAME,
    }


def packing_slip(request, pk):
    """Bon d'envoi (staff only): delivery note + picking list with the dummies' references."""
    kit = get_object_or_404(TrialKitOrder, pk=pk, status=TrialKitOrder.Status.PAID)
    return render(request, "trialkit/print/packing_slip.html", _print_context(kit))


def return_label_staff(request, pk):
    kit = get_object_or_404(TrialKitOrder, pk=pk, status=TrialKitOrder.Status.PAID)
    return render(request, "trialkit/print/return_label.html", _print_context(kit))


def return_label(request, token):
    """Return label for the customer, reached through the signed link sent by e-mail."""
    kit = services.kit_from_token(token)
    if kit is None or kit.status != TrialKitOrder.Status.PAID:
        raise Http404
    return render(request, "trialkit/print/return_label.html", _print_context(kit))
