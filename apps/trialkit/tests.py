from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.tests import WEBHOOK_SECRET, fake_session, signed_post
from apps.pricing.tests import make_ring

from . import services
from .models import SampleRing, TrialKitOrder, normalize_code

KIT_SETTINGS = dict(
    STRIPE_SECRET_KEY="sk_test",
    STRIPE_DEMO_MODE=False,
    STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET,
    TRIAL_KIT_MIN=4,
    TRIAL_KIT_MAX=4,
    TRIAL_KIT_PRICE_CENTS=10000,
    TRIAL_KIT_CREDIT_CENTS=8000,
    TRIAL_KIT_REFUND_CENTS=2000,
    TRIAL_KIT_RETURN_DAYS=8,
    TRIAL_KIT_DELIVERY_DAYS=2,
    TRIAL_KIT_REMINDER_EVERY_DAYS=2,
)


def paid_kit(samples, **fields):
    kit = TrialKitOrder.objects.create(
        price=100, credit_amount=80, refund_amount=20, status="paid", paid_at=timezone.now(),
        email="claire@example.com", full_name="Claire Martin", stripe_payment_intent="pi_123",
        shipping_address={"line1": "1 rue de la Paix", "postal_code": "75002", "city": "Paris", "country": "FR"},
        **fields,
    )
    kit.samples.set(samples)
    return kit


