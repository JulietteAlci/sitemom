from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("ring", "ring_name", "size", "engraving", "quantity", "unit_price", "weight_g")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "created_at", "status", "full_name", "email", "total", "discount")
    list_filter = ("status",)
    search_fields = ("reference", "email", "full_name", "stripe_session_id")
    readonly_fields = (
        "reference",
        "total",
        "discount",
        "trial_kit",
        "gold_spot_eur_per_oz",
        "stripe_session_id",
        "stripe_payment_intent",
        "created_at",
        "paid_at",
        "shipping_address",
    )
    inlines = [OrderItemInline]
