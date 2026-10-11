from django.conf import settings
from django.db import models
from django.utils import timezone


class Task(models.Model):
    """A manual to-do item for the shop team (automatic tasks are computed, see services.py)."""

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normale"
        HIGH = "high", "Haute"

    title = models.CharField("tâche", max_length=200)
    notes = models.TextField("notes", blank=True)
    due_date = models.DateField("échéance", default=timezone.localdate)
    priority = models.CharField("priorité", max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="assignée à"
    )
    is_done = models.BooleanField("terminée", default=False)
    done_at = models.DateTimeField("terminée le", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_done", "due_date", "-priority", "pk"]
        verbose_name = "tâche"

    def __str__(self):
        return self.title

    def mark_done(self):
        self.is_done = True
        self.done_at = timezone.now()
        self.save(update_fields=["is_done", "done_at"])
