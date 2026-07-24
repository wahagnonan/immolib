from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from modules.documents.models import RentalDocument
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house

from ..models import Payment, SecurityDepositMovement


class SecurityDepositLifecycleApiTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            phone="+2250700002600",
            password="password",
        )
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Caution",
                address="Cocody",
                city="Abidjan",
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Aminata Kone",
                phone="+2250500002600",
            ),
        )
        self.lease = create_lease(
            actor=self.owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("100000"),
                due_day=5,
                security_deposit=Decimal("200000"),
            ),
        )
        activate_lease(actor=self.owner, lease=self.lease)
        self.client.force_authenticate(self.owner)
        prepared = self.client.post(
            "/api/v1/lease-obligations/prepare-payment/",
            {
                "lease_id": str(self.lease.id),
                "period_start": "2026-08",
                "period_end": "2026-08",
                "include_security_deposit": True,
            },
            format="json",
        )
        obligations = prepared.data["obligations"]
        self.deposit = next(
            item for item in obligations if item["obligation_type"] == "SECURITY_DEPOSIT"
        )
        self.rent = next(
            item for item in obligations if item["obligation_type"] == "RENT"
        )
        paid = self.client.post(
            "/api/v1/payments/",
            {
                "amount": self.deposit["amount_due"],
                "rent_charge_id": self.deposit["id"],
                "method": "BANK_TRANSFER",
                "idempotency_key": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(paid.status_code, status.HTTP_201_CREATED)

    def _settle(self, **overrides):
        payload = {
            "movement_type": "REFUND",
            "amount": "50000.00",
            "idempotency_key": str(uuid4()),
            **overrides,
        }
        return self.client.post(
            f"/api/v1/security-deposits/{self.deposit['id']}/settle/",
            payload,
            format="json",
        )

    def test_refund_reduces_held_balance_and_creates_statement(self):
        response = self._settle(reason="Virement effectué au locataire")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["held_balance"], "150000.00")
        self.assertEqual(response.data["amount_released"], "50000.00")
        movement = SecurityDepositMovement.objects.get()
        self.assertEqual(movement.movement_type, SecurityDepositMovement.Type.REFUND)
        self.assertTrue(
            RentalDocument.objects.filter(
                deposit_movement=movement,
                document_type=RentalDocument.Type.DEPOSIT_SETTLEMENT,
            ).exists()
        )

    def test_retention_requires_a_reason(self):
        response = self._settle(movement_type="RETENTION", reason="")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)

    def test_explicit_agreement_can_apply_deposit_to_rent_without_new_cash(self):
        response = self._settle(
            movement_type="APPLY_TO_RENT",
            amount="100000.00",
            target_rent_charge_id=self.rent["id"],
            agreement_confirmed=True,
            agreement_reference="AVENANT-2026-07-24",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(
            method=Payment.Method.SECURITY_DEPOSIT_APPLICATION
        )
        self.assertFalse(payment.is_cash_movement)
        self.assertEqual(payment.status, Payment.Status.CONFIRMED_BY_TENANT)
        self.assertEqual(response.data["held_balance"], "100000.00")
        rent_response = self.client.get(
            f"/api/v1/rent-charges/{self.rent['id']}/"
        )
        self.assertEqual(rent_response.data["status"], "PAID")

    def test_collected_deposit_cannot_be_cancelled_after_a_release(self):
        self._settle(reason="Remboursement partiel")
        deposit_payment = Payment.objects.get(
            allocations__rent_charge_id=self.deposit["id"]
        )

        response = self.client.post(
            f"/api/v1/payments/{deposit_payment.id}/cancel/",
            {"reason": "Tentative de correction tardive"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Payment.objects.get(id=deposit_payment.id).status,
            Payment.Status.RECORDED_BY_OWNER,
        )
