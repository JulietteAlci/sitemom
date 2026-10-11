"""Transactional e-mails: templates/emails/<kind>/{subject.txt, body.txt, body.html}."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .models import EmailLog

logger = logging.getLogger(__name__)


def send_email(kind: str, to: str, context: dict, reference: str = "") -> EmailLog | None:
    if not to:
        return None
    context = {"SITE_NAME": settings.SITE_NAME, "SITE_URL": settings.SITE_URL, **context}
    subject = " ".join(render_to_string(f"emails/{kind}/subject.txt", context).split())
    text = render_to_string(f"emails/{kind}/body.txt", context)
    html = render_to_string(f"emails/{kind}/body.html", context)
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
    message.attach_alternative(html, "text/html")
    log = EmailLog(kind=kind, reference=reference, to=to, subject=subject, body=text)
    try:
        message.send()
    except Exception as exc:  # never break a payment or an admin action because of the mail server
        logger.exception("E-mail %s to %s failed", kind, to)
        log.status, log.error = EmailLog.Status.FAILED, str(exc)
    log.save()
    return log
