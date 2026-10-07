from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.catalog.models import Ring

from . import providers
from .models import TROY_OUNCE_GRAMS, GoldPrice
from .services import SuspiciousGoldPrice, compute_ring_price, refresh_gold_price


def make_ring(**kwargs):
    defaults = dict(
        name="Test",
        slug="test",
        gender=Ring.Gender.WOMEN,
        width_mm=Decimal("2.5"),
        thickness_mm=Decimal("1.7"),
        reference_weight_g=Decimal("4.00"),
        reference_size=54,
        labor_cost=Decimal("100"),
        stone_cost=Decimal("0"),
        gold_markup_rate=Decimal("0"),
        margin_rate=Decimal("0"),
        purity=Ring.Purity.K18,
        short_description="Test",
    )
    defaults.update(kwargs)
    return Ring.objects.create(**defaults)


class ComputeRingPriceTests(TestCase):
    def setUp(self):
        # 3110.34768 €/oz → exactly 100 €/g of pure gold.
        self.spot = GoldPrice.objects.create(price_per_oz_eur=TROY_OUNCE_GRAMS * 100, source="test")

    def test_no_spot_means_no_price(self):
        GoldPrice.objects.all().delete()
        self.assertIsNone(compute_ring_price(make_ring()))

    @override_settings(VAT_RATE="0.20")
    def test_formula_at_reference_size(self):
        breakdown = compute_ring_price(make_ring(), spot=self.spot)
        # 4 g × 0.750 = 3 g fine gold × 100 €/g = 300 € + 100 € labour = 400 € HT → 480 € TTC.
        self.assertEqual(breakdown.fine_gold_g, Decimal("3.00"))
        self.assertEqual(breakdown.gold_value, Decimal("300.00"))
        self.assertEqual(breakdown.price_ttc, Decimal("480"))
        self.assertEqual(breakdown.price_ht + breakdown.vat, breakdown.price_ttc)
        self.assertEqual(breakdown.amount_cents, 48000)

    @override_settings(VAT_RATE="0.20")
    def test_markup_and_margin(self):
        ring = make_ring(gold_markup_rate=Decimal("0.10"), margin_rate=Decimal("0.50"))
        # (300 × 1.10 + 100) × 1.50 = 645 HT → 774 TTC
        self.assertEqual(compute_ring_price(ring, spot=self.spot).price_ttc, Decimal("774"))

    def test_weight_scales_with_size(self):
        ring = make_ring()
        small = compute_ring_price(ring, 50, self.spot)
        large = compute_ring_price(ring, 60, self.spot)
        self.assertLess(small.weight_g, Decimal("4"))
        self.assertGreater(large.weight_g, Decimal("4"))
        self.assertLess(small.price_ttc, large.price_ttc)

    def test_ttc_is_rounded_up_to_the_euro(self):
        ring = make_ring(labor_cost=Decimal("100.01"))
        self.assertEqual(compute_ring_price(ring, spot=self.spot).price_ttc, Decimal("481"))

    def test_price_follows_spot(self):
        ring = make_ring()
        higher = GoldPrice.objects.create(price_per_oz_eur=TROY_OUNCE_GRAMS * 110, source="test")
        self.assertGreater(compute_ring_price(ring, spot=higher).price_ttc, compute_ring_price(ring, spot=self.spot).price_ttc)
        self.assertEqual(compute_ring_price(ring).spot, higher)  # latest quote by default


class GoldPriceModelTests(TestCase):
    @override_settings(GOLD_PRICE_MAX_AGE_MINUTES=60)
    def test_freshness(self):
        fresh = GoldPrice.objects.create(price_per_oz_eur=3000, source="t")
        stale = GoldPrice.objects.create(price_per_oz_eur=3000, source="t", fetched_at=timezone.now() - timedelta(hours=2))
        self.assertTrue(fresh.is_fresh)
        self.assertFalse(stale.is_fresh)
        self.assertEqual(GoldPrice.current(), fresh)


def fake_response(payload):
    response = mock.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class ProviderTests(TestCase):
    @mock.patch("apps.pricing.providers.requests.get")
    def test_gold_api_com_converts_usd_to_eur(self, get):
        get.side_effect = [fake_response({"price": 4000.0}), fake_response({"rates": {"EUR": 0.9}})]
        price, source = providers.fetch_spot_eur_per_oz("goldapicom")
        self.assertEqual(price, Decimal("3600.00"))
        self.assertEqual(source, "goldapicom")

    @override_settings(GOLDAPI_KEY="key")
    @mock.patch("apps.pricing.providers.requests.get")
    def test_goldapi_io(self, get):
        get.return_value = fake_response({"price": 3456.78})
        price, _ = providers.fetch_spot_eur_per_oz("goldapi")
        self.assertEqual(price, Decimal("3456.78"))
        self.assertEqual(get.call_args.kwargs["headers"], {"x-access-token": "key"})

    @mock.patch("apps.pricing.providers.requests.get")
    def test_invalid_values_rejected(self, get):
        for bad in (None, 0, -5, "abc"):
            get.side_effect = [fake_response({"price": bad})]
            with self.assertRaises(providers.GoldPriceUnavailable):
                providers.fetch_gold_api_com()

    @override_settings(GOLDAPI_KEY="")
    def test_goldapi_requires_key(self):
        with self.assertRaises(providers.GoldPriceUnavailable):
            providers.fetch_goldapi_io()

    def test_manual_provider_cannot_fetch(self):
        with self.assertRaises(providers.GoldPriceUnavailable):
            providers.fetch_spot_eur_per_oz("manual")


class RefreshTests(TestCase):
    @mock.patch("apps.pricing.services.fetch_spot_eur_per_oz", return_value=(Decimal("3000"), "test"))
    def test_refresh_creates_quote(self, _):
        quote = refresh_gold_price()
        self.assertEqual(GoldPrice.current(), quote)

    @mock.patch("apps.pricing.services.fetch_spot_eur_per_oz", return_value=(Decimal("5000"), "test"))
    def test_suspicious_jump_rejected_unless_forced(self, _):
        GoldPrice.objects.create(price_per_oz_eur=3000, source="test")
        with self.assertRaises(SuspiciousGoldPrice):
            refresh_gold_price()
        self.assertEqual(GoldPrice.objects.count(), 1)
        refresh_gold_price(force=True)
        self.assertEqual(GoldPrice.current().price_per_oz_eur, Decimal("5000"))

    @mock.patch(
        "apps.pricing.services.fetch_spot_eur_per_oz", side_effect=providers.GoldPriceUnavailable("down")
    )
    def test_command_reports_failure(self, _):
        with self.assertRaises(CommandError):
            call_command("update_gold_price")
