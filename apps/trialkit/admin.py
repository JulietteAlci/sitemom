from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.orders import payments

from . import services
from .models import SampleRing, TrialKitOrder


@admin.register(SampleRing)
class SampleRingAdmin(admin.ModelAdmin):
    list_display = ("reference", "ring", "size", "quantity", "in_use", "available", "is_active")
    list_editable = ("quantity", "is_active")
    list_filter = ("is_active",)
    search_fields = ("reference", "ring__name", "ring__sku")
    autocomplete_fields = ("ring",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("ring").with_availability()

    @admin.display(description="en circulation", ordering="in_use")
    def in_use(self, obj):
        return obj.in_use

    @admin.display(description="disponibles", ordering="available")
    def available(self, obj):
        if obj.available == 0:
            return format_html('<strong style="color:#b4372e">0 — indisponible</strong>')
        return obj.available


def _run(modeladmin, request, queryset, transition, done_message):
    done = 0
    for kit in queryset:
        try:
            transition(kit)
            done += 1
        except (services.KitTransitionError, payments.PaymentsNotConfigured) as exc:
            modeladmin.message_user(request, str(exc), messages.WARNING)
        except Exception as exc:  # Stripe errors
            modeladmin.message_user(request, f"{kit.reference} : {exc}", messages.ERROR)
    if done:
        modeladmin.message_user(request, done_message.format(count=done), messages.SUCCESS)


@admin.register(TrialKitOrder)
class TrialKitOrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "created_at", "status", "fulfillment", "full_name", "sample_references",
        "return_deadline_display", "reminders_sent", "refund_display",
    )
    list_filter = ("status", "fulfillment", "include_sizer")
    search_fields = ("reference", "credit_code", "email", "full_name", "samples__reference", "tracking_number")
    filter_horizontal = ("samples",)
    actions = ["action_ship", "action_delivered", "action_received", "action_refund", "action_remind"]
    readonly_fields = (
        "reference", "documents", "status", "fulfillment", "price", "credit_amount", "refund_amount", "credit_code",
        "redeemed_order", "shipping_address", "email", "full_name", "phone", "created_at", "paid_at", "shipped_at",
        "delivered_at", "return_deadline_display", "returned_at", "reminders_sent", "last_reminder_at",
        "refunded_at", "refund_id", "stripe_session_id", "stripe_payment_intent",
    )
    fieldsets = (
        (None, {"fields": ("reference", "documents", "status", "fulfillment")}),
        ("Contenu du coffret", {"fields": ("samples", "include_sizer", "message")}),
        ("Client", {"fields": ("full_name", "email", "phone", "shipping_address")}),
        (
            "Logistique",
            {
                "fields": (
                    "tracking_number", "shipped_at", "delivered_at", "return_deadline_display", "returned_at",
                    "reminders_sent", "last_reminder_at",
                )
            },
        ),
        (
            "Paiement",
            {
                "fields": (
                    "price", "credit_amount", "credit_code", "redeemed_order", "refund_amount", "refunded_at",
                    "refund_id", "created_at", "paid_at", "stripe_session_id", "stripe_payment_intent",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("samples")

    @admin.display(description="factices")
    def sample_references(self, obj):
        return ", ".join(sample.reference for sample in obj.samples.all())

    @admin.display(description="retour attendu le")
    def return_deadline_display(self, obj):
        deadline = obj.return_deadline
        if not deadline:
            return "—"
        if obj.is_out and obj.is_return_late:
            return format_html('<strong style="color:#b4372e">{} (en retard)</strong>', deadline.strftime("%d/%m/%Y"))
        return deadline.strftime("%d/%m/%Y")

    @admin.display(description="remboursement")
    def refund_display(self, obj):
        if obj.refunded_at:
            return f"{obj.refund_amount} € le {obj.refunded_at:%d/%m}"
        return "à faire" if obj.can_be_refunded else "—"

    @admin.display(description="commande ayant utilisé le code")
    def redeemed_order(self, obj):
        return obj.redeemed_order or "—"

    @admin.display(description="documents")
    def documents(self, obj):
        if not obj.pk:
            return "—"
        links = [
            ("Bon d'envoi", reverse("backoffice:kit_packing_slip", args=[obj.pk])),
            ("Étiquette retour", reverse("backoffice:kit_return_label", args=[obj.pk])),
        ]
        return format_html_join(" · ", '<a href="{1}" target="_blank">{0}</a>', links)

    @admin.action(description="Marquer expédié (envoie l'e-mail d'expédition)")
    def action_ship(self, request, queryset):
        _run(self, request, queryset, services.ship, "{count} coffret(s) expédié(s), e-mail envoyé.")

    @admin.action(description="Marquer livré")
    def action_delivered(self, request, queryset):
        _run(self, request, queryset, services.mark_delivered, "{count} coffret(s) marqué(s) livré(s).")

    @admin.action(description="Marquer reçu en retour (à contrôler)")
    def action_received(self, request, queryset):
        _run(self, request, queryset, services.receive, "{count} coffret(s) reçu(s).")

    @admin.action(description="Valider le contrôle et rembourser")
    def action_refund(self, request, queryset):
        _run(self, request, queryset, services.refund, "{count} coffret(s) remboursé(s), e-mail envoyé.")

    @admin.action(description="Envoyer une relance maintenant")
    def action_remind(self, request, queryset):
        def remind(kit):
            if not kit.is_out:
                raise services.KitTransitionError(f"Le coffret {kit.reference} n'est pas chez le client.")
            services.send_reminder(kit)

        _run(self, request, queryset, remind, "{count} relance(s) envoyée(s).")
