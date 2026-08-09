from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from modules.subscriptions import paydunya
from modules.subscriptions.models import SubscriptionTransaction
from modules.subscriptions.services import upgrade

User = get_user_model()


class PayDunyaAdapterTests(TestCase):
    def test_is_configured_false_without_keys(self):
        self.assertFalse(paydunya.is_configured())

    def test_is_configured_true_with_keys(self):
        with override_settings(
            PAYDUNYA_MASTER_KEY="mk",
            PAYDUNYA_PRIVATE_KEY="pk",
            PAYDUNYA_TOKEN="tk",
        ):
            self.assertTrue(paydunya.is_configured())

    def test_confirm_invoice_status_mapping(self):
        with patch("modules.subscriptions.paydunya._request") as mock_request:
            mock_request.return_value = {
                "response_code": "00",
                "status": "completed",
            }
            self.assertEqual(
                paydunya.confirm_invoice("token-x"), "COMPLETED"
            )
            mock_request.return_value = {"response_code": "00", "status": "canceled"}
            self.assertEqual(paydunya.confirm_invoice("token-x"), "CANCELLED")
            mock_request.return_value = {"response_code": "00", "status": "pending"}
            self.assertEqual(paydunya.confirm_invoice("token-x"), "PENDING")


class PayDunyaUpgradeFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+2250700000701", password="password"
        )

    @patch("modules.subscriptions.services.paydunya.is_configured", return_value=True)
    @patch("modules.subscriptions.paydunya.create_checkout_invoice")
    def test_upgrade_creates_pending_transaction(self, mock_create, mock_configured):
        mock_create.return_value = ("token-1", "https://paydunya/checkout/1")
        result = upgrade(self.user, "pro")
        self.assertFalse(result.activated)
        self.assertEqual(result.transaction.status, "PENDING")
        self.assertEqual(result.transaction.provider, "PAYDUNYA")
        self.assertEqual(result.transaction.provider_reference, "token-1")
        self.assertEqual(result.transaction.amount, 4000)
        self.assertEqual(
            result.redirect_url, "https://paydunya/checkout/1"
        )

    @patch("modules.subscriptions.services.paydunya.is_configured", return_value=True)
    @patch("modules.subscriptions.paydunya.create_checkout_invoice")
    def test_payment_amount_always_comes_from_server(self, mock_create, mock_configured):
        mock_create.return_value = ("token-2", "https://paydunya/checkout/2")
        upgrade(self.user, "essential")
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["total_amount"], 2000)

    def test_transaction_statuses_cover_required_lifecycle(self):
        expected = {
            "PENDING",
            "SUCCESSFUL",
            "FAILED",
            "CANCELLED",
            "EXPIRED",
        }
        self.assertEqual(
            expected,
            {choice[0] for choice in SubscriptionTransaction.Status.choices},
        )
