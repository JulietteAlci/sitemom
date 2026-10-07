import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.catalog.models import Ring
from apps.orders import payments

from .forms import TrialKitForm
from .models import TrialKitOrder

logger = logging.getLogger(__name__)


def trial_kit(request):
    form = TrialKitForm(request.POST or None, initial={"rings": request.GET.getlist("alliance")})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            kit = TrialKitOrder.objects.create(
                deposit=Decimal(settings.TRIAL_KIT_DEPOSIT_CENTS) / 100,
                include_sizer=form.cleaned_data["include_sizer"],
                message=form.cleaned_data["message"],
            )
            kit.rings.set(form.cleaned_data["rings"])
        try:
            session = payments.create_checkout_session(
                kind="trial_kit",
                obj=kit,
                line_items=[
                    payments.line_item(
                        name=f"Coffret d'essai — {kit.rings.count()} alliances",
                        amount_cents=settings.TRIAL_KIT_DEPOSIT_CENTS,
                        description="Caution remboursée au retour du coffret. Livraison et retour offerts.",
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

    rings = form.fields["rings"].queryset
    selected = {str(pk) for pk in (form["rings"].value() or [])}
    groups = [
        (label, [ring for ring in rings if ring.gender == gender])
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
            "deposit": Decimal(settings.TRIAL_KIT_DEPOSIT_CENTS) / 100,
        },
    )


def trial_kit_success(request):
    kit = TrialKitOrder.objects.filter(stripe_session_id=request.GET.get("session_id", "")).first()
    return render(request, "trialkit/success.html", {"kit": kit})
