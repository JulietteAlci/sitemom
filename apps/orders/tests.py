import hashlib
import hmac
import json
import time
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.pricing.models import TROY_OUNCE_GRAMS, GoldPrice
from apps.pricing.tests import make_ring

from .models import Order

WEBHOOK_SECRET = "whsec_test"


def signed_post(client, payload: dict):
    body = json.dumps(payload)
    timestamp = int(time.time())
    signature = hmac.new(WEBHOOK_SECRET.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    return client.post(
        reverse("orders:stripe_webhook"),
        data=body,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
    )


def fake_session(**kwargs):
    return SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.com/c/pay/cs_test_123")


@override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET, VAT_RATE="0.20")
class CheckoutTests(TestCase):
    def setUp(self):
        GoldPrice.objects.create(price_per_oz_eur=TROY_OUNCE_GRAMS * 100, source="test")
        # (300 € gold + 99.50 € labour) × 1.20 = 479.40 → 480 € TTC at size 54
        self.ring = make_ring(labor_cost=Decimal("99.50"))

    def add_to_cart(self, **data):
        payload = {"size": 54, "engraving": "A & B", "quantity": 1}
        payload.update(data)
        return self.client.post(reverse("orders:cart_add", args=[self.ring.slug]), payload)

    def test_add_to_cart(self):
        self.assertRedirects(self.add_to_cart(), reverse("orders:cart"))
        response = self.client.get(reverse("orders:cart"))
        self.assertEqual(response.context["total"], Decimal("480"))
        self.assertEqual(response.context["cart_count"], 1)

    def test_invalid_size_rejected(self):
        self.add_to_cart(size=99)
        self.assertEqual(self.client.get(reverse("orders:cart")).context["lines"], [])

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    def test_checkout_snapshots_prices_and_redirects_to_stripe(self, create):
        self.add_to_cart(quantity=2)
        response = self.client.post(reverse("orders:checkout"))
        self.assertRedirects(response, "https://checkout.stripe.com/c/pay/cs_test_123", fetch_redirect_response=False)

        order = Order.objects.get()
        self.assertEqual(order.total, Decimal("960"))
        self.assertEqual(order.gold_spot_eur_per_oz, GoldPrice.current().price_per_oz_eur)
        self.assertEqual(order.stripe_session_id, "cs_test_123")
        item = order.items.get()
        self.assertEqual((item.size, item.engraving, item.quantity, item.unit_price), (54, "A & B", 2, Decimal("480")))

        params = create.call_args.kwargs
        self.assertEqual(params["line_items"][0]["price_data"]["unit_amount"], 48000)
        self.assertEqual(params["line_items"][0]["quantity"], 2)
        self.assertEqual(params["metadata"], {"kind": "order", "object_id": str(order.pk), "reference": order.reference})

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    def test_checkout_refused_when_gold_price_is_stale(self, create):
        GoldPrice.objects.update(fetched_at=timezone.now() - timedelta(days=3))
        self.add_to_cart()
        self.assertRedirects(self.client.post(reverse("orders:checkout")), reverse("orders:cart"))
        create.assert_not_called()
        self.assertFalse(Order.objects.exists())

    @override_settings(STRIPE_SECRET_KEY="")
    def test_checkout_without_stripe_keys_fails_gracefully(self):
        self.add_to_cart()
        self.assertRedirects(self.client.post(reverse("orders:checkout")), reverse("orders:cart"))
        self.assertEqual(Order.objects.get().status, Order.Status.CANCELLED)

    def test_success_page_clears_cart(self):
        self.add_to_cart()
        order = Order.objects.create(total=480, gold_spot_eur_per_oz=3000, stripe_session_id="cs_x")
        response = self.client.get(reverse("orders:success"), {"session_id": "cs_x"})
        self.assertEqual(response.context["order"], order)
        self.assertEqual(self.client.get(reverse("orders:cart")).context["lines"], [])


