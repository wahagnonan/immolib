from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from modules.properties.models import Ownership, Property
from modules.properties.services import CreateHouseData, create_house

from ..models import Lease
from ..services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    close_lease,
    create_lease,
    create_tenant,
)


class LeaseServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000100", password="password"
        )
        self.active_co_owner = user_model.objects.create_user(
            phone="+2250700000101", password="password"
        )
        self.observer = user_model.objects.create_user(
            phone="+2250700000102", password="password"
        )
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Yopougon",
                address="Niangon Nord",
                city="Abidjan",
                commune="Yopougon",
            ),
        )
        Ownership.objects.create(
            property=self.house,
            user=self.active_co_owner,
            role=Ownership.Role.CO_OWNER,
            access_level=Ownership.AccessLevel.ACTIVE,
        )
        Ownership.objects.create(
            property=self.house,
            user=self.observer,
            role=Ownership.Role.CO_OWNER,
            access_level=Ownership.AccessLevel.OBSERVER,
        )

    def _create_tenant(self, phone="+2250500000100"):
        return create_tenant(
            actor=self.owner,
            property=self.house,
            data=CreateTenantData(full_name="Moussa Kone", phone=phone),
        )

    def _create_lease(self, tenant):
        return create_lease(
            actor=self.owner,
            property=self.house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("100000"),
                monthly_charges=Decimal("10000"),
                due_day=5,
                security_deposit=Decimal("200000"),
            ),
        )

    def test_active_co_owner_can_create_tenant(self):
        tenant = create_tenant(
            actor=self.active_co_owner,
            property=self.house,
            data=CreateTenantData(
                full_name="Awa Traore", phone="+2250500000101"
            ),
        )

        self.assertEqual(tenant.property, self.house)
        self.assertEqual(tenant.created_by, self.active_co_owner)

    def test_observer_cannot_create_tenant(self):
        with self.assertRaises(PermissionDenied):
            create_tenant(
                actor=self.observer,
                property=self.house,
                data=CreateTenantData(
                    full_name="Awa Traore", phone="+2250500000101"
                ),
            )

    def test_same_phone_cannot_be_added_twice_to_same_house(self):
        self._create_tenant()

        with self.assertRaises(ValidationError):
            self._create_tenant()

    def test_tenant_and_lease_must_belong_to_same_house(self):
        other_house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Cocody", address="Riviera", city="Abidjan"
            ),
        )
        tenant = self._create_tenant()

        with self.assertRaises(ValidationError):
            create_lease(
                actor=self.owner,
                property=other_house,
                tenant=tenant,
                data=CreateLeaseData(
                    start_date=date(2026, 7, 1),
                    monthly_rent=Decimal("100000"),
                    due_day=5,
                ),
            )

    def test_activating_lease_marks_house_as_occupied(self):
        lease = self._create_lease(self._create_tenant())

        activated = activate_lease(actor=self.owner, lease=lease)

        self.house.refresh_from_db()
        self.assertEqual(activated.status, Lease.Status.ACTIVE)
        self.assertIsNotNone(activated.activated_at)
        self.assertEqual(self.house.status, Property.Status.OCCUPIED)

    def test_house_cannot_have_two_active_leases(self):
        first = self._create_lease(self._create_tenant())
        second = self._create_lease(self._create_tenant(phone="+2250500000102"))
        activate_lease(actor=self.owner, lease=first)

        with self.assertRaisesMessage(ValidationError, "deja un bail actif"):
            activate_lease(actor=self.owner, lease=second)

    def test_closing_lease_marks_house_as_vacant_and_keeps_history(self):
        lease = self._create_lease(self._create_tenant())
        activate_lease(actor=self.owner, lease=lease)

        closed = close_lease(actor=self.owner, lease=lease)

        self.house.refresh_from_db()
        self.assertEqual(closed.status, Lease.Status.ENDED)
        self.assertIsNotNone(closed.ended_at)
        self.assertEqual(self.house.status, Property.Status.VACANT)
        self.assertTrue(Lease.objects.filter(id=lease.id).exists())
