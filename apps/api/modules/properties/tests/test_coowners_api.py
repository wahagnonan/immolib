from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.accounts.services import (
    RegisterUserData,
    account_otp_code_for,
    confirm_phone_verification,
    register_user,
)
from modules.properties.models import CoOwnerInvitation, Ownership
from modules.properties.services import CreateHouseData, create_house


class CoOwnerApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700001100", password="password"
        )
        self.existing_user = user_model.objects.create_user(
            phone="+2250500001101", password="password", first_name="Koffi"
        )
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Villa Riviera",
                address="Riviera 3",
                commune="Cocody",
                city="Abidjan",
            ),
        )
        self.client.force_authenticate(self.owner)

    def _invite(self, **overrides):
        payload = {
            "house_id": str(self.house.id),
            "phone": "+2250100001199",
            "email": "invite@example.com",
            "ownership_percentage": "40.00",
            "access_level": Ownership.AccessLevel.OBSERVER,
            **overrides,
        }
        return self.client.post(
            "/api/v1/co-owner-invitations/", payload, format="json"
        )

    def test_existing_account_is_added_immediately(self):
        response = self._invite(phone=self.existing_user.phone)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], CoOwnerInvitation.Status.ACCEPTED)
        self.assertEqual(response.data["accepted_by"]["id"], str(self.existing_user.id))
        ownership = Ownership.objects.get(
            property=self.house, user=self.existing_user
        )
        self.assertEqual(ownership.role, Ownership.Role.CO_OWNER)
        self.assertEqual(ownership.access_level, Ownership.AccessLevel.OBSERVER)
        self.assertEqual(ownership.ownership_percentage, Decimal("40.00"))
        primary = self.house.ownerships.get(role=Ownership.Role.PRIMARY)
        self.assertEqual(primary.ownership_percentage, Decimal("60.00"))

        list_response = self.client.get(
            f"/api/v1/co-owners/?house_id={self.house.id}"
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["house_name"], self.house.name)

    def test_unknown_phone_creates_pending_invitation(self):
        response = self._invite()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], CoOwnerInvitation.Status.PENDING)
        self.assertFalse(response.data["is_expired"])
        self.assertFalse(
            Ownership.objects.filter(
                property=self.house, user__phone="+2250100001199"
            ).exists()
        )

    def test_phone_verification_accepts_pending_invitation(self):
        self._invite(
            phone="+2250100001102",
            ownership_percentage="25.00",
            access_level=Ownership.AccessLevel.ACTIVE,
        )

        registration = register_user(
            data=RegisterUserData(
                phone="+2250100001102",
                password="Une-phrase-secrete-2026!",
                first_name="Aminata",
            )
        )

        user = registration.user
        invitation = CoOwnerInvitation.objects.get(
            property=self.house, phone=user.phone
        )
        self.assertEqual(invitation.status, CoOwnerInvitation.Status.PENDING)
        confirm_phone_verification(
            phone=user.phone,
            code=account_otp_code_for(registration.otp_issue.challenge),
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, CoOwnerInvitation.Status.ACCEPTED)
        ownership = Ownership.objects.get(property=self.house, user=user)
        self.assertEqual(ownership.access_level, Ownership.AccessLevel.ACTIVE)
        self.assertEqual(ownership.ownership_percentage, Decimal("25.00"))
        primary = self.house.ownerships.get(role=Ownership.Role.PRIMARY)
        self.assertEqual(primary.ownership_percentage, Decimal("75.00"))

    def test_expired_invitation_is_not_accepted_during_registration(self):
        response = self._invite(phone="+2250100001103")
        invitation = CoOwnerInvitation.objects.get(id=response.data["id"])
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save(update_fields=["expires_at"])

        registration = register_user(
            data=RegisterUserData(
                phone="+2250100001103",
                password="Une-autre-phrase-secrete-2026!",
            )
        )

        user = registration.user
        confirm_phone_verification(
            phone=user.phone,
            code=account_otp_code_for(registration.otp_issue.challenge),
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, CoOwnerInvitation.Status.PENDING)
        self.assertFalse(
            Ownership.objects.filter(property=self.house, user=user).exists()
        )

        replacement = self._invite(phone=user.phone)
        self.assertEqual(replacement.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            replacement.data["status"], CoOwnerInvitation.Status.ACCEPTED
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, CoOwnerInvitation.Status.EXPIRED)

    def test_only_primary_owner_can_manage_coowners(self):
        self._invite(
            phone=self.existing_user.phone,
            access_level=Ownership.AccessLevel.ACTIVE,
        )
        self.client.force_authenticate(self.existing_user)

        create_response = self._invite(phone="+2250100001104")
        list_response = self.client.get("/api/v1/co-owners/")

        self.assertEqual(create_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data, [])

    def test_primary_owner_updates_access_and_share(self):
        self._invite(phone=self.existing_user.phone)
        ownership = Ownership.objects.get(
            property=self.house, user=self.existing_user
        )

        response = self.client.patch(
            f"/api/v1/co-owners/{ownership.id}/",
            {
                "access_level": Ownership.AccessLevel.ACTIVE,
                "ownership_percentage": "25.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ownership.refresh_from_db()
        self.assertEqual(ownership.access_level, Ownership.AccessLevel.ACTIVE)
        self.assertEqual(ownership.ownership_percentage, Decimal("25.00"))
        primary = self.house.ownerships.get(role=Ownership.Role.PRIMARY)
        self.assertEqual(primary.ownership_percentage, Decimal("75.00"))

    def test_primary_owner_removes_coowner_and_recovers_full_share(self):
        self._invite(phone=self.existing_user.phone)
        ownership = Ownership.objects.get(
            property=self.house, user=self.existing_user
        )

        response = self.client.delete(f"/api/v1/co-owners/{ownership.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Ownership.objects.filter(id=ownership.id).exists())
        primary = self.house.ownerships.get(role=Ownership.Role.PRIMARY)
        self.assertEqual(primary.ownership_percentage, Decimal("100.00"))

    def test_pending_invitations_reserve_their_shares(self):
        first = self._invite(
            phone="+2250100001105", ownership_percentage="60.00"
        )
        second = self._invite(
            phone="+2250100001106", ownership_percentage="40.00"
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ownership_percentage", second.data)

    def test_pending_invitation_can_be_revoked(self):
        created = self._invite(phone="+2250100001107")

        response = self.client.post(
            f"/api/v1/co-owner-invitations/{created.data['id']}/revoke/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], CoOwnerInvitation.Status.REVOKED)
        self.assertIsNotNone(response.data["revoked_at"])

        replacement = self._invite(phone="+2250100001107")
        self.assertEqual(replacement.status_code, status.HTTP_201_CREATED)

    def test_primary_owner_cannot_be_invited_as_coowner(self):
        response = self._invite(phone=self.owner.phone)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)

    def test_empty_update_is_rejected(self):
        self._invite(phone=self.existing_user.phone)
        ownership = Ownership.objects.get(
            property=self.house, user=self.existing_user
        )

        response = self.client.patch(
            f"/api/v1/co-owners/{ownership.id}/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_user_cannot_list_invitations(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/co-owner-invitations/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
