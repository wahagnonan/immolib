from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house


class RentChargeApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000400", password="password"
        )
        self.outsider = user_model.objects.create_user(
            phone="+2250700000401", password="password"
        )
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Anyama", address="Centre", city="Abidjan"
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Paul Yao", phone="+2250500000400"
            ),
        )
        lease = create_lease(
            actor=self.owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("75000"),
                due_day=5,
            ),
        )
        activate_lease(actor=self.owner, lease=lease)

    @patch("modules.billing.api.views.timezone.localdate")
    def test_owner_generates_and_lists_monthly_charge(self, localdate):
        localdate.return_value = date(2026, 7, 25)
        self.client.force_authenticate(self.owner)

        generate_response = self.client.post(
            "/api/v1/rent-charges/generate/",
            {"period": "2026-08"},
            format="json",
        )
        list_response = self.client.get("/api/v1/rent-charges/?period=2026-08")

        self.assertEqual(generate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(generate_response.data["created"], 1)
        self.assertEqual(generate_response.data["charges"][0]["amount_due"], "75000.00")
        self.assertEqual(len(list_response.data), 1)

    @patch("modules.billing.api.views.timezone.localdate")
    def test_outsider_cannot_generate_or_see_owner_charge(self, localdate):
        localdate.return_value = date(2026, 7, 25)
        self.client.force_authenticate(self.owner)
        self.client.post(
            "/api/v1/rent-charges/generate/",
            {"period": "2026-08"},
            format="json",
        )
        self.client.force_authenticate(self.outsider)

        generate_response = self.client.post(
            "/api/v1/rent-charges/generate/",
            {"period": "2026-08"},
            format="json",
        )
        list_response = self.client.get("/api/v1/rent-charges/")

        self.assertEqual(generate_response.data["created"], 0)
        self.assertEqual(generate_response.data["charges"], [])
        self.assertEqual(list_response.data, [])

    def test_invalid_period_format_is_rejected(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            "/api/v1/rent-charges/generate/",
            {"period": "08/2026"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("period", response.data)
