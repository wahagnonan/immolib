from django.test import TestCase, override_settings
from django.urls import reverse

from modules.sms.models import SmsDeliveryReceipt

from .helpers import build_delivery, dr_payload

WEBHOOK_URL = reverse("sms-orange-dr-webhook")


@override_settings(ORANGE_SMS_DR_ALLOWED_IPS=("127.0.0.1",))
class OrangeSmsDeliveryReceiptWebhookTests(TestCase):
    def setUp(self):
        self.delivery = build_delivery()
        self.delivery.provider_reference = "resource-ABC"
        self.delivery.save()

    def test_webhook_503_when_not_configured(self):
        with override_settings(ORANGE_SMS_DR_ALLOWED_IPS=()):
            response = self.client.post(
                WEBHOOK_URL, dr_payload(), content_type="application/json"
            )

        self.assertEqual(response.status_code, 503)

    def test_webhook_403_for_ip_not_in_whitelist(self):
        with override_settings(ORANGE_SMS_DR_ALLOWED_IPS=("10.0.0.1",)):
            response = self.client.post(
                WEBHOOK_URL, dr_payload(), content_type="application/json"
            )

        self.assertEqual(response.status_code, 403)

    def test_webhook_accepts_delivery_receipt_and_correlates(self):
        response = self.client.post(
            WEBHOOK_URL, dr_payload(), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        received = response.json()["received"]
        self.assertTrue(received["created"])
        self.assertTrue(received["correlated"])
        self.assertEqual(received["message_id"], "resource-ABC")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, "DELIVERED")
        self.assertIsNotNone(self.delivery.delivered_at)

    def test_webhook_duplicate_delivery_receipt_is_idempotent(self):
        first = self.client.post(
            WEBHOOK_URL, dr_payload(), content_type="application/json"
        )
        second = self.client.post(
            WEBHOOK_URL, dr_payload(), content_type="application/json"
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["received"]["created"])
        self.assertEqual(SmsDeliveryReceipt.objects.count(), 1)

    def test_webhook_rejects_invalid_payload(self):
        response = self.client.post(
            WEBHOOK_URL,
            {"deliveryInfoNotification": {}},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_webhook_failure_does_not_downgrade_delivered(self):
        self.client.post(
            WEBHOOK_URL, dr_payload(), content_type="application/json"
        )
        response = self.client.post(
            WEBHOOK_URL,
            dr_payload(status="DeliveryImpossible"),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, "DELIVERED")
