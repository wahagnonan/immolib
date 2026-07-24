from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from modules.properties.models import Ownership, Property
from modules.properties.services import CreateHouseData, create_house


class OwnershipModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.primary_owner = user_model.objects.create_user(
            phone="+2250700000001", password="password"
        )
        self.co_owner = user_model.objects.create_user(
            phone="+2250700000002", password="password"
        )
        self.house = Property.objects.create(
            name="Maison Yopougon Niangon",
            address="Niangon Nord",
            commune="Yopougon",
            city="Abidjan",
        )

    def test_house_accepts_one_primary_owner_and_multiple_co_owners(self):
        Ownership.objects.create(
            property=self.house,
            user=self.primary_owner,
            role=Ownership.Role.PRIMARY,
            access_level=Ownership.AccessLevel.ACTIVE,
            ownership_percentage=60,
        )
        Ownership.objects.create(
            property=self.house,
            user=self.co_owner,
            role=Ownership.Role.CO_OWNER,
            access_level=Ownership.AccessLevel.OBSERVER,
            ownership_percentage=40,
        )

        self.assertEqual(self.house.ownerships.count(), 2)
        self.assertEqual(self.house.property_type, Property.Type.HOUSE)

    def test_house_cannot_have_two_primary_owners(self):
        Ownership.objects.create(
            property=self.house,
            user=self.primary_owner,
            role=Ownership.Role.PRIMARY,
            access_level=Ownership.AccessLevel.ACTIVE,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Ownership.objects.create(
                property=self.house,
                user=self.co_owner,
                role=Ownership.Role.PRIMARY,
                access_level=Ownership.AccessLevel.ACTIVE,
            )

    def test_same_user_cannot_be_added_twice_to_same_house(self):
        Ownership.objects.create(
            property=self.house,
            user=self.primary_owner,
            role=Ownership.Role.PRIMARY,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Ownership.objects.create(
                property=self.house,
                user=self.primary_owner,
                role=Ownership.Role.CO_OWNER,
            )

    def test_create_house_service_always_adds_primary_owner(self):
        house = create_house(
            owner=self.primary_owner,
            data=CreateHouseData(
                name="Maison Cocody",
                address="Riviera 3",
                city="Abidjan",
                commune="Cocody",
            ),
        )

        ownership = house.ownerships.get()
        self.assertEqual(ownership.user, self.primary_owner)
        self.assertEqual(ownership.role, Ownership.Role.PRIMARY)
        self.assertEqual(ownership.access_level, Ownership.AccessLevel.ACTIVE)
