from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.orders.tests import WEBHOOK_SECRET, fake_session, signed_post
from apps.pricing.tests import make_ring

from .models import TrialKitOrder, normalize_code


@override_settings(
    STRIPE_SECRET_KEY="sk_test",
    STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET,
    TRIAL_KIT_MIN=8,
    TRIAL_KIT_MAX=12,
    TRIAL_KIT_PRICE_CENTS=8000,
)
class TrialKitTests(TestCase):
    def setUp(self):
        self.rings = [make_ring(name=f"R{i}", slug=f"r{i}") for i in range(14)]
        make_ring(name="Not for trial", slug="no-trial", available_for_trial=False)

    def post(self, rings):
        return self.client.post(
            reverse("trialkit:start"), {"rings": [r.pk for r in rings], "include_sizer": "on"}
        )

    def test_page_lists_only_trial_rings(self):
        response = self.client.get(reverse("trialkit:start"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Not for trial")

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    def test_selection_bounds(self, create):
        for count in (7, 13):
            response = self.post(self.rings[:count])
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors["rings"])
        create.assert_not_called()
        self.assertFalse(TrialKitOrder.objects.exists())

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    def test_valid_kit_charges_kit_price(self, create):
        for count in (8, 12):
            response = self.post(self.rings[:count])
            self.assertRedirects(response, fake_session().url, fetch_redirect_response=False)
            kit = TrialKitOrder.objects.latest("pk")
            self.assertEqual(kit.rings.count(), count)
            self.assertTrue(kit.reference.startswith("ESS-"))
            params = create.call_args.kwargs
            self.assertEqual(params["line_items"][0]["price_data"]["unit_amount"], 8000)
            self.assertEqual(kit.price, 80)
            self.assertRegex(kit.credit_code, r"^ESSAI-[2-9A-HJ-NP-Z]{4}-[2-9A-HJ-NP-Z]{4}$")
            self.assertEqual(params["metadata"]["kind"], "trial_kit")

    def test_ring_not_available_for_trial_rejected(self):
        response = self.client.post(
            reverse("trialkit:start"), {"rings": [r.pk for r in self.rings[:7]] + [999999]}
        )
        self.assertTrue(response.context["form"].errors["rings"])

    def test_webhook_marks_kit_paid(self):
        kit = TrialKitOrder.objects.create(price=80, stripe_session_id="cs_kit")
        kit.rings.set(self.rings[:8])
        signed_post(
            self.client,
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_kit",
                        "payment_status": "paid",
                        "metadata": {"kind": "trial_kit", "object_id": str(kit.pk)},
                        "customer_details": {"email": "b@example.com"},
                    }
                },
            },
        )
        kit.refresh_from_db()
        self.assertEqual(kit.status, TrialKitOrder.Status.PAID)
        self.assertEqual(kit.fulfillment, TrialKitOrder.Fulfillment.TO_PREPARE)


class CreditCodeTests(TestCase):
    def test_codes_are_unique(self):
        codes = {TrialKitOrder.objects.create(price=80).credit_code for _ in range(20)}
        self.assertEqual(len(codes), 20)

    def test_normalize_code(self):
        for raw in ("essai-abcd-efgh", "ESSAI ABCD EFGH", "abcdefgh", " Essai-ABCD-efgh "):
            self.assertEqual(normalize_code(raw), "ESSAI-ABCD-EFGH")
        self.assertEqual(normalize_code("ESSAI-ABC"), "")
        self.assertEqual(normalize_code(""), "")
