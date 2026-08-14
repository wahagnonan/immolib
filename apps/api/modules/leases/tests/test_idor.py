"""Matrice IDOR cross-tenant : locataires, baux, invitations locataires."""

from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.tests.idor_fixtures import make_estate, make_landlord
from modules.leases.models import Lease, Tenant
from modules.leases.services import (
    CreateTenantData,
    create_tenant,
    create_tenant_invitation,
)
from modules.properties.services import CreateHouseData, create_house


class EstateIdorBase(APITestCase):
    def setUp(self):
        self.landlord_a = make_landlord("+2250700001301")
        self.landlord_b = make_landlord("+2250700001302")
        self.estate_b = make_estate(
            owner=self.landlord_b,
            name="Villa B",
            tenant_phone="+2250500001302",
            coowner_phone="+2250100001302",
        )
        self.unlinked_tenant = create_tenant(
            actor=self.landlord_b,
            property=self.estate_b.house,
            data=CreateTenantData(
                full_name="Locataire sans compte",
                phone="+2250500001303",
            ),
        )
        self.tenant_invitation = create_tenant_invitation(
            actor=self.landlord_b, tenant=self.unlinked_tenant
        )
        self.client.force_authenticate(self.landlord_a)


class TenantIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_tenant_of_b(self):
        response = self.client.get(f"/api/v1/tenants/{self.estate_b.tenant.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_update_tenant_of_b(self):
        response = self.client.patch(
            f"/api/v1/tenants/{self.estate_b.tenant.id}/",
            {"full_name": "Piraté"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_cannot_delete_tenant_of_b(self):
        response = self.client.delete(f"/api/v1/tenants/{self.estate_b.tenant.id}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_list_excludes_tenants_of_b(self):
        response = self.client.get("/api/v1/tenants/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.tenant.id), [str(t["id"]) for t in response.data]
        )

    def test_a_cannot_create_tenant_on_house_of_b(self):
        response = self.client.post(
            "/api/v1/tenants/",
            {
                "house_id": str(self.estate_b.house.id),
                "full_name": "Intrus",
                "phone": "+2250500001399",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LeaseIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_lease_of_b(self):
        response = self.client.get(f"/api/v1/leases/{self.estate_b.lease.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_update_lease_of_b(self):
        response = self.client.patch(
            f"/api/v1/leases/{self.estate_b.lease.id}/",
            {"monthly_rent": "1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_list_excludes_leases_of_b(self):
        response = self.client.get("/api/v1/leases/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.lease.id), [str(l["id"]) for l in response.data]
        )

    def test_a_cannot_activate_lease_of_b(self):
        self.estate_b.lease.status = Lease.Status.DRAFT
        self.estate_b.lease.save(update_fields=["status"])
        response = self.client.post(
            f"/api/v1/leases/{self.estate_b.lease.id}/activate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.estate_b.lease.refresh_from_db()
        self.assertEqual(self.estate_b.lease.status, Lease.Status.DRAFT)

    def test_a_cannot_close_lease_of_b(self):
        response = self.client.post(
            f"/api/v1/leases/{self.estate_b.lease.id}/close/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.estate_b.lease.refresh_from_db()
        self.assertEqual(self.estate_b.lease.status, Lease.Status.ACTIVE)

    def test_a_cannot_create_lease_on_house_of_b(self):
        response = self.client.post(
            "/api/v1/leases/",
            {
                "house_id": str(self.estate_b.house.id),
                "tenant_id": str(self.estate_b.tenant.id),
                "start_date": "2026-10-01",
                "monthly_rent": "50000",
                "due_day": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TenantInvitationIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_invitation_of_b(self):
        response = self.client.get(
            f"/api/v1/tenant-invitations/{self.tenant_invitation.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_share_invitation_of_b(self):
        response = self.client.post(
            f"/api/v1/tenant-invitations/{self.tenant_invitation.id}/share/",
            {"channel": "EMAIL_AUTOMATIC"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_revoke_invitation_of_b(self):
        response = self.client.post(
            f"/api/v1/tenant-invitations/{self.tenant_invitation.id}/revoke/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.tenant_invitation.refresh_from_db()
        self.assertEqual(self.tenant_invitation.status, "PENDING")

    def test_a_list_excludes_invitations_of_b(self):
        response = self.client.get("/api/v1/tenant-invitations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.tenant_invitation.id),
            [str(i["id"]) for i in response.data],
        )

    def test_a_cannot_create_invitation_for_tenant_of_b(self):
        response = self.client.post(
            "/api/v1/tenant-invitations/",
            {"tenant_id": str(self.unlinked_tenant.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
