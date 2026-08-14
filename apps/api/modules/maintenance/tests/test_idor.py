"""Matrice IDOR cross-tenant : incidents de maintenance (cote bailleur et locataire)."""

from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.tests.idor_fixtures import make_estate, make_landlord
from modules.maintenance.models import MaintenanceIncident


class EstateIdorBase(APITestCase):
    def setUp(self):
        self.landlord_a = make_landlord("+2250700001801")
        self.landlord_b = make_landlord("+2250700001802")
        self.estate_b = make_estate(
            owner=self.landlord_b,
            name="Villa B",
            tenant_phone="+2250500001802",
            coowner_phone="+2250100001802",
        )
        self.client.force_authenticate(self.landlord_a)


class MaintenanceOwnerIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_incident_of_b(self):
        response = self.client.get(f"/api/v1/incidents/{self.estate_b.incident.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_update_incident_of_b(self):
        response = self.client.patch(
            f"/api/v1/incidents/{self.estate_b.incident.id}/",
            {"title": "Piraté"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_cannot_set_status_of_incident_of_b(self):
        response = self.client.post(
            f"/api/v1/incidents/{self.estate_b.incident.id}/set-status/",
            {"status": MaintenanceIncident.Status.CANCELLED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.estate_b.incident.refresh_from_db()
        self.assertEqual(self.estate_b.incident.status, MaintenanceIncident.Status.REPORTED)

    def test_a_cannot_comment_on_incident_of_b(self):
        response = self.client.post(
            f"/api/v1/incidents/{self.estate_b.incident.id}/comment/",
            {"message": "Piraté"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_list_excludes_incidents_of_b(self):
        response = self.client.get("/api/v1/incidents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.incident.id),
            [str(i["id"]) for i in response.data],
        )

    def test_a_cannot_create_incident_on_lease_of_b(self):
        response = self.client.post(
            "/api/v1/incidents/",
            {
                "lease_id": str(self.estate_b.lease.id),
                "title": "Piraté",
                "description": "Intrusion",
                "category": "SECURITY",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MaintenanceTenantIdorTests(EstateIdorBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.estate_b.tenant_user)

    def test_tenant_list_only_contains_own_incidents(self):
        response = self.client.get("/api/v1/tenant-portal/incidents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [str(i["id"]) for i in response.data]
        self.assertIn(str(self.estate_b.incident.id), ids)

    def test_other_tenant_cannot_list_incidents_of_b(self):
        other_tenant = make_landlord("+2250500001801")
        self.client.force_authenticate(other_tenant)
        response = self.client.get("/api/v1/tenant-portal/incidents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.incident.id),
            [str(i["id"]) for i in response.data],
        )

    def test_other_tenant_cannot_comment_on_incident_of_b(self):
        other_tenant = make_landlord("+2250500001801")
        self.client.force_authenticate(other_tenant)
        response = self.client.post(
            f"/api/v1/tenant-portal/incidents/{self.estate_b.incident.id}/comment/",
            {"message": "Piraté"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_tenant_cannot_respond_to_incident_of_b(self):
        other_tenant = make_landlord("+2250500001801")
        self.client.force_authenticate(other_tenant)
        response = self.client.post(
            f"/api/v1/tenant-portal/incidents/{self.estate_b.incident.id}/respond/",
            {"action": "CLOSE", "message": "Merci"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_landlord_a_cannot_see_tenant_incidents_of_b(self):
        self.client.force_authenticate(self.landlord_a)
        response = self.client.get("/api/v1/tenant-portal/incidents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.incident.id),
            [str(i["id"]) for i in response.data],
        )
