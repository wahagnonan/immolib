from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from modules.properties.models import Property
from modules.properties.services import CreateHouseData, create_house


class HouseApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000010", password="password"
        )
        self.other_owner = user_model.objects.create_user(
            phone="+2250700000011", password="password"
        )

    def test_authenticated_user_can_create_house(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            "/api/v1/houses/",
            {
                "name": "Maison Bingerville",
                "address": "Quartier Feh Kesse",
                "commune": "Bingerville",
                "city": "Abidjan",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        house = Property.objects.get(id=response.data["id"])
        self.assertEqual(house.ownerships.get().user, self.owner)
        self.assertEqual(house.property_type, Property.Type.HOUSE)
        self.assertEqual(response.data["property_type"], "HOUSE")
        self.assertEqual(response.data["property_type_label"], "Maison")

    def test_create_apartment_and_land_with_property_type(self):
        self.client.force_authenticate(self.owner)
        self.client.post(
            "/api/v1/subscription/upgrade/",
            {"plan_slug": "essential"},
            format="json",
        )

        apartment = self.client.post(
            "/api/v1/houses/",
            {
                "name": "Résidence Les Cocotiers",
                "address": "Boulevard VGE",
                "commune": "Cocody",
                "city": "Abidjan",
                "property_type": "APARTMENT",
            },
            format="json",
        )
        land = self.client.post(
            "/api/v1/houses/",
            {
                "name": "Terrain Plateau",
                "address": "Avenue Chardy",
                "city": "Abidjan",
                "property_type": "LAND",
            },
            format="json",
        )

        self.assertEqual(apartment.status_code, status.HTTP_201_CREATED)
        self.assertEqual(land.status_code, status.HTTP_201_CREATED)
        self.assertEqual(apartment.data["property_type"], "APARTMENT")
        self.assertEqual(apartment.data["property_type_label"], "Appartement")
        self.assertEqual(land.data["property_type"], "LAND")
        self.assertEqual(land.data["property_type_label"], "Terrain")
        self.assertEqual(Property.objects.get(id=apartment.data["id"]).property_type, "APARTMENT")
        self.assertEqual(Property.objects.get(id=land.data["id"]).property_type, "LAND")

    def test_invalid_property_type_is_rejected(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            "/api/v1/houses/",
            {
                "name": "Bien bizarre",
                "address": "Adjamé",
                "city": "Abidjan",
                "property_type": "VILLA",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_only_lists_houses_they_own(self):
        own_house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Ma maison", address="Yopougon", city="Abidjan"
            ),
        )
        create_house(
            owner=self.other_owner,
            data=CreateHouseData(
                name="Maison etrangere", address="Cocody", city="Abidjan"
            ),
        )
        self.client.force_authenticate(self.owner)

        response = self.client.get("/api/v1/houses/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(own_house.id))

    def test_anonymous_user_cannot_list_houses(self):
        response = self.client.get("/api/v1/houses/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
