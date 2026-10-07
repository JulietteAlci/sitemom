from django.contrib import admin

from .models import TrialKitOrder


@admin.register(TrialKitOrder)
class TrialKitOrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "credit_code", "created_at", "status", "fulfillment", "full_name", "ring_count", "price")
    list_filter = ("status", "fulfillment", "include_sizer")
    list_editable = ("fulfillment",)
    search_fields = ("reference", "credit_code", "email", "full_name")
    filter_horizontal = ("rings",)
    readonly_fields = (
        "reference",
        "price",
        "credit_code",
        "redeemed_order",
        "stripe_session_id",
        "stripe_payment_intent",
        "created_at",
        "paid_at",
        "shipping_address",
    )

    @admin.display(description="Commande ayant utilisé le code")
    def redeemed_order(self, obj):
        return obj.redeemed_order or "—"

    @admin.display(description="Nb alliances")
    def ring_count(self, obj):
        return obj.rings.count()
