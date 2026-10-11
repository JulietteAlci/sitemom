import stripe
from django import forms
from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.orders.models import Order
from apps.pricing.providers import GoldPriceUnavailable
from apps.pricing.services import SuspiciousGoldPrice, refresh_gold_price
from apps.orders.payments import PaymentsNotConfigured
from apps.trialkit import services as kit_services
from apps.trialkit.models import TrialKitOrder

from .models import Task
from .services import PERIODS, build_tasks, period_end


class QuickTaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "due_date", "priority"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Nouvelle tâche…", "autocomplete": "off"}),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


def task_list(request):
    period = request.GET.get("periode", "jour")
    if period not in PERIODS:
        period = "jour"
    form = QuickTaskForm(request.POST or None, initial={"due_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tâche ajoutée.")
        return redirect(f"{reverse('backoffice:tasks')}?periode={period}")
    tasks = build_tasks(period)
    context = {
        **admin.site.each_context(request),
        "title": f"Tâches — {PERIODS[period].lower()}",
        "period": period,
        "periods": PERIODS,
        "tasks": tasks,
        "overdue_count": sum(task.overdue for task in tasks),
        "end": period_end(period),
        "form": form,
    }
    return render(request, "backoffice/task_list.html", context)


KIT_TRANSITIONS = {
    "kit_shipped": kit_services.ship,
    "kit_delivered": kit_services.mark_delivered,
    "kit_received": kit_services.receive,
    "kit_refund": kit_services.refund,
}


def _set(obj, **fields):
    for name, value in fields.items():
        setattr(obj, name, value)
    obj.save(update_fields=list(fields))


@require_POST
def task_action(request):
    action, pk = request.POST.get("action"), request.POST.get("pk")
    now = timezone.now()
    if action == "task_done":
        get_object_or_404(Task, pk=pk).mark_done()
    elif action in KIT_TRANSITIONS:
        kit = get_object_or_404(TrialKitOrder, pk=pk)
        try:
            KIT_TRANSITIONS[action](kit)
        except (kit_services.KitTransitionError, PaymentsNotConfigured, stripe.StripeError) as exc:
            messages.error(request, str(exc))
            return _back(request)
    elif action == "kit_reminders":
        sent = kit_services.send_due_reminders()
        messages.success(request, f"{sent} relance{'s' if sent > 1 else ''} envoyée{'s' if sent > 1 else ''}.")
        return _back(request)
    elif action == "order_production":
        _set(get_object_or_404(Order, pk=pk), fulfillment=Order.Fulfillment.IN_PRODUCTION)
    elif action == "order_shipped":
        _set(get_object_or_404(Order, pk=pk), fulfillment=Order.Fulfillment.SHIPPED, shipped_at=now)
    elif action == "gold_refresh":
        try:
            refresh_gold_price()
        except (GoldPriceUnavailable, SuspiciousGoldPrice) as exc:
            messages.error(request, f"Cours non mis à jour : {exc}")
            return _back(request)
    else:
        messages.error(request, "Action inconnue.")
        return _back(request)
    messages.success(request, "C'est noté !")
    return _back(request)


def _back(request):
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = reverse("backoffice:tasks")
    return redirect(target)
