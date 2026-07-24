from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.billing.services import generate_monthly_charges
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.payments.models import Payment
from modules.payments.services import RecordOfflinePaymentData, record_offline_payment
from modules.properties.services import CreateHouseData, create_house

from ..models import NotificationDelivery, RentalDocument
from ..notifications import SimulatedNotificationAdapter, process_notification_batch


class PublicDocumentFlowApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000800", password="password"
        )
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Treichville",
                address="Avenue 8",
                city="Abidjan",
                commune="Treichville",
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Ali Diarra",
                phone="+2250500000800",
                email="ali@example.com",
            ),
        )
        lease = create_lease(
            actor=self.owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("90000"),
                due_day=5,
            ),
        )
        activate_lease(actor=self.owner, lease=lease)
        charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]
        self.payment = record_offline_payment(
            actor=self.owner,
            charge=charge,
            data=RecordOfflinePaymentData(
                amount=Decimal("40000"),
                method=Payment.Method.CASH,
                idempotency_key=uuid4(),
                received_at=timezone.make_aware(datetime(2026, 8, 4, 8, 0)),
            ),
        ).payment
        self.document = self.payment.rental_documents.get(
            document_type=RentalDocument.Type.PAYMENT_RECEIPT
        )

    @override_settings(EXPOSE_TEST_OTP=True)
    def test_guest_opens_receipt_and_confirms_payment(self):
        self.client.force_authenticate(self.owner)
        share_response = self.client.post(
            f"/api/v1/documents/{self.document.id}/share/",
            {"channels": ["SMS", "WHATSAPP"]},
            format="json",
        )
        self.client.force_authenticate(user=None)
        access_token = share_response.data["secure_url"].rsplit("/", 1)[-1]

        otp_response = self.client.post(
            "/api/v1/public-access/request-otp/",
            {"access_token": access_token, "channel": "SMS"},
            format="json",
        )
        verify_response = self.client.post(
            "/api/v1/public-access/verify-otp/",
            {
                "challenge_id": otp_response.data["challenge_id"],
                "code": otp_response.data["otp_code"],
            },
            format="json",
        )
        grant = verify_response.data["grant_token"]
        document_response = self.client.post(
            "/api/v1/public-access/view-document/",
            {"grant_token": grant},
            format="json",
        )
        confirm_response = self.client.post(
            "/api/v1/public-access/payment-response/",
            {"grant_token": grant, "action": "CONFIRM"},
            format="json",
        )

        self.assertEqual(share_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(share_response.data["deliveries"]), 2)
        self.assertEqual(otp_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(document_response.data["reference"], self.document.reference)
        self.assertEqual(
            confirm_response.data["status"], Payment.Status.CONFIRMED_BY_TENANT
        )

    @override_settings(EXPOSE_TEST_OTP=True)
    def test_guest_can_dispute_payment_with_reason(self):
        self.client.force_authenticate(self.owner)
        shared = self.client.post(
            f"/api/v1/documents/{self.document.id}/share/",
            {"channels": ["EMAIL"]},
            format="json",
        )
        self.client.force_authenticate(user=None)
        access_token = shared.data["secure_url"].rsplit("/", 1)[-1]
        requested = self.client.post(
            "/api/v1/public-access/request-otp/",
            {"access_token": access_token, "channel": "EMAIL"},
            format="json",
        )
        verified = self.client.post(
            "/api/v1/public-access/verify-otp/",
            {
                "challenge_id": requested.data["challenge_id"],
                "code": requested.data["otp_code"],
            },
            format="json",
        )

        response = self.client.post(
            "/api/v1/public-access/payment-response/",
            {
                "grant_token": verified.data["grant_token"],
                "action": "DISPUTE",
                "reason": "Je ne reconnais pas ce versement",
            },
            format="json",
        )

        self.assertEqual(
            response.data["status"], Payment.Status.DISPUTED_BY_TENANT
        )

    def test_otp_is_not_exposed_by_default(self):
        self.client.force_authenticate(self.owner)
        shared = self.client.post(
            f"/api/v1/documents/{self.document.id}/share/",
            {"channels": ["SMS"]},
            format="json",
        )
        self.client.force_authenticate(user=None)
        access_token = shared.data["secure_url"].rsplit("/", 1)[-1]

        response = self.client.post(
            "/api/v1/public-access/request-otp/",
            {"access_token": access_token, "channel": "SMS"},
            format="json",
        )

        self.assertNotIn("otp_code", response.data)

    def test_owner_lists_masked_delivery_statuses(self):
        self.client.force_authenticate(self.owner)
        shared = self.client.post(
            f"/api/v1/documents/{self.document.id}/share/",
            {"channels": ["SMS", "EMAIL"]},
            format="json",
        )
        adapter = SimulatedNotificationAdapter()
        process_notification_batch(
            adapters={"SMS": adapter, "EMAIL": adapter, "WHATSAPP": adapter}
        )

        response = self.client.get(
            f"/api/v1/notification-deliveries/?document_id={self.document.id}"
        )

        self.assertEqual(shared.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual({item["status"] for item in response.data}, {"SENT"})
        self.assertEqual({item["attempt_count"] for item in response.data}, {1})
        self.assertEqual(
            {item["masked_destination"] for item in response.data},
            {"***0800", "al***@example.com"},
        )
        self.assertNotContains(response, "+2250500000800")
        self.assertTrue(
            all(item["document_id"] == str(self.document.id) for item in response.data)
        )

    def test_owner_prepares_manual_whatsapp_share_without_delivery(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            f"/api/v1/documents/{self.document.id}/manual-share/",
            {"channel": "WHATSAPP"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["action_url"].startswith("https://wa.me/225"))
        self.assertIn("/documents/", response.data["secure_url"])
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_other_owner_cannot_list_delivery_statuses(self):
        self.client.force_authenticate(self.owner)
        self.client.post(
            f"/api/v1/documents/{self.document.id}/share/",
            {"channels": [NotificationDelivery.Channel.SMS]},
            format="json",
        )
        stranger = get_user_model().objects.create_user(
            phone="+2250700000899", password="password"
        )
        self.client.force_authenticate(stranger)

        response = self.client.get("/api/v1/notification-deliveries/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_owner_downloads_document_pdf(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(f"/api/v1/documents/{self.document.id}/pdf/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(self.document.reference, response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertGreater(len(response.content), 10_000)

    def test_other_owner_cannot_download_document_pdf(self):
        stranger = get_user_model().objects.create_user(
            phone="+2250700000888", password="password"
        )
        self.client.force_authenticate(stranger)

        response = self.client.get(f"/api/v1/documents/{self.document.id}/pdf/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(EXPOSE_TEST_OTP=True)
    def test_verified_guest_downloads_document_pdf(self):
        self.client.force_authenticate(self.owner)
        shared = self.client.post(
            f"/api/v1/documents/{self.document.id}/share/",
            {"channels": ["SMS"]},
            format="json",
        )
        self.client.force_authenticate(user=None)
        access_token = shared.data["secure_url"].rsplit("/", 1)[-1]
        requested = self.client.post(
            "/api/v1/public-access/request-otp/",
            {"access_token": access_token, "channel": "SMS"},
            format="json",
        )
        verified = self.client.post(
            "/api/v1/public-access/verify-otp/",
            {
                "challenge_id": requested.data["challenge_id"],
                "code": requested.data["otp_code"],
            },
            format="json",
        )

        response = self.client.post(
            "/api/v1/public-access/download-document/",
            {"grant_token": verified.data["grant_token"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_guest_cannot_download_pdf_with_invalid_grant(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/v1/public-access/download-document/",
            {"grant_token": "invalid"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anyone_can_verify_document_reference(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(
            "/api/v1/public-access/verify-reference/",
            {"reference": self.document.reference.lower()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["authentic"])
        self.assertEqual(response.data["reference"], self.document.reference)
        self.assertEqual(response.data["status"], RentalDocument.Status.ACTIVE)
        self.assertNotIn("tenant_phone", response.data)
        self.assertNotIn("owner_phone", response.data)
        self.assertNotIn("payment_id", response.data)
        self.assertNotIn("tenant_name", response.data)
        self.assertNotIn("owner_name", response.data)
        self.assertNotIn("house_name", response.data)
        self.assertNotIn("house_address", response.data)
        self.assertNotIn("payment_method", response.data)

    def test_unknown_document_reference_is_not_found(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(
            "/api/v1/public-access/verify-reference/",
            {"reference": "IMM-QUT-2026-INCONNUE"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
