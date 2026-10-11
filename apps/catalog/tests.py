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


class ProductStructureTests(TestCase):
    """Product page options (métal, type de pierre, poids carat, taille) and stone pricing."""

    def setUp(self):
        from .models import Collection, Metal, ModelFamily, ProductFAQ, Reassurance, Review, StoneOption

        GoldPrice.objects.create(price_per_oz_eur=Decimal("3000"), source="test")
        family = ModelFamily.objects.create(name="Éclat")
        self.collection = Collection.objects.create(name="Solitaires", slug="solitaires")
        self.ring = make_ring(
            name="Solitaire diamant", slug="solitaire-diamant", category=Ring.Category.SOLITAIRE,
            main_stone=Ring.MainStone.DIAMOND, family=family, engraving_max_length=100,
        )
        self.ring.metals.set(Metal.objects.filter(code__in=["jaune", "blanc", "rose"]))
        self.ring.collections.add(self.collection)
        for stone_type, carat, price in (("naturel", "0.10", 100), ("naturel", "0.50", 1000), ("synthese", "0.50", 200)):
            StoneOption.objects.create(ring=self.ring, stone_type=stone_type, carat=Decimal(carat), price=price)
        self.sibling = make_ring(name="Solitaire saphir", slug="solitaire-saphir", main_stone="saphir", family=family)
        self.sibling.collections.add(self.collection)
        Review.objects.create(author="Claire M.", rating=5, text="Superbe.")
        Review.objects.create(author="Paul D.", rating=4, text="Très bien.", ring=self.ring)
        ProductFAQ.objects.create(question="Quelle taille ?", answer="Votre tour de doigt.")
        Reassurance.objects.create(title="Livraison offerte", text="Colis assuré.")

    def get(self, **params):
        return self.client.get(self.ring.get_absolute_url(), params)

    def test_default_selection_is_cheapest_first_option(self):
        selection = self.get().context["selection"]
        self.assertEqual((selection.metal.code, str(selection.stone.carat), selection.size), ("jaune", "0.10", 54))

    def test_selection_changes_price(self):
        small = self.get(carat="0.10").context["breakdown"].price_ttc
        natural = self.get(pierre="naturel", carat="0.50").context["breakdown"].price_ttc
        lab = self.get(pierre="synthese", carat="0.50").context["breakdown"].price_ttc
        self.assertLess(small, lab)
        self.assertLess(lab, natural)
        # Stone cost is added before margin and VAT (test ring: no margin): (1000 − 100) × 1.20 = 1080 € more.
        self.assertEqual(natural - small, Decimal("1080"))

    def test_invalid_params_fall_back(self):
        selection = self.get(metal="platine", pierre="x", carat="abc", taille="99").context["selection"]
        self.assertEqual((selection.metal.code, str(selection.stone.carat), selection.size), ("jaune", "0.10", 54))

    def test_carat_choices_follow_stone_type(self):
        rows = {row["key"]: row for row in self.get(pierre="synthese").context["selectors"]}
        self.assertEqual([c["label"] for c in rows["carat"]["choices"]], ["0,50 carat"])
        self.assertEqual([c["label"] for c in rows["metal"]["choices"]], ["Or jaune", "Or blanc", "Or rose"])

    def test_page_sections(self):
        response = self.get(carat="0.50")
        for text in ("Existe aussi en", "Solitaire saphir", "Les avis clients", "Dans la même collection",
                     "Certificat d'authenticité", "Votre sélection en bénéficie", "Quelle taille ?",
                     "Livraison offerte", "Ajouter une gravure", "Caractères utilisés : 0 / 200"):
            self.assertContains(response, text)
        self.assertEqual(response.context["review_stats"]["count"], 2)
        # Structured data only uses this product's own reviews.
        self.assertContains(response, '"reviewCount": 1')

    def test_no_lab_certificate_mention_for_small_diamond(self):
        self.assertNotContains(self.get(carat="0.10"), "Votre sélection en bénéficie")

    def test_add_to_cart_with_options(self):
        from apps.orders.cart import Cart  # noqa: F401

        stone = self.ring.stone_options.get(stone_type="synthese")
        self.client.post(
            reverse("orders:cart_add", args=[self.ring.slug]),
            {"size": 56, "metal": "rose", "stone": stone.pk, "engraving": "A" * 100, "comment": "Pour juin"},
        )
        line = self.client.get(reverse("orders:cart")).context["lines"][0]
        self.assertEqual((line.metal.code, line.stone, line.size, line.comment), ("rose", stone, 56, "Pour juin"))
        self.assertEqual(line.breakdown.price_ttc, self.ring.price(56, stone=stone).price_ttc)
        self.assertEqual(line.description, "Or rose · Diamant de synthèse 0,50 carat · taille 56")

    def test_add_to_cart_rejects_foreign_stone_and_long_engraving(self):
        foreign = self.sibling.stone_options.create(carat=Decimal("0.30"), price=50)
        for data in ({"stone": foreign.pk}, {"stone": self.ring.cheapest_stone.pk, "engraving": "A" * 101}):
            self.client.post(reverse("orders:cart_add", args=[self.ring.slug]), {"size": 54, **data})
        self.assertEqual(self.client.get(reverse("orders:cart")).context["lines"], [])

    def test_collection_page_and_metal_filter(self):
        response = self.client.get(self.collection.get_absolute_url())
        self.assertEqual(sorted(ring.name for ring, _ in response.context["items"]), ["Solitaire diamant", "Solitaire saphir"])
        names = [r.name for r, _ in self.client.get(reverse("catalog:ring_list"), {"couleur": "rose"}).context["items"]]
        self.assertIn("Solitaire diamant", names)
