from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.billing.services import generate_monthly_charges
from modules.documents.models import RentalDocument
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house

from ..models import Payment


class OfflinePaymentApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000600", password="password"
        )
        self.outsider = user_model.objects.create_user(
            phone="+2250700000601", password="password"
        )
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Koumassi", address="Sicogi", city="Abidjan"
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Eric N'Guessan", phone="+2250500000600"
            ),
        )
        self.lease = create_lease(
            actor=self.owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("80000"),
                due_day=5,
                security_deposit=Decimal("200000"),
            ),
        )
        activate_lease(actor=self.owner, lease=self.lease)
        self.charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]
        self.received_at = timezone.make_aware(datetime(2026, 8, 4, 9, 0))

    def _payload(self, key):
        return {
            "rent_charge_id": str(self.charge.id),
            "amount": "30000.00",
            "method": "CASH",
            "received_at": self.received_at.isoformat(),
            "idempotency_key": str(key),
            "note": "Recu directement du locataire",
        }

    def test_owner_records_partial_payment_and_sees_balance(self):
        self.client.force_authenticate(self.owner)

        payment_response = self.client.post(
            "/api/v1/payments/", self._payload(uuid4()), format="json"
        )
        charge_response = self.client.get(
            f"/api/v1/rent-charges/{self.charge.id}/"
        )

        self.assertEqual(payment_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            payment_response.data["status"], Payment.Status.RECORDED_BY_OWNER
        )
        self.assertEqual(charge_response.data["amount_paid"], "30000.00")
        self.assertEqual(charge_response.data["balance_due"], "50000.00")
        self.assertEqual(charge_response.data["status"], "PARTIALLY_PAID")

    def test_api_retry_with_same_key_does_not_duplicate_payment(self):
        self.client.force_authenticate(self.owner)
        key = uuid4()

        first = self.client.post("/api/v1/payments/", self._payload(key), format="json")
        second = self.client.post("/api/v1/payments/", self._payload(key), format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Payment.objects.count(), 1)

    def test_outsider_cannot_view_or_record_payment(self):
        self.client.force_authenticate(self.owner)
        self.client.post("/api/v1/payments/", self._payload(uuid4()), format="json")
        self.client.force_authenticate(self.outsider)

        list_response = self.client.get("/api/v1/payments/")
        create_response = self.client.post(
            "/api/v1/payments/", self._payload(uuid4()), format="json"
        )

        self.assertEqual(list_response.data, [])
        self.assertEqual(create_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_cancels_payment_with_reason(self):
        self.client.force_authenticate(self.owner)
        created = self.client.post(
            "/api/v1/payments/", self._payload(uuid4()), format="json"
        )

        response = self.client.post(
            f"/api/v1/payments/{created.data['id']}/cancel/",
            {"reason": "Montant attribue au mauvais mois"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Payment.Status.CANCELLED)
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.amount_paid, Decimal("0"))

    def test_owner_pays_deposit_and_three_months_in_one_operation(self):
        self.client.force_authenticate(self.owner)
        prepared = self.client.post(
            "/api/v1/lease-obligations/prepare-payment/",
            {
                "lease_id": str(self.lease.id),
                "period_start": "2026-08",
                "period_end": "2026-10",
                "include_security_deposit": True,
            },
            format="json",
        )

        self.assertEqual(prepared.status_code, status.HTTP_200_OK)
        self.assertEqual(len(prepared.data["obligations"]), 4)
        allocations = [
            {
                "obligation_id": item["id"],
                "amount": item["balance_due"],
            }
            for item in prepared.data["obligations"]
        ]
        response = self.client.post(
            "/api/v1/payments/",
            {
                "amount": "440000.00",
                "allocations": allocations,
                "method": "CASH",
                "received_at": self.received_at.isoformat(),
                "idempotency_key": str(uuid4()),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["allocations"]), 4)
        self.assertEqual(
            RentalDocument.objects.filter(
                document_type=RentalDocument.Type.DEPOSIT_RECEIPT
            ).count(),
            1,
        )
        self.assertEqual(
            RentalDocument.objects.filter(
                document_type=RentalDocument.Type.RENT_RECEIPT
            ).count(),
            3,
        )
        payment_receipt = RentalDocument.objects.get(
            document_type=RentalDocument.Type.PAYMENT_RECEIPT
        )
        self.assertEqual(len(payment_receipt.breakdown), 4)
