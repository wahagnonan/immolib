from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from modules.accounts.models import AccountOtpChallenge
from modules.documents.models import NotificationDelivery


class ServiceHealthTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            phone="+2250707070707", password="motdepasse-test"
        )
        self.challenge = AccountOtpChallenge.objects.create(
            user=user,
            purpose=AccountOtpChallenge.Purpose.EMAIL_VERIFICATION,
            channel=AccountOtpChallenge.Channel.EMAIL,
            destination="locataire@example.com",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def _delivery(self, **overrides):
        defaults = {
            "kind": NotificationDelivery.Kind.ACCOUNT_OTP,
            "account_challenge": self.challenge,
            "channel": NotificationDelivery.Channel.EMAIL,
            "destination": "locataire@example.com",
            "subject": "Code",
            "body": "Code de verification",
        }
        defaults.update(overrides)
        return NotificationDelivery.objects.create(**defaults)

    def test_healthy_when_database_ok_and_queue_empty(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"]["database"]["status"], "ok")
        self.assertEqual(
            payload["checks"]["notification_queue"]["status"], "ok"
        )

    def test_stuck_notification_without_adapter_degrades_health(self):
        delivery = self._delivery()
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            created_at=timezone.now() - timedelta(minutes=30)
        )
        with self.settings(NOTIFICATION_ADAPTERS={}):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 503)
        queue = response.json()["checks"]["notification_queue"]
        self.assertEqual(queue["status"], "degraded")
        self.assertEqual(queue["queued_without_adapter_since_cutoff"], 1)

    def test_queued_delivery_covered_by_adapter_is_not_stuck(self):
        self._delivery()
        with self.settings(
            NOTIFICATION_ADAPTERS={
                "EMAIL": "modules.documents.notifications.SimulatedNotificationAdapter"
            }
        ):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["checks"]["notification_queue"][
                "queued_without_adapter_since_cutoff"
            ],
            0,
        )

    def test_fresh_queued_delivery_does_not_alert(self):
        self._delivery(channel=NotificationDelivery.Channel.PUSH)
        with self.settings(NOTIFICATION_ADAPTERS={}):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
