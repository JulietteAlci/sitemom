from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Ring
from apps.pricing.models import GoldPrice


class CoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=open("/dev/null", "w"))

    def test_seed_is_idempotent(self):
        call_command("seed_demo", stdout=open("/dev/null", "w"))
        self.assertEqual(Ring.objects.count(), 12)
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
