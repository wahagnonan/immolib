from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from modules.leases.models import Tenant
from modules.notifications.models import NotificationPreference
from modules.notifications.services import (
    available_routes_for_user,
    register_push_subscription,
)
from modules.properties.services import CreateHouseData, create_house


class NotificationRoutingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            phone="+2250700001300",
            email="tenant@example.com",
            email_verified_at=timezone.now(),
            password="password",
        )

    def test_push_precedes_email_then_sms_is_opt_in_only(self):
        register_push_subscription(
            user=self.user,
            token="fcm-routing-token",
            device_name="Téléphone",
        )

        routes = available_routes_for_user(self.user)

        self.assertEqual([route.channel for route in routes], ["PUSH", "EMAIL"])

    def test_explicit_preference_moves_available_channel_first(self):
        preference = NotificationPreference.objects.create(
            user=self.user,
            preferred_channel=NotificationPreference.PreferredChannel.EMAIL,
            sms_enabled=True,
        )

        routes = available_routes_for_user(self.user)

        self.assertEqual(routes[0].channel, "EMAIL")
        self.assertEqual(routes[1].channel, "SMS")
