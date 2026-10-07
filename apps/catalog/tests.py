from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.pricing.models import GoldPrice
from apps.pricing.tests import make_ring

from .models import Ring


class CatalogViewTests(TestCase):
    def setUp(self):
        GoldPrice.objects.create(price_per_oz_eur=Decimal("3000"), source="test")
        self.women = make_ring(name="Femme", slug="femme-1", gender=Ring.Gender.WOMEN, color=Ring.Color.ROSE)
        self.men = make_ring(name="Homme", slug="homme-1", gender=Ring.Gender.MEN, reference_weight_g=Decimal("8"))
        self.unisex = make_ring(name="Mixte", slug="mixte-1", gender=Ring.Gender.UNISEX)
        make_ring(name="Hors ligne", slug="off", gender=Ring.Gender.MEN, is_active=False)

    def _names(self, response):
        return [ring.name for ring, _ in response.context["items"]]

    def test_men_catalogue_includes_unisex(self):
        response = self.client.get(reverse("catalog:men"))
        self.assertEqual(sorted(self._names(response)), ["Homme", "Mixte"])

    def test_women_catalogue_includes_unisex(self):
        response = self.client.get(reverse("catalog:women"))
        self.assertEqual(sorted(self._names(response)), ["Femme", "Mixte"])

    def test_filter_and_sort(self):
        response = self.client.get(reverse("catalog:women"), {"couleur": "rose"})
        self.assertEqual(self._names(response), ["Femme"])
        response = self.client.get(reverse("catalog:ring_list"), {"tri": "prix-desc"})
        self.assertEqual(self._names(response)[0], "Homme")
        # unknown values are ignored
        response = self.client.get(reverse("catalog:ring_list"), {"couleur": "violet", "tri": "x"})
        self.assertEqual(len(self._names(response)), 3)

    def test_detail_shows_price_and_structured_data(self):
        response = self.client.get(self.men.get_absolute_url(), {"taille": 62})
        self.assertEqual(response.context["size"], 62)
        self.assertContains(response, '"@type": "Product"')
        self.assertContains(response, '"priceCurrency": "EUR"')

    def test_detail_invalid_size_falls_back(self):
        response = self.client.get(self.men.get_absolute_url(), {"taille": "999"})
        self.assertEqual(response.context["size"], self.men.reference_size)

    def test_inactive_ring_is_404(self):
        self.assertEqual(self.client.get(reverse("catalog:ring_detail", args=["off"])).status_code, 404)

    def test_works_without_gold_price(self):
        GoldPrice.objects.all().delete()
        self.assertEqual(self.client.get(reverse("catalog:men")).status_code, 200)
        response = self.client.get(self.men.get_absolute_url())
        self.assertContains(response, "Prix bientôt disponible")
