from django.core.management.base import BaseCommand, CommandError

from apps.pricing.providers import GoldPriceUnavailable
from apps.pricing.services import SuspiciousGoldPrice, refresh_gold_price


class Command(BaseCommand):
    help = "Fetch the gold spot price and store it (run every 15 minutes via cron)."

    def add_arguments(self, parser):
        parser.add_argument("--provider", help="Override GOLD_PRICE_PROVIDER")
        parser.add_argument(
            "--force", action="store_true", help="Accept the quote even if it deviates strongly from the last one"
        )

    def handle(self, *args, **options):
        try:
            quote = refresh_gold_price(options["provider"], force=options["force"])
        except (GoldPriceUnavailable, SuspiciousGoldPrice) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Cours enregistré : {quote}"))