@override_settings(**KIT_SETTINGS)
class KitOrderTests(TestCase):
    """1. Order a kit of 4 dummies for 100 €, with stock limits."""

    def setUp(self):
        self.rings = [make_ring(name=f"Modèle {i}", slug=f"modele-{i}") for i in range(6)]
        self.samples = [SampleRing.objects.create(reference=f"FAC-{i}", ring=ring, quantity=2) for i, ring in enumerate(self.rings)]
        SampleRing.objects.create(reference="FAC-OFF", ring=make_ring(name="Retiré", slug="retire"), is_active=False)

    def post(self, samples):
        return self.client.post(reverse("trialkit:start"), {"samples": [s.pk for s in samples], "include_sizer": "on"})

    def test_page_lists_active_dummies_only(self):
        response = self.client.get(reverse("trialkit:start"))
        self.assertContains(response, "Modèle 0")
        self.assertNotContains(response, "Retiré")
        self.assertContains(response, "Choisissez</strong> 4 modèles")

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    def test_exactly_four_dummies(self, create):
        for count in (3, 5):
            response = self.post(self.samples[:count])
            self.assertIn("exactement 4", str(response.context["form"].errors["samples"]))
        create.assert_not_called()

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    def test_valid_kit_charges_100(self, create):
        response = self.post(self.samples[:4])
        self.assertRedirects(response, fake_session().url, fetch_redirect_response=False)
        kit = TrialKitOrder.objects.get()
        self.assertEqual((kit.price, kit.credit_amount, kit.refund_amount), (100, 80, 20))
        self.assertEqual(kit.samples.count(), 4)
        params = create.call_args.kwargs
        self.assertEqual(params["line_items"][0]["price_data"]["unit_amount"], 10000)
        # 1. Contact details and address are collected by the checkout.
        self.assertEqual(params["shipping_address_collection"]["allowed_countries"][0], "FR")
        self.assertTrue(params["phone_number_collection"]["enabled"])

    @mock.patch("apps.orders.payments.stripe.checkout.Session.create", side_effect=fake_session)
    def test_stock_makes_dummy_unavailable(self, create):
        scarce = self.samples[0]
        scarce.quantity = 2
        scarce.save()
        paid_kit([scarce, *self.samples[1:4]], fulfillment="shipped", shipped_at=timezone.now())
        paid_kit([scarce, *self.samples[1:4]], fulfillment="delivered", shipped_at=timezone.now())
        annotated = SampleRing.objects.with_availability().get(pk=scarce.pk)
        self.assertEqual((annotated.in_use, annotated.available), (2, 0))

        response = self.client.get(reverse("trialkit:start"))
        self.assertContains(response, "Indisponible actuellement")
        response = self.post([scarce, *self.samples[3:6]])
        self.assertIn("viennent d&#x27;être réservés", response.content.decode())
        create.assert_not_called()

    def test_stock_comes_back_once_checked_or_cancelled(self):
        sample = self.samples[0]
        sample.quantity = 1
        sample.save()
        kit = paid_kit([sample], fulfillment="returned", shipped_at=timezone.now())
        self.assertEqual(sample.available_count(), 0)  # back at the shop but not checked yet
        kit.fulfillment = "refunded"
        kit.save()
        self.assertEqual(sample.available_count(), 1)
        # An unpaid checkout reserves the dummy for 30 minutes only.
        pending = TrialKitOrder.objects.create(price=100)
        pending.samples.set([sample])
        self.assertEqual(sample.available_count(), 0)
        TrialKitOrder.objects.filter(pk=pending.pk).update(created_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(sample.available_count(), 1)

    def test_product_page_links_to_kit_only_when_dummy_available(self):
        ring = self.rings[0]
        self.assertContains(self.client.get(ring.get_absolute_url()), f"?factice={self.samples[0].pk}")
        SampleRing.objects.filter(ring=ring).update(quantity=0)
        self.assertNotContains(self.client.get(ring.get_absolute_url()), "Essayer à domicile")


@override_settings(**KIT_SETTINGS)
class KitLifecycleTests(TestCase):
    """2 to 7: e-mails, admin documents, return window, reminders and 20 € refund."""

    def setUp(self):
        rings = [make_ring(name=f"Modèle {i}", slug=f"modele-{i}", sku=f"ALL-{i}") for i in range(4)]
        self.samples = [SampleRing.objects.create(reference=f"FAC-{i}", ring=ring) for i, ring in enumerate(rings)]
        self.kit = TrialKitOrder.objects.create(price=100, credit_amount=80, refund_amount=20, stripe_session_id="cs_kit")
        self.kit.samples.set(self.samples)

    def pay(self):
        signed_post(self.client, {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_kit", "payment_status": "paid", "payment_intent": "pi_123",
                "metadata": {"kind": "trial_kit", "object_id": str(self.kit.pk)},
                "customer_details": {"email": "claire@example.com", "name": "Claire Martin", "phone": "0600000000"},
                "collected_information": {"shipping_details": {"name": "Claire Martin", "address": {
                    "line1": "1 rue de la Paix", "postal_code": "75002", "city": "Paris", "country": "FR"}}},
            }},
        })
        self.kit.refresh_from_db()

    def test_confirmation_email(self):
        self.pay()
        self.assertEqual(self.kit.status, "paid")
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["claire@example.com"])
        self.assertIn(self.kit.reference, message.subject)
        for text in ("Modèle 0", "1 rue de la Paix", "8 jours", "20 €", self.kit.credit_code):
            self.assertIn(text, message.body)
        self.pay()  # webhook replay: no second e-mail
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_documents_and_dashboard(self):
        self.pay()
        admin = User.objects.create_superuser("admin", "a@example.com", "pass-1234-xyz")
        self.client.force_login(admin)
        tasks = self.client.get(reverse("backoffice:tasks"), {"periode": "semaine"})
        self.assertContains(tasks, f"Préparer et expédier le coffret {self.kit.reference}")
        self.assertContains(tasks, "FAC-0, FAC-1, FAC-2, FAC-3")
        slip = self.client.get(reverse("backoffice:kit_packing_slip", args=[self.kit.pk]))
        for text in ("Bon d'envoi", "FAC-3", "ALL-3", "Modèle 3", "75002 Paris", "<svg class=\"barcode\""):
            self.assertContains(slip, text)
        label = self.client.get(reverse("backoffice:kit_return_label", args=[self.kit.pk]))
        self.assertContains(label, "Maison Alliance")  # shop address as recipient
        self.assertContains(label, "Claire Martin")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("backoffice:kit_packing_slip", args=[self.kit.pk])).status_code, 302)

    def test_shipping_email_with_return_label_and_deadline(self):
        self.pay()
        services.ship(self.kit, tracking_number="6A123456789")
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.fulfillment, "shipped")
        shipped = mail.outbox[-1]
        self.assertIn("en route", shipped.subject)
        self.assertIn("6A123456789", shipped.body)
        # 5. 8 days after (estimated) delivery = shipping + 2 + 8 days.
        self.assertEqual(self.kit.return_deadline, timezone.localdate() + timedelta(days=10))
        self.assertIn(self.kit.return_deadline.strftime("%Y"), shipped.body)
        label_url = services.return_label_url(self.kit)
        self.assertIn(label_url, shipped.body)
        response = self.client.get(label_url.replace("http://localhost:8000", ""))
        self.assertContains(response, self.kit.reference)
        self.assertEqual(self.client.get(reverse("trialkit:return_label", args=["forged"])).status_code, 404)

        services.mark_delivered(self.kit, when=timezone.now() + timedelta(days=1))
        self.assertEqual(self.kit.return_deadline, timezone.localdate() + timedelta(days=9))
        with self.assertRaises(services.KitTransitionError):
            services.ship(self.kit)

    def test_reminders_every_two_days_until_returned(self):
        self.pay()
        services.ship(self.kit)
        sent_before = len(mail.outbox)
        self.assertEqual(services.send_due_reminders(), 0)  # shipping e-mail just sent

        TrialKitOrder.objects.filter(pk=self.kit.pk).update(shipped_at=timezone.now() - timedelta(days=2))
        self.assertEqual(services.send_due_reminders(), 1)
        self.assertIn("Pensez à nous renvoyer", mail.outbox[-1].subject)
        self.assertEqual(services.send_due_reminders(), 0)  # not again the same day

        TrialKitOrder.objects.filter(pk=self.kit.pk).update(
            shipped_at=timezone.now() - timedelta(days=12), last_reminder_at=timezone.now() - timedelta(days=2)
        )
        self.assertEqual(services.send_due_reminders(), 1)
        self.assertIn("est attendu", mail.outbox[-1].subject)  # past the deadline
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.reminders_sent, 2)
        self.assertEqual(len(mail.outbox), sent_before + 2)

        services.receive(self.kit)
        TrialKitOrder.objects.filter(pk=self.kit.pk).update(last_reminder_at=timezone.now() - timedelta(days=5))
        self.assertEqual(services.send_due_reminders(), 0)

    def test_reminder_command(self):
        from django.core.management import call_command
        from io import StringIO

        self.pay()
        services.ship(self.kit)
        TrialKitOrder.objects.filter(pk=self.kit.pk).update(shipped_at=timezone.now() - timedelta(days=3))
        out = StringIO()
        call_command("send_kit_reminders", stdout=out)
        self.assertIn("1 relance", out.getvalue())

    @mock.patch("apps.orders.payments.stripe.Refund.create", return_value=mock.Mock(id="re_123"))
    def test_refund_20_after_check(self, refund_create):
        self.pay()
        with self.assertRaises(services.KitTransitionError):
            services.refund(self.kit)  # not back yet
        services.ship(self.kit)
        services.receive(self.kit)
        services.refund(self.kit)
        self.kit.refresh_from_db()
        refund_create.assert_called_once()
        self.assertEqual(refund_create.call_args.kwargs["payment_intent"], "pi_123")
        self.assertEqual(refund_create.call_args.kwargs["amount"], 2000)
        self.assertEqual((self.kit.fulfillment, self.kit.refund_id), ("refunded", "re_123"))
        self.assertIn("20 € remboursés", mail.outbox[-1].subject)
        with self.assertRaises(services.KitTransitionError):
            services.refund(self.kit)  # never twice
        self.assertEqual(refund_create.call_count, 1)

    @override_settings(STRIPE_DEMO_MODE=True)
    def test_refund_in_demo_mode_is_simulated(self):
        self.pay()
        services.ship(self.kit)
        services.receive(self.kit)
        services.refund(self.kit)
        self.assertTrue(self.kit.refund_id.startswith("demo_re_"))

    def test_task_list_actions_drive_the_lifecycle(self):
        self.pay()
        admin = User.objects.create_superuser("admin", "a@example.com", "pass-1234-xyz")
        self.client.force_login(admin)

        def act(action):
            self.client.post(reverse("backoffice:task_action"), {"action": action, "pk": self.kit.pk})
            self.kit.refresh_from_db()

        with override_settings(STRIPE_DEMO_MODE=True):
            act("kit_shipped")
            self.assertEqual(self.kit.fulfillment, "shipped")
            act("kit_delivered")
            act("kit_received")
            tasks = self.client.get(reverse("backoffice:tasks"))
            self.assertContains(tasks, f"Contrôler le coffret {self.kit.reference} et rembourser 20 €")
            act("kit_refund")
        self.assertEqual(self.kit.fulfillment, "refunded")
        self.assertEqual(
            [m.subject.split(" ")[0] for m in mail.outbox], ["Votre", "Votre", "Votre"]
        )  # confirmation, shipped, refunded


