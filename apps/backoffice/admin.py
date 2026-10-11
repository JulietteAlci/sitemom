from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "due_date", "priority", "assignee", "is_done")
    list_editable = ("is_done",)
    list_filter = ("is_done", "priority", "assignee")
    search_fields = ("title", "notes")
    date_hierarchy = "due_date"

    def save_model(self, request, obj, form, change):
        if obj.is_done and not obj.done_at:
            from django.utils import timezone

            obj.done_at = timezone.now()
        super().save_model(request, obj, form, change)
