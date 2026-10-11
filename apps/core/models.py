from django.db import models


class EmailLog(models.Model):
    """Every transactional e-mail sent to a customer (visible in the admin)."""

    class Status(models.TextChoices):
        SENT = "sent", "Envoyé"
        FAILED = "failed", "Échec"

    kind = models.CharField("type", max_length=40, db_index=True)
    reference = models.CharField("référence", max_length=24, blank=True, db_index=True)
    to = models.EmailField("destinataire")
    subject = models.CharField("objet", max_length=255)
    body = models.TextField("contenu")
    status = models.CharField("statut", max_length=10, choices=Status.choices, default=Status.SENT)
    error = models.TextField("erreur", blank=True)
    sent_at = models.DateTimeField("envoyé le", auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "e-mail envoyé"
        verbose_name_plural = "e-mails envoyés"

    def __str__(self):
        return f"{self.subject} → {self.to}"