class CreditCodeTests(TestCase):
    def test_codes_are_unique(self):
        codes = {TrialKitOrder.objects.create(price=100).credit_code for _ in range(20)}
        self.assertEqual(len(codes), 20)

    def test_normalize_code(self):
        for raw in ("essai-abcd-efgh", "ESSAI ABCD EFGH", "abcdefgh", " Essai-ABCD-efgh "):
            self.assertEqual(normalize_code(raw), "ESSAI-ABCD-EFGH")
        self.assertEqual(normalize_code("ESSAI-ABC"), "")
        self.assertEqual(normalize_code(""), "")


class BarcodeTests(TestCase):
    def test_code128_structure(self):
        from .templatetags.barcode import code128_widths

        widths = code128_widths("A")
        self.assertTrue(widths.startswith("211214"))  # start B
        self.assertTrue(widths.endswith("2331112"))  # stop
        self.assertEqual(widths[6:12], "111323")  # "A"
        self.assertEqual(sum(map(int, widths)), 11 * 3 + 13)


@override_settings(**KIT_SETTINGS)
class KitAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "a@example.com", "pass-1234-xyz")
        self.client.force_login(self.admin)
        ring = make_ring(sku="ALL-1")
        self.sample = SampleRing.objects.create(reference="FAC-1", ring=ring, quantity=1)
        self.kit = paid_kit([self.sample])

    def test_stock_and_kit_pages(self):
        stock = self.client.get(reverse("admin:trialkit_samplering_changelist"))
        self.assertContains(stock, "0 — indisponible")
        kits = self.client.get(reverse("admin:trialkit_trialkitorder_changelist"))
        self.assertContains(kits, "FAC-1")
        change = self.client.get(reverse("admin:trialkit_trialkitorder_change", args=[self.kit.pk]))
        self.assertContains(change, "Étiquette retour")

    def test_admin_actions(self):
        url = reverse("admin:trialkit_trialkitorder_changelist")
        self.client.post(url, {"action": "action_ship", "_selected_action": [self.kit.pk]})
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.fulfillment, "shipped")
        self.assertIn("en route", mail.outbox[-1].subject)
        # Refusing an impossible step does not crash.
        response = self.client.post(url, {"action": "action_refund", "_selected_action": [self.kit.pk]}, follow=True)
        self.assertContains(response, "doit être reçu")
