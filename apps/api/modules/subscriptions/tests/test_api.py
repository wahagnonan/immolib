from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from modules.subscriptions.models import Subscription, SubscriptionTransaction

User = get_user_model()


class SubscriptionApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+2250700000401", password="password"
        )
        self.client.force_authenticate(self.user)

    def test_get_subscription_returns_free_plan(self):
        response = self.client.get("/api/v1/subscription/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"]["slug"], "free")
        self.assertEqual(response.data["max_houses"], 1)
        self.assertEqual(response.data["house_count"], 0)

    def test_get_subscription_creates_subscription_if_missing(self):
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())
        response = self.client.get("/api/v1/subscription/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Subscription.objects.filter(user=self.user).exists())

    def test_list_plans(self):
        response = self.client.get("/api/v1/subscription/plans/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [plan["slug"] for plan in response.data]
        self.assertEqual(slugs, ["free", "essential", "pro"])
        pro = next(plan for plan in response.data if plan["slug"] == "pro")
        self.assertEqual(pro["price_monthly"], 4000)
        self.assertEqual(pro["max_houses"], 15)

    def test_upgrade_pilot_activates_plan(self):
        response = self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "essential"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["activated"])
        self.assertIsNone(response.data["redirect_url"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription.plan.slug, "essential")

    def test_upgrade_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "pro"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_upgrade_unknown_plan_rejected(self):
        response = self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "platinum"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_subscription(self):
        self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "pro"},
            format="json",
        )
        response = self.client.post("/api/v1/subscription/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "CANCELLED")

    def test_cancel_free_plan_rejected(self):
        response = self.client.post("/api/v1/subscription/cancel/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("modules.subscriptions.services.paydunya.is_configured", return_value=True)
    @patch("modules.subscriptions.paydunya.create_checkout_invoice")
    def test_upgrade_with_paydunya_returns_redirect_url(
        self, mock_create_invoice, mock_configured
    ):
        mock_create_invoice.return_value = ("test_token", "https://paydunya/checkout")
        response = self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "pro"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["activated"])
        self.assertEqual(
            response.data["redirect_url"], "https://paydunya/checkout"
        )
        transaction = SubscriptionTransaction.objects.get(
            user=self.user, provider="PAYDUNYA"
        )
        self.assertEqual(transaction.provider_reference, "test_token")
        self.assertEqual(transaction.status, "PENDING")
        self.assertEqual(transaction.amount, 4000)
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription.plan.slug, "free")

    @patch("modules.subscriptions.services.paydunya.is_configured", return_value=True)
    @patch("modules.subscriptions.paydunya.confirm_invoice")
    @patch("modules.subscriptions.paydunya.create_checkout_invoice")
    def test_paydunya_webhook_activates_subscription(
        self, mock_create_invoice, mock_confirm, mock_configured
    ):
        mock_create_invoice.return_value = ("test_token", "https://paydunya/checkout")
        mock_confirm.return_value = "COMPLETED"
        self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "pro"},
            format="json",
        )
        response = self.client.post(
            "/api/v1/webhooks/paydunya/",
            {"invoice": {"token": "test_token"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["transaction_status"], "SUCCESSFUL")
        transaction = SubscriptionTransaction.objects.get(
            user=self.user, provider="PAYDUNYA"
        )
        self.assertEqual(transaction.status, "SUCCESSFUL")
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription.plan.slug, "pro")

    @patch("modules.subscriptions.services.paydunya.is_configured", return_value=True)
    @patch("modules.subscriptions.paydunya.confirm_invoice")
    @patch("modules.subscriptions.paydunya.create_checkout_invoice")
    def test_paydunya_webhook_cancel_keeps_plan(
        self, mock_create_invoice, mock_confirm, mock_configured
    ):
        mock_create_invoice.return_value = ("test_token", "https://paydunya/checkout")
        mock_confirm.return_value = "CANCELLED"
        self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "pro"},
            format="json",
        )
        response = self.client.post(
            "/api/v1/webhooks/paydunya/",
            {"invoice": {"token": "test_token"}},
            format="json",
        )
        self.assertEqual(response.data["transaction_status"], "CANCELLED")
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription.plan.slug, "free")

    @patch("modules.subscriptions.services.paydunya.is_configured", return_value=True)
    @patch("modules.subscriptions.paydunya.confirm_invoice")
    @patch("modules.subscriptions.paydunya.create_checkout_invoice")
    def test_paydunya_webhook_is_idempotent(
        self, mock_create_invoice, mock_confirm, mock_configured
    ):
        mock_create_invoice.return_value = ("test_token", "https://paydunya/checkout")
        mock_confirm.return_value = "COMPLETED"
        self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "pro"},
            format="json",
        )
        first = self.client.post(
            "/api/v1/webhooks/paydunya/",
            {"invoice": {"token": "test_token"}},
            format="json",
        )
        second = self.client.post(
            "/api/v1/webhooks/paydunya/",
            {"invoice": {"token": "test_token"}},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(
            SubscriptionTransaction.objects.filter(
                user=self.user, provider="PAYDUNYA", status="SUCCESSFUL"
            ).count(),
            1,
        )

    @patch("modules.subscriptions.services.paydunya.is_configured", return_value=True)
    @patch("modules.subscriptions.paydunya.confirm_invoice")
    @patch("modules.subscriptions.paydunya.create_checkout_invoice")
    def test_transaction_refresh_confirms_payment(
        self, mock_create_invoice, mock_confirm, mock_configured
    ):
        mock_create_invoice.return_value = ("test_token", "https://paydunya/checkout")
        mock_confirm.return_value = "COMPLETED"
        created = self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "essential"},
            format="json",
        )
        transaction_id = created.data["transaction"]["id"]
        response = self.client.get(
            f"/api/v1/subscription/transactions/{transaction_id}/refresh/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SUCCESSFUL")

    def test_anonymous_user_cannot_read_subscription(self):
        self.client.force_authenticate(None)
        response = self.client.get("/api/v1/subscription/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class HouseLimitApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+2250700000501", password="password"
        )
        self.client.force_authenticate(self.user)

    def _create_house(self, name: str):
        return self.client.post(
            "/api/v1/houses/",
            {
                "name": name,
                "address": "Yopougon",
                "commune": "Yopougon",
                "city": "Abidjan",
            },
            format="json",
        )

    def test_free_can_create_first_house(self):
        response = self._create_house("Maison 1")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_free_rejected_on_second_house_with_structured_error(self):
        self._create_house("Maison 1")
        response = self._create_house("Maison 2")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "HOUSE_LIMIT_REACHED")
        self.assertEqual(response.data["required_plan"], "essential")
        self.assertIn("limite de 1 bien", response.data["detail"])

    def test_essential_allows_up_to_five_houses(self):
        self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "essential"},
            format="json",
        )
        for index in range(5):
            response = self._create_house(f"Maison {index}")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self._create_house("Maison 6")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CoOwnerGateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+2250700000601", password="password"
        )
        self.client.force_authenticate(self.user)
        house_response = self.client.post(
            "/api/v1/houses/",
            {
                "name": "Maison 1",
                "address": "Cocody",
                "city": "Abidjan",
            },
            format="json",
        )
        self.house_id = house_response.data["id"]

    def test_free_cannot_invite_coowner(self):
        response = self.client.post(
            "/api/v1/co-owner-invitations/",
            {"house_id": self.house_id, "phone": "+2250700000699"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "FEATURE_NOT_AVAILABLE")
        self.assertEqual(response.data["feature"], "co_owners")
        self.assertEqual(response.data["required_plan"], "essential")

    def test_essential_can_invite_coowner(self):
        self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "essential"},
            format="json",
        )
        response = self.client.post(
            "/api/v1/co-owner-invitations/",
            {"house_id": self.house_id, "phone": "+2250700000699"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
