from django import template
from django.db.models import Sum
from django.utils import timezone

from apps.orders.models import Order
from apps.pricing.models import GoldPrice
from apps.trialkit.models import TrialKitOrder

from ..services import build_tasks

register = template.Library()


@register.simple_tag
def dashboard():
    """Key figures for the admin home page."""
    today = timezone.localdate()
    month_start = today.replace(day=1)
    paid_this_month = Order.objects.filter(status=Order.Status.PAID, paid_at__date__gte=month_start)
    return {
        "today_count": len(build_tasks("jour")),
        "week_count": len(build_tasks("semaine")),
        "orders_open": Order.objects.filter(
            status=Order.Status.PAID,
            fulfillment__in=[Order.Fulfillment.TO_MAKE, Order.Fulfillment.IN_PRODUCTION],
        ).count(),
        "kits_to_ship": TrialKitOrder.objects.filter(
            status=TrialKitOrder.Status.PAID, fulfillment=TrialKitOrder.Fulfillment.TO_PREPARE
        ).count(),
        "revenue_month": paid_this_month.aggregate(total=Sum("total"))["total"] or 0,
        "orders_month": paid_this_month.count(),
        "gold": GoldPrice.current(),
    }
