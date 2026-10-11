from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalog.models import Ring
from apps.pricing.models import GoldPrice


class CoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=open("/dev/null", "w"))

    def test_seed_is_idempotent(self):
        call_command("seed_demo", stdout=open("/dev/null", "w"))
        self.assertEqual(Ring.objects.count(), 17)  # 12 alliances + 5 solitaires
        self.assertEqual(GoldPrice.objects.count(), 1)

    def test_home(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Cours de l'or")
        self.assertContains(response, '"@type": "JewelryStore"')
        self.assertContains(response, '"FAQPage"')

    def test_robots_points_to_sitemap(self):
        response = self.client.get("/robots.txt")
        self.assertContains(response, "Sitemap: http")
        self.assertContains(response, "Disallow: /panier/")

    def test_sitemap_lists_catalogue_and_blog(self):
        response = self.client.get("/sitemap.xml")
        ring = Ring.objects.first()
        self.assertContains(response, ring.get_absolute_url())
        self.assertContains(response, reverse("catalog:men"))
        self.assertContains(response, "/journal/")

    def test_llms_txt(self):
        response = self.client.get("/llms.txt")
        self.assertEqual(response["Content-Type"], "text/markdown; charset=utf-8")
        self.assertContains(response, "## Alliances")
        self.assertContains(response, "€ TTC")

    def test_gold_price_page_and_api(self):
        self.assertEqual(self.client.get(reverse("pricing:gold_price")).status_code, 200)
        data = self.client.get(reverse("pricing:gold_price_api")).json()
        self.assertTrue(data["available"])
        self.assertEqual(Decimal(data["eur_per_oz"]), GoldPrice.current().price_per_oz_eur)


@override_settings(
    TRIAL_KIT_PRICE_CENTS=10000, TRIAL_KIT_CREDIT_CENTS=8000, TRIAL_KIT_REFUND_CENTS=2000, TRIAL_KIT_RETURN_DAYS=8
)
class HowItWorksTests(TestCase):
    def test_page_describes_the_customer_journey(self):
        response = self.client.get(reverse("core:how_it_works"))
        self.assertEqual(len(response.context["steps"]), 5)
        for text in (
            "Commandez votre coffret d&#x27;essai à 100\u00a0€",
            "Essayez les alliances chez vous",
            "Renvoyez le coffret sous 8 jours",
            "nous vous remboursons 20\u00a0€",
            "Commandez vos alliances sur le site",
            "80\u00a0€ sont déduits",
            "Recevez vos alliances",
            "ces 80\u00a0€ ne sont pas remboursés",
            '"@type":"HowTo"',
        ):
            self.assertContains(response, text)

    def test_linked_from_navigation_and_sitemap(self):
        url = reverse("core:how_it_works")
        self.assertContains(self.client.get(reverse("core:home")), f'href="{url}"')
        self.assertContains(self.client.get("/sitemap.xml"), url)
