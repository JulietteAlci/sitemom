"""Build the team's to-do list: manual tasks plus tasks derived from shop activity.

Automatic tasks disappear by themselves once the underlying record moves on
(kit shipped, order shipped, gold price refreshed…).
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order
from apps.pricing.models import GoldPrice
from apps.trialkit.models import TrialKitOrder

from .models import Task

PERIODS = {"jour": "Aujourd'hui", "semaine": "7 prochains jours"}


@dataclass
class TaskItem:
    kind: str  # category label shown as a badge
    title: str
    due: date
    detail: str = ""
    url: str = ""
    high_priority: bool = False
    actions: list[tuple[str, str, int]] = field(default_factory=list)  # (label, action, pk)

    @property
    def overdue(self) -> bool:
        return self.due < timezone.localdate()

    @property
    def due_today(self) -> bool:
        return self.due == timezone.localdate()


def period_end(period: str, today: date | None = None) -> date:
    today = today or timezone.localdate()
    if period == "semaine":
        return today + timedelta(days=6)  # the next 7 days, whatever the weekday
    return today


def _join(*parts) -> str:
    return " · ".join(part for part in parts if part)


def _admin_url(obj) -> str:
    meta = obj._meta
    return reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[obj.pk])


def _manual_tasks(end: date):
    for task in Task.objects.filter(is_done=False, due_date__lte=end).select_related("assignee"):
        yield TaskItem(
            kind="Tâche",
            title=task.title,
            due=task.due_date,
            detail=_join(task.notes, str(task.assignee) if task.assignee else ""),
            url=_admin_url(task),
            high_priority=task.priority == Task.Priority.HIGH,
            actions=[("Terminer", "task_done", task.pk)],
        )


def _trial_kit_tasks():
    to_ship = TrialKitOrder.objects.filter(
        status=TrialKitOrder.Status.PAID, fulfillment=TrialKitOrder.Fulfillment.TO_PREPARE
    ).prefetch_related("rings")
    for kit in to_ship:
        yield TaskItem(
            kind="Coffret",
            title=f"Préparer et expédier le coffret {kit.reference}",
            due=timezone.localdate(kit.paid_at) + timedelta(days=1),
            detail=_join(kit.full_name or kit.email, f"{kit.rings.count()} alliances", "baguier" if kit.include_sizer else ""),
            url=_admin_url(kit),
            high_priority=True,
            actions=[("Marquer expédié", "kit_shipped", kit.pk)],
        )
    awaiting_return = TrialKitOrder.objects.filter(
        fulfillment=TrialKitOrder.Fulfillment.SHIPPED, shipped_at__isnull=False
    )
    for kit in awaiting_return:
        yield TaskItem(
            kind="Coffret",
            title=f"Vérifier le retour du coffret {kit.reference}",
            due=timezone.localdate(kit.shipped_at) + timedelta(days=settings.TRIAL_KIT_RETURN_DAYS),
            detail=_join(f"Expédié le {timezone.localdate(kit.shipped_at):%d/%m}",
                         f"relancer {kit.full_name or kit.email or 'le client'} si besoin"),
            url=_admin_url(kit),
            actions=[("Marquer retourné", "kit_returned", kit.pk)],
        )


def _order_tasks():
    open_orders = Order.objects.filter(
        status=Order.Status.PAID, fulfillment__in=[Order.Fulfillment.TO_MAKE, Order.Fulfillment.IN_PRODUCTION]
    ).prefetch_related("items__ring")
    for order in open_orders:
        items = ", ".join(f"{item.ring_name} T{item.size}" for item in order.items.all())
        if order.fulfillment == Order.Fulfillment.TO_MAKE:
            yield TaskItem(
                kind="Commande",
                title=f"Lancer la fabrication de la commande {order.reference}",
                due=timezone.localdate(order.paid_at),
                detail=_join(order.full_name or order.email, items),
                url=_admin_url(order),
                high_priority=True,
                actions=[("Passer en fabrication", "order_production", order.pk)],
            )
        else:
            yield TaskItem(
                kind="Commande",
                title=f"Expédier la commande {order.reference}",
                due=order.ship_by,
                detail=_join(order.full_name or order.email, f"livraison promise le {order.delivery_deadline:%d/%m/%Y}"),
                url=_admin_url(order),
                high_priority=True,
                actions=[("Marquer expédiée", "order_shipped", order.pk)],
            )


def _gold_price_tasks():
    quote = GoldPrice.current()
    if quote is None or not quote.is_fresh:
        yield TaskItem(
            kind="Cours de l'or",
            title="Mettre à jour le cours de l'or (paiements suspendus)",
            due=timezone.localdate(),
            detail="Dernier cours : " + (f"{quote.fetched_at:%d/%m/%Y %H:%M}" if quote else "aucun"),
            url=reverse("admin:pricing_goldprice_changelist"),
            high_priority=True,
            actions=[("Actualiser", "gold_refresh", 0)],
        )


def build_tasks(period: str = "jour") -> list[TaskItem]:
    """Tasks due by the end of the period, overdue ones included, most urgent first."""
    end = period_end(period)
    items = [
        *_manual_tasks(end),
        *(item for item in _trial_kit_tasks() if item.due <= end),
        *(item for item in _order_tasks() if item.due <= end),
        *_gold_price_tasks(),
    ]
    return sorted(items, key=lambda item: (item.due, not item.high_priority, item.title))
