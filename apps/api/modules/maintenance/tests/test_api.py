from datetime import date
from decimal import Decimal

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
from modules.properties.models import Ownership
from modules.properties.services import CreateHouseData, create_house

from ..models import MaintenanceEvent, MaintenanceIncident


class MaintenanceIncidentApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700001600",
            password="password",
            first_name="Jean",
            last_name="Soro",
        )
        self.tenant_user = user_model.objects.create_user(
            phone="+2250500001600",
            password="password",
            first_name="Aminata",
            last_name="Koné",
        )
        self.observer = user_model.objects.create_user(
            phone="+2250100001600",
            password="password",
        )
        self.outsider = user_model.objects.create_user(
            phone="+2250100001699",
            password="password",
        )
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Angré",
                address="Angré 8e tranche",
                city="Abidjan",
                commune="Cocody",
            ),
        )
        Ownership.objects.create(
            property=self.house,
            user=self.observer,
            role=Ownership.Role.CO_OWNER,
            access_level=Ownership.AccessLevel.OBSERVER,
        )
        self.tenant = create_tenant(
            actor=self.owner,
            property=self.house,
            data=CreateTenantData(
                full_name="Aminata Koné",
                phone=self.tenant_user.phone,
            ),
        )
        self.lease = create_lease(
            actor=self.owner,
            property=self.house,
            tenant=self.tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("125000"),
                due_day=5,
            ),
        )
        activate_lease(actor=self.owner, lease=self.lease)

    def _create_as_tenant(self):
        self.client.force_authenticate(self.tenant_user)
        response = self.client.post(
            "/api/v1/tenant-portal/incidents/",
            {
                "lease_id": str(self.lease.id),
                "title": "Fuite sous l'évier",
                "description": "L'eau coule depuis ce matin sous l'évier.",
                "category": MaintenanceIncident.Category.PLUMBING,
                "priority": MaintenanceIncident.Priority.HIGH,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response

    def test_tenant_reports_and_owner_sees_incident(self):
        created = self._create_as_tenant()
        self.client.force_authenticate(self.owner)

        listed = self.client.get("/api/v1/incidents/")

        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0]["id"], created.data["id"])
        self.assertEqual(listed.data[0]["house_name"], "Maison Angré")
        self.assertEqual(listed.data[0]["status"], "REPORTED")
        self.assertEqual(
            listed.data[0]["events"][0]["actor_role"],
            MaintenanceEvent.ActorRole.TENANT,
        )

    def test_owner_progresses_then_tenant_closes_resolution(self):
        incident_id = self._create_as_tenant().data["id"]
        self.client.force_authenticate(self.owner)
        acknowledged = self.client.post(
            f"/api/v1/incidents/{incident_id}/set-status/",
            {"status": "ACKNOWLEDGED", "message": "Demande reçue."},
            format="json",
        )
        in_progress = self.client.post(
            f"/api/v1/incidents/{incident_id}/set-status/",
            {"status": "IN_PROGRESS", "message": "Le plombier est en route."},
            format="json",
        )
        resolved = self.client.post(
            f"/api/v1/incidents/{incident_id}/set-status/",
            {"status": "RESOLVED", "message": "Joint remplacé."},
            format="json",
        )
        self.client.force_authenticate(self.tenant_user)
        closed = self.client.post(
            f"/api/v1/tenant-portal/incidents/{incident_id}/respond/",
            {"action": "CLOSE", "message": "La fuite est arrêtée."},
            format="json",
        )

        self.assertEqual(acknowledged.data["status"], "ACKNOWLEDGED")
        self.assertEqual(in_progress.data["status"], "IN_PROGRESS")
        self.assertEqual(resolved.data["status"], "RESOLVED")
        self.assertEqual(closed.data["status"], "CLOSED")
        self.assertEqual(len(closed.data["events"]), 5)
        self.assertIsNotNone(closed.data["closed_at"])

    def test_tenant_reopens_with_required_reason(self):
        incident_id = self._create_as_tenant().data["id"]
        incident = MaintenanceIncident.objects.get(id=incident_id)
        incident.status = MaintenanceIncident.Status.RESOLVED
        incident.save(update_fields=["status"])
        self.client.force_authenticate(self.tenant_user)

        rejected = self.client.post(
            f"/api/v1/tenant-portal/incidents/{incident_id}/respond/",
            {"action": "REOPEN", "message": ""},
            format="json",
        )
        reopened = self.client.post(
            f"/api/v1/tenant-portal/incidents/{incident_id}/respond/",
            {"action": "REOPEN", "message": "La fuite a recommencé."},
            format="json",
        )

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(reopened.data["status"], "IN_PROGRESS")
        self.assertEqual(
            reopened.data["events"][-1]["message"],
            "La fuite a recommencé.",
        )

    def test_owner_and_tenant_comments_are_traced(self):
        incident_id = self._create_as_tenant().data["id"]
        self.client.force_authenticate(self.owner)
        owner_comment = self.client.post(
            f"/api/v1/incidents/{incident_id}/comment/",
            {"message": "Pouvez-vous couper l'arrivée d'eau ?"},
            format="json",
        )
        self.client.force_authenticate(self.tenant_user)
        tenant_comment = self.client.post(
            f"/api/v1/tenant-portal/incidents/{incident_id}/comment/",
            {"message": "Oui, l'eau est coupée."},
            format="json",
        )

        self.assertEqual(owner_comment.status_code, status.HTTP_200_OK)
        self.assertEqual(tenant_comment.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [event["actor_role"] for event in tenant_comment.data["events"]],
            ["TENANT", "OWNER", "TENANT"],
        )

    def test_observer_reads_but_cannot_change_status(self):
        incident_id = self._create_as_tenant().data["id"]
        self.client.force_authenticate(self.observer)

        listed = self.client.get("/api/v1/incidents/")
        changed = self.client.post(
            f"/api/v1/incidents/{incident_id}/set-status/",
            {"status": "ACKNOWLEDGED"},
            format="json",
        )

        self.assertEqual(len(listed.data), 1)
        self.assertEqual(changed.status_code, status.HTTP_403_FORBIDDEN)

    def test_outsider_cannot_see_or_comment(self):
        incident_id = self._create_as_tenant().data["id"]
        self.client.force_authenticate(self.outsider)

        owner_list = self.client.get("/api/v1/incidents/")
        tenant_list = self.client.get("/api/v1/tenant-portal/incidents/")
        comment = self.client.post(
            f"/api/v1/tenant-portal/incidents/{incident_id}/comment/",
            {"message": "Intrusion"},
            format="json",
        )

        self.assertEqual(owner_list.data, [])
        self.assertEqual(tenant_list.data, [])
        self.assertEqual(comment.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_owner_transition_is_rejected(self):
        incident_id = self._create_as_tenant().data["id"]
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            f"/api/v1/incidents/{incident_id}/set-status/",
            {"status": "RESOLVED"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            MaintenanceIncident.objects.get(id=incident_id).status,
            MaintenanceIncident.Status.REPORTED,
        )
