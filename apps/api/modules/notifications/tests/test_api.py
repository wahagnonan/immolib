from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import NotificationPreference, PushSubscription


class NotificationPreferenceApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            phone="+2250700001200",
            email="awa@example.com",
            email_verified_at=timezone.now(),
            password="password",
        )
        self.client.force_authenticate(self.user)

    def test_defaults_are_cost_aware(self):
        response = self.client.get("/api/v1/notification-preferences/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["push_enabled"])
        self.assertTrue(response.data["email_enabled"])
        self.assertFalse(response.data["whatsapp_enabled"])
        self.assertFalse(response.data["sms_enabled"])
        self.assertEqual(response.data["available_channels"], ["EMAIL"])

    def test_whatsapp_requires_explicit_opt_in(self):
        rejected = self.client.patch(
            "/api/v1/notification-preferences/",
            {"whatsapp_enabled": True},
            format="json",
        )
        accepted = self.client.patch(
            "/api/v1/notification-preferences/",
            {"whatsapp_enabled": True, "whatsapp_opt_in": True},
            format="json",
        )

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertIsNotNone(preference.whatsapp_opted_in_at)
        self.assertIn("WHATSAPP", accepted.data["available_channels"])

    def test_push_token_can_be_registered_and_deactivated(self):
        created = self.client.post(
            "/api/v1/push-subscriptions/",
            {"token": "fcm-token-browser-123456", "device_name": "Chrome Android"},
            format="json",
        )
        listed = self.client.get("/api/v1/push-subscriptions/")
        deleted = self.client.delete(
            "/api/v1/push-subscriptions/",
            {"token": "fcm-token-browser-123456"},
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["token_suffix"], "123456")
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PushSubscription.objects.get().is_active)
