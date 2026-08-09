"""Matrice de securite de l'espace admin.

ADMIN -> 200 ; BAILLEUR -> 403 ; LOCATAIRE -> 403 ; non authentifie -> 401.
La securite repose sur le backend : modifier l'URL, le role affiche ou le
token cote client ne change rien a l'autorisation serveur.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.models import AuditLog
from modules.leases.models import Lease
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house
from modules.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


class AdminSecurityFixture:
    def make_landlord(self, phone: str) -> User:
        landlord = User.objects.create_user(phone=phone, password="password")
        create_house(
            owner=landlord,
            data=CreateHouseData(name="Maison test", address="Cocody", city="Abidjan"),
        )
        return landlord

    def make_tenant_user(self, phone: str) -> User:
        owner = self.make_landlord("+2250700000901")
        from modules.subscriptions.services import upgrade

        upgrade(owner, "essential")
        tenant_user = User.objects.create_user(
            phone=phone, password="password", email="tenant@example.com"
        )
        house = create_house(
            owner=owner,
            data=CreateHouseData(
                name="Maison locataire", address="Yopougon", city="Abidjan"
            ),
        )
        tenant = create_tenant(
            actor=owner,
            property=house,
            data=CreateTenantData(
                full_name="Locataire test",
                phone=tenant_user.phone,
                email=tenant_user.email,
            ),
        )
        create_lease(
            actor=owner,
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
        return tenant_user

    def make_admin(self, phone: str = "+2250700000900") -> User:
        return User.objects.create_user(
            phone=phone, password="password", role=User.Role.ADMIN
        )


class AdminAccessMatrixTests(AdminSecurityFixture, APITestCase):
    """GET /admin/users : 200 admin, 403 bailleur, 403 locataire, 401 anonyme."""

    ADMIN_URL = "/api/v1/admin/users/"

    def setUp(self):
        self.admin = self.make_admin()
        self.landlord = self.make_landlord("+2250700000902")
        self.tenant_user = self.make_tenant_user("+2250500000902")

    def test_admin_can_list_users(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.ADMIN_URL + "?page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_landlord_forbidden(self):
        self.client.force_authenticate(self.landlord)
        response = self.client.get(self.ADMIN_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tenant_forbidden(self):
        self.client.force_authenticate(self.tenant_user)
        response = self.client.get(self.ADMIN_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_returns_401(self):
        response = self.client.get(self.ADMIN_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_write_returns_401(self):
        response = self.client.patch(
            f"/api/v1/admin/users/{self.landlord.id}/status/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_all_admin_routes_require_admin(self):
        routes = [
            "/api/v1/admin/dashboard/",
            "/api/v1/admin/users/",
            "/api/v1/admin/landlords/",
            "/api/v1/admin/tenants/",
            "/api/v1/admin/houses/",
            "/api/v1/admin/subscriptions/",
            "/api/v1/admin/payments/",
            "/api/v1/admin/notifications/",
            "/api/v1/admin/audit-logs/",
            "/api/v1/admin/stats/users-evolution/?period=30d",
        ]
        for url in routes:
            with self.subTest(url=url):
                self.client.force_authenticate(self.landlord)
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.client.force_authenticate(self.admin)
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)


class RoleTamperingTests(AdminSecurityFixture, APITestCase):
    """Un utilisateur ne peut jamais devenir admin en manipulant l'API."""

    def setUp(self):
        self.admin = self.make_admin()
        self.user = User.objects.create_user(
            phone="+2250700000903", password="password"
        )

    def test_register_ignores_role_field(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": "+2250700000999",
                "password": "MotDePasse1!",
                "password_confirmation": "MotDePasse1!",
                "role": "ADMIN",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(phone="+2250700000999")
        self.assertEqual(created.role, User.Role.USER)

    def test_no_endpoint_allows_role_change(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            "/api/v1/auth/me/", {"role": "ADMIN"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.USER)

    def test_user_cannot_suspend_another_user(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            f"/api/v1/admin/users/{self.admin.id}/status/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class UserSuspensionTests(AdminSecurityFixture, APITestCase):
    def setUp(self):
        self.admin = self.make_admin()
        self.target = User.objects.create_user(
            phone="+2250700000904", password="password", email="suspendu@example.com"
        )

    def test_suspend_blocks_login_and_logs_audit(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/v1/admin/users/{self.target.id}/status/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.USER_SUSPENDED,
                target_id=str(self.target.id),
                admin=self.admin,
            ).exists()
        )
        self.client.force_authenticate(None)
        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": "suspendu@example.com", "password": "password"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reactivate_restores_login_and_logs_audit(self):
        self.target.is_active = False
        self.target.save(update_fields=["is_active"])
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/v1/admin/users/{self.target.id}/status/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.USER_REACTIVATED,
                target_id=str(self.target.id),
            ).exists()
        )

    def test_admin_cannot_suspend_self(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/v1/admin/users/{self.admin.id}/status/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class SubscriptionAdminActionTests(AdminSecurityFixture, APITestCase):
    def setUp(self):
        self.admin = self.make_admin()
        self.landlord = self.make_landlord("+2250700000905")
        from modules.subscriptions.services import upgrade

        upgrade(self.landlord, "pro")
        self.subscription = Subscription.objects.get(user=self.landlord)

    def test_admin_change_plan_and_audit(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/v1/admin/subscriptions/{self.subscription.id}/",
            {"action": "change_plan", "plan_slug": "pro"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan.slug, "pro")
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        log = AuditLog.objects.get(
            action=AuditLog.Action.SUBSCRIPTION_CHANGED,
            target_id=str(self.subscription.id),
        )
        self.assertEqual(log.metadata["plan_to"], "pro")
        self.assertNotIn("password", log.metadata)
        self.assertNotIn("token", log.metadata)

    def test_admin_extend_subscription(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/v1/admin/subscriptions/{self.subscription.id}/",
            {"action": "extend", "days": 30},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.SUBSCRIPTION_EXTENDED,
                target_id=str(self.subscription.id),
            ).exists()
        )

    def test_admin_cancel_subscription(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/v1/admin/subscriptions/{self.subscription.id}/",
            {"action": "cancel"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.CANCELLED)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.SUBSCRIPTION_CANCELLED,
                target_id=str(self.subscription.id),
            ).exists()
        )

    def test_landlord_cannot_change_subscription(self):
        self.client.force_authenticate(self.landlord)
        response = self.client.patch(
            f"/api/v1/admin/subscriptions/{self.subscription.id}/",
            {"action": "cancel"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CreateAdminCommandTests(APITestCase):
    def test_create_new_admin(self):
        call_command(
            "create_admin",
            phone="+2250700000906",
            password="MotDePasse1!",
            email="admin2@immolib.ci",
            first_name="Admin",
            last_name="ImmoLib",
        )
        user = User.objects.get(phone="+2250700000906")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.check_password("MotDePasse1!"))
        self.assertEqual(user.email, "admin2@immolib.ci")

    def test_promote_existing_user(self):
        user = User.objects.create_user(
            phone="+2250700000907", password="password"
        )
        call_command("create_admin", phone="+2250700000907", promote=True)
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.check_password("password"))

    def test_create_without_password_rejected(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("create_admin", phone="+2250700000908")