@override_settings(STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(total=480, gold_spot_eur_per_oz=3000, stripe_session_id="cs_1")

    def event(self, type_="checkout.session.completed", **session):
        obj = {
            "id": "cs_1",
            "payment_status": "paid",
            "payment_intent": "pi_1",
            "metadata": {"kind": "order", "object_id": str(self.order.pk)},
            "customer_details": {"email": "a@example.com", "name": "Alice", "phone": "+33600000000"},
            "collected_information": {"shipping_details": {"name": "Alice Martin", "address": {"city": "Paris"}}},
        }
        obj.update(session)
        return {"type": type_, "data": {"object": obj}}

    def test_invalid_signature(self):
        response = self.client.post(
            reverse("orders:stripe_webhook"), data="{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=bad"
        )
        self.assertEqual(response.status_code, 400)

    def test_completed_marks_paid_idempotently(self):
        self.assertEqual(signed_post(self.client, self.event()).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.email, "a@example.com")
        self.assertEqual(self.order.full_name, "Alice Martin")
        self.assertEqual(self.order.shipping_address, {"city": "Paris"})
        paid_at = self.order.paid_at
        signed_post(self.client, self.event())
        self.order.refresh_from_db()
        self.assertEqual(self.order.paid_at, paid_at)

    def test_unpaid_completion_is_ignored(self):
        signed_post(self.client, self.event(payment_status="unpaid"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_session_id_must_match(self):
        signed_post(self.client, self.event(id="cs_other"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_expired_cancels(self):
        signed_post(self.client, self.event("checkout.session.expired", payment_status="unpaid"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)


@override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET, VAT_RATE="0.20")
class TrialKitCreditTests(TestCase):
    """Step 4 of the customer journey: the trial kit price is deducted with its unique code."""

    def setUp(self):
        from apps.trialkit.models import TrialKitOrder

        GoldPrice.objects.create(price_per_oz_eur=TROY_OUNCE_GRAMS * 100, source="test")
        self.ring = make_ring(labor_cost=Decimal("99.50"))  # 480 € TTC
        self.kit = TrialKitOrder.objects.create(price=80, status=TrialKitOrder.Status.PAID)
        self.client.post(reverse("orders:cart_add", args=[self.ring.slug]), {"size": 54, "quantity": 1})

    def apply(self, code):
        return self.client.post(reverse("orders:cart_trial_kit_code"), {"code": code})

    def cart(self):
        return self.client.get(reverse("orders:cart")).context

    def test_valid_code_is_deducted(self):
        self.apply(self.kit.credit_code.lower())
        context = self.cart()
        self.assertEqual(context["subtotal"], Decimal("480"))
        self.assertEqual(context["credit"].amount, Decimal("80"))
        self.assertEqual(context["total"], Decimal("400"))

    def test_unknown_code_rejected(self):
        self.apply("ESSAI-ZZZZ-ZZZZ")
        self.assertIsNone(self.cart()["credit"])

    def test_unpaid_kit_code_not_usable(self):
        self.kit.status = self.kit.Status.PENDING
        self.kit.save()
        self.apply(self.kit.credit_code)
        context = self.cart()
        self.assertIn("confirmation du paiement", context["credit"].error)
        self.assertEqual(context["total"], Decimal("480"))

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    @mock.patch("apps.orders.payments.stripe.Coupon.create", return_value=SimpleNamespace(id="coupon_1"))
    def test_checkout_applies_stripe_coupon(self, coupon_create, session_create):
        self.apply(self.kit.credit_code)
        self.client.post(reverse("orders:checkout"))
        order = Order.objects.get()
        self.assertEqual((order.total, order.discount, order.trial_kit), (Decimal("400"), Decimal("80"), self.kit))
        self.assertEqual(order.subtotal, Decimal("480"))
        self.assertEqual(coupon_create.call_args.kwargs["amount_off"], 8000)
        self.assertEqual(coupon_create.call_args.kwargs["max_redemptions"], 1)
        self.assertEqual(session_create.call_args.kwargs["discounts"], [{"coupon": "coupon_1"}])

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    @mock.patch("apps.orders.payments.stripe.Coupon.create", return_value=SimpleNamespace(id="coupon_1"))
    def test_code_is_single_use(self, *_):
        Order.objects.create(
            total=400, discount=80, trial_kit=self.kit, gold_spot_eur_per_oz=3000, status=Order.Status.PAID
        )
        self.apply(self.kit.credit_code)
        self.assertIn("déjà été utilisé", self.cart()["credit"].error)
        self.assertRedirects(self.client.post(reverse("orders:checkout")), reverse("orders:cart"))
        self.assertEqual(Order.objects.count(), 1)

    def test_code_reserved_by_another_pending_checkout(self):
        Order.objects.create(total=400, discount=80, trial_kit=self.kit, gold_spot_eur_per_oz=3000)
        self.apply(self.kit.credit_code)
        self.assertIn("en cours d'utilisation", self.cart()["credit"].error)

    @mock.patch("apps.orders.views.stripe.checkout.Session.expire")
    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    @mock.patch("apps.orders.payments.stripe.Coupon.create", return_value=SimpleNamespace(id="coupon_1"))
    def test_customer_can_retry_after_abandoning_checkout(self, _coupon, _create, expire):
        self.apply(self.kit.credit_code)
        self.client.post(reverse("orders:checkout"))
        self.client.post(reverse("orders:checkout"))  # came back from Stripe and retried
        expire.assert_called_once()
        first, second = Order.objects.order_by("pk")
        self.assertEqual(first.status, Order.Status.CANCELLED)
        self.assertEqual((second.status, second.discount), (Order.Status.PENDING, Decimal("80")))

    def test_paid_order_converts_kit(self):
        order = Order.objects.create(
            total=400, discount=80, trial_kit=self.kit, gold_spot_eur_per_oz=3000, stripe_session_id="cs_1"
        )
        signed_post(
            self.client,
            {
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_1", "payment_status": "paid",
                                    "metadata": {"kind": "order", "object_id": str(order.pk)}}},
            },
        )
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.fulfillment, self.kit.Fulfillment.CONVERTED)
        self.assertEqual(self.kit.redeemed_order, order)
