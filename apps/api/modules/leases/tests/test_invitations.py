from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.documents.models import NotificationDelivery
from modules.documents.notifications import build_notification_message
from modules.properties.services import CreateHouseData, create_house

from ..models import Tenant, TenantInvitation, TenantInvitationShareEvent
from ..services import (
    CreateTenantData,
    claim_tenant_invitation,
    create_tenant,
    create_tenant_invitation,
    revoke_tenant_invitation,
    share_tenant_invitation,
    sign_tenant_invitation,
)


class TenantInvitationFixture:
    def make_fixture(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700001400",
            password="password",
            first_name="Jean",
            last_name="Soro",
        )
        self.outsider = user_model.objects.create_user(
            phone="+2250700001401",
            password="password",
        )
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Cocody",
                address="Cocody Angré",
                city="Abidjan",
                commune="Cocody",
            ),
        )
        self.tenant = create_tenant(
            actor=self.owner,
            property=self.house,
            data=CreateTenantData(
                full_name="Mariam Koné",
                phone="+2250500001400",
                email="mariam@example.com",
            ),
        )


class TenantInvitationServiceTests(TenantInvitationFixture, TestCase):
    def setUp(self):
        self.make_fixture()

    def test_pending_invitation_is_reused_and_marks_tenant_invited(self):
        first = create_tenant_invitation(actor=self.owner, tenant=self.tenant)
        second = create_tenant_invitation(actor=self.owner, tenant=self.tenant)

        self.assertEqual(first, second)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, Tenant.Status.INVITED)
        self.assertEqual(TenantInvitation.objects.count(), 1)

    def test_manual_whatsapp_and_automatic_email_are_distinct(self):
        invitation = create_tenant_invitation(
            actor=self.owner, tenant=self.tenant
        )

        manual = share_tenant_invitation(
            actor=self.owner,
            invitation=invitation,
            channel=TenantInvitationShareEvent.Channel.WHATSAPP,
        )
        automatic = share_tenant_invitation(
            actor=self.owner,
            invitation=invitation,
            channel="EMAIL_AUTOMATIC",
        )

        self.assertTrue(manual.action_url.startswith("https://wa.me/225"))
        self.assertIsNotNone(manual.share_event)
        self.assertIsNone(manual.delivery)
        self.assertEqual(automatic.delivery.channel, "EMAIL")
        self.assertEqual(automatic.delivery.destination, "mariam@example.com")
        self.assertEqual(NotificationDelivery.objects.count(), 1)

        message = build_notification_message(
            NotificationDelivery.objects.select_related(
                "tenant_invitation__tenant__property",
                "tenant_invitation__invited_by",
            ).get()
        )
        self.assertIn("Mariam Koné", message.body)
        self.assertIn("Maison Cocody", message.body)
        self.assertIn("/invitation-locataire/", message.body)

    def test_verified_matching_email_accepts_invitation(self):
        invitation = create_tenant_invitation(
            actor=self.owner, tenant=self.tenant
        )
        user = get_user_model().objects.create_user(
            phone=self.tenant.phone,
            email=self.tenant.email,
            email_verified_at=timezone.now(),
            phone_verified_at=None,
            password="password",
        )

        accepted = claim_tenant_invitation(
            token=sign_tenant_invitation(invitation),
            user=user,
        )

        self.assertEqual(accepted.status, TenantInvitation.Status.ACCEPTED)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.linked_user, user)
        self.assertEqual(self.tenant.status, Tenant.Status.ACTIVE)
        self.assertIsNone(user.phone_verified_at)

    def test_unrelated_account_cannot_claim_invitation(self):
        invitation = create_tenant_invitation(
            actor=self.owner, tenant=self.tenant
        )

        with self.assertRaisesMessage(ValidationError, "ne correspond pas"):
            claim_tenant_invitation(
                token=sign_tenant_invitation(invitation),
                user=self.outsider,
            )

        self.tenant.refresh_from_db()
        self.assertIsNone(self.tenant.linked_user)

    def test_revoked_invitation_cannot_be_shared(self):
        invitation = create_tenant_invitation(
            actor=self.owner, tenant=self.tenant
        )
        revoke_tenant_invitation(actor=self.owner, invitation=invitation)

        with self.assertRaisesMessage(ValidationError, "plus active"):
            share_tenant_invitation(
                actor=self.owner,
                invitation=invitation,
                channel="EMAIL_AUTOMATIC",
            )


