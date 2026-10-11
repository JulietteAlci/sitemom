from django.contrib import admin

from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("sent_at", "kind", "reference", "to", "subject", "status")
    list_filter = ("kind", "status")
    search_fields = ("reference", "to", "subject")
    readonly_fields = ("sent_at", "kind", "reference", "to", "subject", "body", "status", "error")

    def has_add_permission(self, request):
        return False
