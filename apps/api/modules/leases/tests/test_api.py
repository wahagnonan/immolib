from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from modules.properties.models import Ownership
from modules.properties.services import CreateHouseData, create_house

from ..models import Lease, Tenant


class TenantAndLeaseApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000200", password="password"
        )
        self.observer = user_model.objects.create_user(
            phone="+2250700000201", password="password"
        )
        self.outsider = user_model.objects.create_user(
            phone="+2250700000202", password="password"
        )
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Bingerville",
                address="Feh Kesse",
                city="Abidjan",
                commune="Bingerville",
            ),
        )
        Ownership.objects.create(
            property=self.house,
            user=self.observer,
            role=Ownership.Role.CO_OWNER,
            access_level=Ownership.AccessLevel.OBSERVER,
        )

    def _create_tenant(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/v1/tenants/",
            {
                "house_id": str(self.house.id),
                "full_name": "Moussa Kone",
                "phone": "+2250500000200",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def _create_lease(self, tenant_id):
        response = self.client.post(
            "/api/v1/leases/",
            {
                "house_id": str(self.house.id),
                "tenant_id": tenant_id,
                "start_date": "2026-07-01",
                "monthly_rent": "100000.00",
                "monthly_charges": "10000.00",
                "due_day": 5,
                "security_deposit": "200000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def test_owner_creates_tenant_then_draft_lease_then_activates_it(self):
        tenant = self._create_tenant()
        lease = self._create_lease(tenant["id"])

        self.assertEqual(tenant["status"], Tenant.Status.UNREGISTERED)
        self.assertEqual(lease["status"], Lease.Status.DRAFT)

        response = self.client.post(f"/api/v1/leases/{lease['id']}/activate/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Lease.Status.ACTIVE)
        self.house.refresh_from_db()
        self.assertEqual(self.house.status, "OCCUPIED")

    def test_observer_can_view_but_cannot_create_tenant(self):
        self._create_tenant()
        self.client.force_authenticate(self.observer)

        list_response = self.client.get("/api/v1/tenants/")
        create_response = self.client.post(
            "/api/v1/tenants/",
            {
                "house_id": str(self.house.id),
                "full_name": "Awa Traore",
                "phone": "+2250500000201",
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(create_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_outsider_cannot_see_tenants_or_leases(self):
        tenant = self._create_tenant()
        self._create_lease(tenant["id"])
        self.client.force_authenticate(self.outsider)

        tenants_response = self.client.get("/api/v1/tenants/")
        leases_response = self.client.get("/api/v1/leases/")

        self.assertEqual(tenants_response.data, [])
        self.assertEqual(leases_response.data, [])

    def test_invalid_due_day_is_rejected(self):
        tenant = self._create_tenant()

        response = self.client.post(
            "/api/v1/leases/",
            {
                "house_id": str(self.house.id),
                "tenant_id": tenant["id"],
                "start_date": "2026-07-01",
                "monthly_rent": "100000.00",
                "due_day": 31,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("due_day", response.data)

    def test_owner_can_close_active_lease(self):
        tenant = self._create_tenant()
        lease = self._create_lease(tenant["id"])
        self.client.post(f"/api/v1/leases/{lease['id']}/activate/")

        response = self.client.post(f"/api/v1/leases/{lease['id']}/close/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Lease.Status.ENDED)
        self.house.refresh_from_db()
        self.assertEqual(self.house.status, "VACANT")