class TenantInvitationApiTests(TenantInvitationFixture, APITestCase):
    def setUp(self):
        self.make_fixture()

    @override_settings(EXPOSE_TEST_OTP=True)
    def test_invitation_registration_email_verification_links_tenant(self):
        self.client.force_authenticate(self.owner)
        created = self.client.post(
            "/api/v1/tenant-invitations/",
            {"tenant_id": str(self.tenant.id)},
            format="json",
        )
        token = created.data["secure_url"].rsplit("/", 1)[-1]

        self.client.force_authenticate(user=None)
        preview = self.client.post(
            "/api/v1/public-tenant-invitations/preview/",
            {"token": token},
            format="json",
        )
        registered = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": self.tenant.phone,
                "email": self.tenant.email,
                "first_name": "Mariam",
                "last_name": "Koné",
                "password": "Une-phrase-secrete-2026!",
                "password_confirmation": "Une-phrase-secrete-2026!",
                "tenant_invitation_token": token,
            },
            format="json",
        )
        verified = self.client.post(
            "/api/v1/auth/email-verification/confirm/",
            {
                "phone": self.tenant.phone,
                "code": registered.data["otp_code"],
            },
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data["house_name"], "Maison Cocody")
        self.assertEqual(registered.data["verification_channel"], "EMAIL")
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.tenant.refresh_from_db()
        invitation = TenantInvitation.objects.get()
        self.assertEqual(self.tenant.linked_user.phone, self.tenant.phone)
        self.assertEqual(self.tenant.status, Tenant.Status.ACTIVE)
        self.assertEqual(invitation.status, TenantInvitation.Status.ACCEPTED)

    def test_owner_can_prepare_manual_share_and_outsider_cannot_list(self):
        self.client.force_authenticate(self.owner)
        created = self.client.post(
            "/api/v1/tenant-invitations/",
            {"tenant_id": str(self.tenant.id)},
            format="json",
        )
        shared = self.client.post(
            f"/api/v1/tenant-invitations/{created.data['id']}/share/",
            {"channel": "COPY"},
            format="json",
        )
        self.client.force_authenticate(self.outsider)
        outsider_list = self.client.get("/api/v1/tenant-invitations/")

        self.assertEqual(shared.status_code, status.HTTP_201_CREATED)
        self.assertIn("/invitation-locataire/", shared.data["message"])
        self.assertIsNotNone(shared.data["share_event_id"])
        self.assertEqual(outsider_list.status_code, status.HTTP_200_OK)
        self.assertEqual(outsider_list.data, [])

    def test_registration_rejects_contacts_different_from_invitation(self):
        invitation = create_tenant_invitation(
            actor=self.owner, tenant=self.tenant
        )
        token = sign_tenant_invitation(invitation)

        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": "+2250500001499",
                "email": "other@example.com",
                "password": "Une-phrase-secrete-2026!",
                "password_confirmation": "Une-phrase-secrete-2026!",
                "tenant_invitation_token": token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)
        self.assertFalse(
            get_user_model().objects.filter(phone="+2250500001499").exists()
        )

    @override_settings(EXPOSE_TEST_OTP=True)
    def test_invitation_without_email_uses_phone_proof(self):
        self.tenant.email = ""
        self.tenant.save(update_fields=["email"])
        invitation = create_tenant_invitation(
            actor=self.owner, tenant=self.tenant
        )
        token = sign_tenant_invitation(invitation)

        registered = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": self.tenant.phone,
                "email": "",
                "password": "Une-phrase-secrete-2026!",
                "password_confirmation": "Une-phrase-secrete-2026!",
                "tenant_invitation_token": token,
            },
            format="json",
        )
        verified = self.client.post(
            "/api/v1/auth/phone-verification/confirm/",
            {
                "phone": self.tenant.phone,
                "code": registered.data["otp_code"],
            },
            format="json",
        )

        self.assertEqual(registered.data["verification_channel"], "SMS")
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, Tenant.Status.ACTIVE)
        self.assertIsNotNone(self.tenant.linked_user)

    def test_existing_verified_account_can_claim_link(self):
        invitation = create_tenant_invitation(
            actor=self.owner, tenant=self.tenant
        )
        user = get_user_model().objects.create_user(
            phone=self.tenant.phone,
            email=self.tenant.email,
            password="password",
        )
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/v1/public-tenant-invitations/claim/",
            {"token": sign_tenant_invitation(invitation)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ACCEPTED")
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.linked_user, user)
