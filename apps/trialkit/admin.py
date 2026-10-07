from django.contrib import admin

from .models import TrialKitOrder


@admin.register(TrialKitOrder)
class TrialKitOrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "created_at", "status", "fulfillment", "full_name", "ring_count", "deposit")
    list_filter = ("status", "fulfillment", "include_sizer")
    list_editable = ("fulfillment",)
    search_fields = ("reference", "email", "full_name")
    filter_horizontal = ("rings",)
    readonly_fields = (
        "reference",
        "deposit",
        "stripe_session_id",
        "stripe_payment_intent",
        "created_at",
        "paid_at",
        "shipping_address",
    )

    @admin.display(description="Nb alliances")
    def ring_count(self, obj):
        return obj.rings.count()
