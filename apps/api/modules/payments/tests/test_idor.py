"""Matrice IDOR cross-tenant : paiements, demandes P2P, comptes de reception, cautions."""

from decimal import Decimal
from uuid import uuid4

from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.tests.idor_fixtures import make_estate, make_landlord
from modules.payments.models import Payment, PaymentMethodAccount, PaymentRequest


class EstateIdorBase(APITestCase):
    def setUp(self):
        self.landlord_a = make_landlord("+2250700001501")
        self.landlord_b = make_landlord("+2250700001502")
        self.estate_b = make_estate(
            owner=self.landlord_b,
            name="Villa B",
            tenant_phone="+2250500001502",
            coowner_phone="+2250100001502",
        )
        self.method_account_b = PaymentMethodAccount.objects.create(
            owner=self.landlord_b,
            operator=PaymentMethodAccount.Operator.ORANGE_MONEY,
            account_identifier="+2250700001509",
            account_holder="Bailleur B",
        )
        self.client.force_authenticate(self.landlord_a)


class PaymentIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_payment_of_b(self):
        response = self.client.get(f"/api/v1/payments/{self.estate_b.payment.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_update_payment_of_b(self):
        response = self.client.patch(
            f"/api/v1/payments/{self.estate_b.payment.id}/",
            {"amount": "1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_cannot_cancel_payment_of_b(self):
        response = self.client.post(
            f"/api/v1/payments/{self.estate_b.payment.id}/cancel/",
            {"reason": "Pirate"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.estate_b.payment.refresh_from_db()
        self.assertEqual(
            self.estate_b.payment.status, Payment.Status.RECORDED_BY_OWNER
        )

    def test_a_list_excludes_payments_of_b(self):
        response = self.client.get("/api/v1/payments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.payment.id),
            [str(p["id"]) for p in response.data["results"]],
        )

    def test_a_cannot_record_payment_on_charge_of_b(self):
        response = self.client.post(
            "/api/v1/payments/",
            {
                "rent_charge_id": str(self.estate_b.unpaid_charge.id),
                "amount": "10000.00",
                "method": "CASH",
                "idempotency_key": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Payment.objects.count(), 1)

    def test_a_cannot_record_allocations_on_charge_of_b(self):
        response = self.client.post(
            "/api/v1/payments/",
            {
                "amount": "10000.00",
                "method": "CASH",
                "idempotency_key": str(uuid4()),
                "allocations": [
                    {
                        "obligation_id": str(self.estate_b.unpaid_charge.id),
                        "amount": "10000.00",
                    }
                ],
            },
            format="json",
        )
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND))
        self.assertEqual(Payment.objects.count(), 1)


class PaymentRequestIdorTests(EstateIdorBase):
    def test_a_cannot_list_payment_requests_of_b(self):
        response = self.client.get("/api/v1/payment-requests/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.payment_request.id),
            [str(r["id"]) for r in response.data["results"]],
        )

    def test_a_cannot_confirm_payment_request_of_b(self):
        response = self.client.post(
            f"/api/v1/payment-requests/{self.estate_b.payment_request.id}/confirm/",
            {"received_amount": "50000.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.estate_b.payment_request.refresh_from_db()
        self.assertEqual(self.estate_b.payment_request.status, PaymentRequest.Status.PENDING)

    def test_a_cannot_refuse_payment_request_of_b(self):
        response = self.client.post(
            f"/api/v1/payment-requests/{self.estate_b.payment_request.id}/refuse/",
            {"reason": "Pirate"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_of_a_cannot_cancel_request_of_b(self):
        tenant_a = make_landlord("+2250500001501")
        self.client.force_authenticate(tenant_a)
        response = self.client.post(
            f"/api/v1/payment-requests/{self.estate_b.payment_request.id}/cancel/",
            {"reason": "Pirate"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.estate_b.payment_request.refresh_from_db()
        self.assertEqual(self.estate_b.payment_request.status, PaymentRequest.Status.PENDING)

    def test_tenant_of_a_cannot_create_request_on_charge_of_b(self):
        outsider_tenant = make_landlord("+2250500001503")
        self.client.force_authenticate(outsider_tenant)
        response = self.client.post(
            "/api/v1/payment-requests/",
            {
                "rent_charge_id": str(self.estate_b.unpaid_charge.id),
                "amount": "10000.00",
                "operator": "ORANGE_MONEY",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PaymentMethodAccountIdorTests(EstateIdorBase):
    def test_a_cannot_delete_account_of_b(self):
        response = self.client.delete(
            f"/api/v1/payment-methods/{self.method_account_b.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            PaymentMethodAccount.objects.filter(id=self.method_account_b.id).exists()
        )

    def test_a_cannot_make_account_of_b_default(self):
        response = self.client.post(
            f"/api/v1/payment-methods/{self.method_account_b.id}/make-default/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_list_excludes_accounts_of_b(self):
        response = self.client.get("/api/v1/payment-methods/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.method_account_b.id),
            [str(a["id"]) for a in response.data],
        )

    def test_a_tenant_cannot_use_account_of_another_landlord_for_request(self):
        from datetime import date

        from modules.billing.services import generate_monthly_charges

        self.client.force_authenticate(self.landlord_a)
        october_charge = generate_monthly_charges(
            actor=self.landlord_b,
            period_start=date(2026, 10, 1),
            today=date(2026, 9, 25),
        ).charges[0]
        account_a = PaymentMethodAccount.objects.create(
            owner=self.landlord_a,
            operator=PaymentMethodAccount.Operator.ORANGE_MONEY,
            account_identifier="+2250700001510",
            account_holder="Bailleur A",
        )
        self.client.force_authenticate(self.estate_b.tenant_user)
        response = self.client.post(
            "/api/v1/payment-requests/",
            {
                "rent_charge_id": str(october_charge.id),
                "amount": "10000.00",
                "operator": "ORANGE_MONEY",
                "method_account_id": str(account_a.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SecurityDepositIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_deposit_of_b(self):
        response = self.client.get(
            f"/api/v1/security-deposits/{self.estate_b.deposit_obligation.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_settle_deposit_of_b(self):
        response = self.client.post(
            f"/api/v1/security-deposits/{self.estate_b.deposit_obligation.id}/settle/",
            {
                "movement_type": "REFUND",
                "amount": "50000.00",
                "idempotency_key": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_list_excludes_deposits_of_b(self):
        response = self.client.get("/api/v1/security-deposits/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.deposit_obligation.id),
            [str(d["id"]) for d in response.data["results"]],
        )

    def test_a_cannot_settle_deposit_against_own_target_charge_of_b(self):
        response = self.client.post(
            f"/api/v1/security-deposits/{self.estate_b.deposit_obligation.id}/settle/",
            {
                "movement_type": "APPLY_TO_RENT",
                "amount": "50000.00",
                "agreement_confirmed": True,
                "target_rent_charge_id": str(self.estate_b.unpaid_charge.id),
                "idempotency_key": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
