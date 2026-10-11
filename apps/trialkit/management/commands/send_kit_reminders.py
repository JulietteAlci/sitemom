from django.core.management.base import BaseCommand

from apps.trialkit.services import send_due_reminders


class Command(BaseCommand):
    help = "E-mail customers whose trial kit is due back (every TRIAL_KIT_REMINDER_EVERY_DAYS days). Run daily."

    def handle(self, *args, **options):
        sent = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(f"{sent} relance(s) envoyée(s)."))
