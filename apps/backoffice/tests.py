from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.pricing.models import GoldPrice
from apps.pricing.tests import make_ring
from apps.trialkit.models import TrialKitOrder

from .models import Task
from .services import build_tasks


@override_settings(TRIAL_KIT_RETURN_DAYS=8, TRIAL_KIT_DELIVERY_DAYS=2, STRIPE_DEMO_MODE=True)
class TaskListTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass-1234-xyz")
        self.client.force_login(self.admin)
        self.today = timezone.localdate()
        self.now = timezone.now()
        GoldPrice.objects.create(price_per_oz_eur=Decimal("3000"), source="test")
        self.ring = make_ring(lead_time_days=10)

    def titles(self, period):
        return [task.title for task in build_tasks(period)]

    def test_requires_staff(self):
        self.client.logout()
        response = self.client.get(reverse("backoffice:tasks"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_manual_tasks_by_period(self):
        Task.objects.create(title="En retard", due_date=self.today - timedelta(days=2))
        Task.objects.create(title="Aujourd'hui", due_date=self.today)
        Task.objects.create(title="Dans 3 jours", due_date=self.today + timedelta(days=3))
        Task.objects.create(title="Dans 10 jours", due_date=self.today + timedelta(days=10))
        Task.objects.create(title="Déjà faite", due_date=self.today, is_done=True)
        self.assertEqual(self.titles("jour"), ["En retard", "Aujourd'hui"])
        self.assertEqual(self.titles("semaine"), ["En retard", "Aujourd'hui", "Dans 3 jours"])
        self.assertTrue(build_tasks("jour")[0].overdue)

    def test_automatic_tasks(self):
        kit = TrialKitOrder.objects.create(price=80, status="paid", paid_at=self.now - timedelta(days=1), full_name="Claire")
        TrialKitOrder.objects.create(price=80, status="pending")  # unpaid: no task
        returned_soon = TrialKitOrder.objects.create(
            price=80, status="paid", paid_at=self.now, fulfillment="shipped", shipped_at=self.now - timedelta(days=5)
        )
        order = Order.objects.create(total=500, gold_spot_eur_per_oz=3000, status="paid", paid_at=self.now)
        OrderItem.objects.create(order=order, ring=self.ring, ring_name="Test", size=54, unit_price=500, weight_g=4)
        in_production = Order.objects.create(
            total=500, gold_spot_eur_per_oz=3000, status="paid", paid_at=self.now - timedelta(days=5),
            fulfillment="in_production",
        )
        OrderItem.objects.create(order=in_production, ring=self.ring, ring_name="Test", size=54, unit_price=500, weight_g=4)

        day = self.titles("jour")
        self.assertIn(f"Préparer et expédier le coffret {kit.reference}", day)
        self.assertIn(f"Lancer la fabrication de la commande {order.reference}", day)
        self.assertNotIn(f"Réceptionner le retour du coffret {returned_soon.reference}", day)
        week = self.titles("semaine")
        # Shipped 5 days ago + 2 delivery days + 8 days to send it back → due in 5 days.
        self.assertIn(f"Réceptionner le retour du coffret {returned_soon.reference}", week)
        # Paid 5 days ago, 10-day lead time, 2 shipping days → ship by in 3 days.
        self.assertEqual(in_production.ship_by, self.today + timedelta(days=3))
        self.assertIn(f"Expédier la commande {in_production.reference}", week)
        self.assertNotIn(f"Expédier la commande {in_production.reference}", day)

    def test_stale_gold_price_task(self):
        self.assertNotIn("Mettre à jour le cours de l'or (paiements suspendus)", self.titles("jour"))
        GoldPrice.objects.update(fetched_at=self.now - timedelta(days=3))
        self.assertIn("Mettre à jour le cours de l'or (paiements suspendus)", self.titles("jour"))

    def test_page_and_quick_add(self):
        response = self.client.post(
            reverse("backoffice:tasks") + "?periode=semaine",
            {"title": "Appeler le sertisseur", "due_date": self.today.isoformat(), "priority": "high"},
        )
        self.assertRedirects(response, reverse("backoffice:tasks") + "?periode=semaine")
        response = self.client.get(reverse("backoffice:tasks"), {"periode": "semaine"})
        self.assertContains(response, "Tâches de la semaine")
        self.assertContains(response, "Appeler le sertisseur")
        self.assertEqual(self.client.get(reverse("backoffice:tasks"), {"periode": "x"}).context["period"], "jour")

    def act(self, action, pk, next_url=""):
        return self.client.post(reverse("backoffice:task_action"), {"action": action, "pk": pk, "next": next_url})

    def test_actions(self):
        task = Task.objects.create(title="À faire")
        kit = TrialKitOrder.objects.create(price=80, status="paid", paid_at=self.now)
        order = Order.objects.create(total=500, gold_spot_eur_per_oz=3000, status="paid", paid_at=self.now)

        self.act("task_done", task.pk)
        self.act("kit_shipped", kit.pk)
        self.act("order_production", order.pk)
        task.refresh_from_db(); kit.refresh_from_db(); order.refresh_from_db()
        self.assertTrue(task.is_done and task.done_at)
        self.assertEqual((kit.fulfillment, bool(kit.shipped_at)), ("shipped", True))
        self.assertEqual(order.fulfillment, "in_production")

        self.act("kit_received", kit.pk)
        self.act("kit_refund", kit.pk)  # nothing to refund on this kit: just validates the check
        self.act("order_shipped", order.pk)
        kit.refresh_from_db(); order.refresh_from_db()
        self.assertEqual((kit.fulfillment, order.fulfillment), ("refunded", "shipped"))
        self.assertEqual(self.titles("semaine"), [])

    def test_action_redirects_only_to_safe_urls(self):
        task = Task.objects.create(title="À faire")
        response = self.act("task_done", task.pk, "https://evil.example.com/")
        self.assertRedirects(response, reverse("backoffice:tasks"))
        self.assertRedirects(self.act("nope", 1, "/admin/"), "/admin/", fetch_redirect_response=False)

    def test_action_requires_post(self):
        self.assertEqual(self.client.get(reverse("backoffice:task_action")).status_code, 405)

    def test_dashboard(self):
        Task.objects.create(title="Aujourd'hui")
        Order.objects.create(total=Decimal("1200"), gold_spot_eur_per_oz=3000, status="paid", paid_at=self.now)
        response = self.client.get(reverse("admin:index"))
        for text in ("Tâches du jour", "Tâches de la semaine", "Commandes à traiter", "Chiffre d'affaires du mois", "€/g"):
            self.assertContains(response, text)
        self.assertRegex(response.content.decode(), r"1\D?200 €")  # revenue of the month
