from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.payments.models import Payment
from modules.payments.services import RecordOfflinePaymentData, record_offline_payment
from modules.properties.services import CreateHouseData, create_house

from ..services import generate_monthly_charges


class DashboardOverviewApiTests(APITestCase):
    def test_overview_returns_aggregates_and_small_lists(self):
        owner = get_user_model().objects.create_user(
            phone="+2250700002800",
            password="password",
        )
        house = create_house(
            owner=owner,
            data=CreateHouseData(
                name="Maison Synthèse",
                address="Marcory",
                city="Abidjan",
            ),
        )
        tenant = create_tenant(
            actor=owner,
            property=house,
            data=CreateTenantData(
                full_name="Fatou Bamba",
                phone="+2250500002800",
            ),
        )
        current_month = timezone.localdate().replace(day=1)
        lease = create_lease(
            actor=owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=current_month,
                monthly_rent=Decimal("100000"),
                due_day=min(timezone.localdate().day, 28),
            ),
        )
        activate_lease(actor=owner, lease=lease)
        charge = generate_monthly_charges(
            actor=owner,
            period_start=current_month,
            today=timezone.localdate(),
        ).charges[0]
        record_offline_payment(
            actor=owner,
            charge=charge,
            data=RecordOfflinePaymentData(
                amount=Decimal("40000"),
                method=Payment.Method.CASH,
                idempotency_key=uuid4(),
                received_at=timezone.now(),
            ),
        )
        self.client.force_authenticate(owner)

        response = self.client.get("/api/v1/dashboard/overview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["houses"]["total"], 1)
        self.assertEqual(response.data["collection"]["expected"], "100000")
        self.assertEqual(response.data["collection"]["collected"], "40000")
        self.assertEqual(response.data["collection"]["remaining"], "60000")
        self.assertEqual(len(response.data["monthly_collection"]), 6)
        self.assertEqual(len(response.data["priority_charges"]), 1)
        self.assertEqual(len(response.data["recent_payments"]), 1)
