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
