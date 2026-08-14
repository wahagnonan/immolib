"""Matrice IDOR cross-tenant : maisons, coproprietaires, invitations.

Un bailleur A ne peut ni lire ni modifier les objets du bailleur B :
reponse 404 attendue, jamais 403 (pas de fuite d'existence).
"""

from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.tests.idor_fixtures import make_estate, make_landlord
from modules.properties.models import Ownership
from modules.properties.services import (
    CreateHouseData,
    InviteCoOwnerData,
    create_house,
    invite_coowner,
)


class EstateIdorBase(APITestCase):
    def setUp(self):
        self.landlord_a = make_landlord("+2250700001201")
        self.landlord_b = make_landlord("+2250700001202")
        self.estate_b = make_estate(
            owner=self.landlord_b,
            name="Villa B",
            tenant_phone="+2250500001202",
            coowner_phone="+2250100001202",
        )
        self.client.force_authenticate(self.landlord_a)


class HouseIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_house_of_b(self):
        response = self.client.get(f"/api/v1/houses/{self.estate_b.house.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_update_house_of_b(self):
        response = self.client.patch(
            f"/api/v1/houses/{self.estate_b.house.id}/",
            {"name": "Piraté"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_cannot_delete_house_of_b(self):
        response = self.client.delete(f"/api/v1/houses/{self.estate_b.house.id}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_list_excludes_house_of_b(self):
        response = self.client.get("/api/v1/houses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(str(self.estate_b.house.id), [str(h["id"]) for h in response.data])


class CoOwnerIdorTests(EstateIdorBase):
    def setUp(self):
        super().setUp()
        self.coowner_user = make_landlord("+2250700001203")
        invite_coowner(
            actor=self.landlord_b,
            property=self.estate_b.house,
            data=InviteCoOwnerData(
                phone=self.coowner_user.phone,
                access_level=Ownership.AccessLevel.ACTIVE,
            ),
        )
        self.coownership = Ownership.objects.get(
            property=self.estate_b.house, user=self.coowner_user
        )

    def test_a_cannot_retrieve_coownership_of_b(self):
        response = self.client.get(f"/api/v1/co-owners/{self.coownership.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_update_coownership_of_b(self):
        response = self.client.patch(
            f"/api/v1/co-owners/{self.coownership.id}/",
            {"access_level": Ownership.AccessLevel.ACTIVE},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.coownership.refresh_from_db()
        self.assertEqual(
            self.coownership.access_level, Ownership.AccessLevel.ACTIVE
        )

    def test_a_cannot_delete_coownership_of_b(self):
        response = self.client.delete(f"/api/v1/co-owners/{self.coownership.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Ownership.objects.filter(id=self.coownership.id).exists()
        )

    def test_a_list_excludes_coowners_of_b(self):
        response = self.client.get("/api/v1/co-owners/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.coownership.id), [str(c["id"]) for c in response.data]
        )


class CoOwnerInvitationIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_invitation_of_b(self):
        response = self.client.get(
            f"/api/v1/co-owner-invitations/{self.estate_b.coowner_invitation.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_revoke_invitation_of_b(self):
        response = self.client.post(
            f"/api/v1/co-owner-invitations/{self.estate_b.coowner_invitation.id}/revoke/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.estate_b.coowner_invitation.refresh_from_db()
        self.assertEqual(
            self.estate_b.coowner_invitation.status, "PENDING"
        )

    def test_a_list_excludes_invitations_of_b(self):
        response = self.client.get("/api/v1/co-owner-invitations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.coowner_invitation.id),
            [str(i["id"]) for i in response.data],
        )

    def test_a_cannot_invite_coowner_on_house_of_b(self):
        response = self.client.post(
            "/api/v1/co-owner-invitations/",
            {
                "house_id": str(self.estate_b.house.id),
                "phone": "+2250100001299",
                "access_level": Ownership.AccessLevel.OBSERVER,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
