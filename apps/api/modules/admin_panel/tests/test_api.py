"""Tests fonctionnels des endpoints admin (dashboard, listes, filtres)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.models import AuditLog
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house
from modules.subscriptions.models import (
    Subscription,
    SubscriptionPlan,
    SubscriptionTransaction,
)

User = get_user_model()


class AdminApiFixture:
    def setUp(self):
        self.admin = User.objects.create_user(
            phone="+2250700000800", password="password", role=User.Role.ADMIN
        )
        self.owner = User.objects.create_user(
            phone="+2250700000801",
            password="password",
            first_name="Jean",
            last_name="Soro",
        )
        self.client.force_authenticate(self.admin)


class AdminDashboardTests(AdminApiFixture, APITestCase):
    def test_dashboard_metrics_are_real(self):
        self.owner.role = User.Role.ADMIN
        self.owner.save(update_fields=["role"])
        create_house(
            owner=self.owner,
            data=CreateHouseData(name="Villa", address="Cocody", city="Abidjan"),
        )
        response = self.client.get("/api/v1/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["users"]["total"], 2)
        self.assertEqual(data["users"]["admins"], 2)
        self.assertEqual(data["users"]["landlords"], 1)
        self.assertEqual(data["houses"]["total"], 1)
        self.assertIn("revenue", data)
        self.assertEqual(data["revenue"]["currency"], "XOF")

    def test_dashboard_revenue_from_successful_transactions_only(self):
        plan = SubscriptionPlan.objects.get(slug="pro")
        user2 = User.objects.create_user(phone="+2250700000802", password="password")
        SubscriptionTransaction.objects.create(
            user=user2,
            plan=plan,
            amount=4000,
            status=SubscriptionTransaction.Status.SUCCESSFUL,
            completed_at=timezone.now(),
        )
        SubscriptionTransaction.objects.create(
            user=user2,
            plan=plan,
            amount=4000,
            status=SubscriptionTransaction.Status.FAILED,
            completed_at=timezone.now(),
        )
        response = self.client.get("/api/v1/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["revenue"]["month"], 4000)
        self.assertEqual(response.data["revenue"]["day"], 4000)


class AdminUsersListTests(AdminApiFixture, APITestCase):
    def setUp(self):
        super().setUp()
        from modules.subscriptions.services import upgrade

        upgrade(self.owner, "essential")
        create_house(
            owner=self.owner,
            data=CreateHouseData(name="Maison Yop", address="Yopougon", city="Abidjan"),
        )
        self.tenant_user = User.objects.create_user(
            phone="+2250500000800", password="password", email="loc@example.com"
        )
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(name="Maison Cocody", address="Cocody", city="Abidjan"),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Locataire",
                phone=self.tenant_user.phone,
                email=self.tenant_user.email,
            ),
        )
        create_lease(
            actor=self.owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("50000"),
                monthly_charges=Decimal("0"),
                due_day=5,
                security_deposit=Decimal("0"),
            ),
        )

    def test_list_users_with_annotations(self):
        response = self.client.get("/api/v1/admin/users/?page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertGreaterEqual(len(results), 3)
        owner_row = next(
            row for row in results if row["id"] == str(self.owner.id)
        )
        self.assertEqual(owner_row["houses_count"], 2)
        self.assertEqual(owner_row["plan_slug"], "essential")

    def test_filter_by_search_and_role(self):
        response = self.client.get(
            "/api/v1/admin/users/?search=loc@example.com&page=1"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "loc@example.com")

        response = self.client.get("/api/v1/admin/users/?role=ADMIN&page=1")
        rows = response.data["results"]
        self.assertTrue(all(row["role"] == "ADMIN" for row in rows))

    def test_user_detail(self):
        response = self.client.get(f"/api/v1/admin/users/{self.owner.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.owner.id))
        self.assertEqual(response.data["full_name"], "Jean Soro")


class AdminLandlordsAndHousesTests(AdminApiFixture, APITestCase):
    def setUp(self):
        super().setUp()
        from modules.subscriptions.services import upgrade

        upgrade(self.owner, "essential")
        create_house(
            owner=self.owner,
            data=CreateHouseData(name="Villa Riviera", address="Riviera", city="Abidjan"),
        )

    def test_landlords_list(self):
        response = self.client.get("/api/v1/admin/landlords/?page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], str(self.owner.id))
        self.assertEqual(rows[0]["houses_count"], 1)

    def test_houses_list_with_owner(self):
        response = self.client.get("/api/v1/admin/houses/?page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Villa Riviera")
        self.assertFalse(rows[0]["has_active_lease"])

    def test_houses_filter_by_occupancy(self):
        create_house(
            owner=self.owner,
            data=CreateHouseData(name="Villa Deux", address="Cocody", city="Abidjan"),
        )
        response = self.client.get("/api/v1/admin/houses/?occupancy=with_tenant&page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)
        response = self.client.get(
            "/api/v1/admin/houses/?occupancy=without_tenant&page=1"
        )
        self.assertEqual(len(response.data["results"]), 2)


class AdminAuditLogTests(AdminApiFixture, APITestCase):
    def test_audit_logs_list_and_filters(self):
        target = User.objects.create_user(
            phone="+2250700000803", password="password"
        )
        AuditLog.objects.create(
            admin=self.admin,
            action=AuditLog.Action.USER_SUSPENDED,
            target_type="user",
            target_id=str(target.id),
            metadata={"phone": target.phone},
            ip_address="127.0.0.1",
        )
        response = self.client.get("/api/v1/admin/audit-logs/?page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "USER_SUSPENDED")
        self.assertNotIn("password", rows[0]["metadata"])

        response = self.client.get(
            "/api/v1/admin/audit-logs/?action=USER_REACTIVATED&page=1"
        )
        self.assertEqual(len(response.data["results"]), 0)
