from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.billing.services import generate_monthly_charges
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.payments.models import Payment
from modules.payments.services import (
    RecordOfflinePaymentData,
    cancel_payment,
    record_offline_payment,
)
from modules.properties.services import CreateHouseData, create_house

from ..models import ManualShareEvent, NotificationDelivery, RentalDocument
from ..services import (
    request_document_otp,
    prepare_manual_share,
    resolve_document_grant,
    share_document,
    verify_document_otp,
)


class RentalDocumentServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000700",
            password="password",
            first_name="Jean",
            last_name="Soro",
        )
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Marcory",
                address="Marcory Zone 4",
                city="Abidjan",
                commune="Marcory",
            ),
        )
        self.tenant = create_tenant(
            actor=self.owner,
            property=self.house,
            data=CreateTenantData(
                full_name="Fatou Kone",
                phone="+2250500000700",
                email="fatou@example.com",
            ),
        )
        lease = create_lease(
            actor=self.owner,
            property=self.house,
            tenant=self.tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("100000"),
                due_day=5,
            ),
        )
        activate_lease(actor=self.owner, lease=lease)
        self.charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]
        self.received_at = timezone.make_aware(datetime(2026, 8, 4, 12, 0))

    def _record(self, amount):
        return record_offline_payment(
            actor=self.owner,
            charge=self.charge,
            data=RecordOfflinePaymentData(
                amount=Decimal(amount),
                method=Payment.Method.CASH,
                idempotency_key=uuid4(),
                received_at=self.received_at,
            ),
        ).payment

    def test_partial_payment_creates_receipt_but_not_rent_receipt(self):
        payment = self._record("40000")

        receipt = payment.rental_documents.get()
        self.assertEqual(
            receipt.document_type, RentalDocument.Type.PAYMENT_RECEIPT
        )
        self.assertEqual(receipt.amount, Decimal("40000"))
        self.assertEqual(receipt.tenant_name, "Fatou Kone")
        self.assertEqual(receipt.owner_name, "Jean Soro")
        self.assertFalse(
            RentalDocument.objects.filter(
                document_type=RentalDocument.Type.RENT_RECEIPT
            ).exists()
        )

    def test_full_payment_creates_one_rent_receipt(self):
        self._record("40000")
        last_payment = self._record("60000")

        self.assertEqual(
            RentalDocument.objects.filter(
                document_type=RentalDocument.Type.PAYMENT_RECEIPT
            ).count(),
            2,
        )
        rent_receipt = RentalDocument.objects.get(
            document_type=RentalDocument.Type.RENT_RECEIPT
        )
        self.assertEqual(rent_receipt.payment, last_payment)
        self.assertEqual(rent_receipt.amount, Decimal("100000"))
        self.assertTrue(rent_receipt.reference.startswith("IMM-QUT-"))

    def test_document_snapshot_does_not_change_with_tenant_name(self):
        payment = self._record("40000")
        document = payment.rental_documents.get()

        self.tenant.full_name = "Nouveau nom"
        self.tenant.save(update_fields=["full_name"])
        document.refresh_from_db()

        self.assertEqual(document.tenant_name, "Fatou Kone")

    def test_cancelling_last_payment_voids_receipt_and_quittance(self):
        self._record("40000")
        payment = self._record("60000")

        cancel_payment(
            actor=self.owner,
            payment=payment,
            reason="Paiement attribue au mauvais mois",
        )

        self.assertFalse(
            RentalDocument.objects.filter(
                payment=payment, status=RentalDocument.Status.ACTIVE
            ).exists()
        )
        self.assertFalse(
            RentalDocument.objects.filter(
                rent_charge=self.charge,
                document_type=RentalDocument.Type.RENT_RECEIPT,
                status=RentalDocument.Status.ACTIVE,
            ).exists()
        )

    def test_owner_can_queue_same_link_for_multiple_channels(self):
        document = self._record("40000").rental_documents.get()

        result = share_document(
            actor=self.owner,
            document=document,
            channels=["SMS", "EMAIL", "WHATSAPP"],
        )

        self.assertEqual(len(result.deliveries), 3)
        self.assertEqual(
            set(item.channel for item in result.deliveries),
            {"SMS", "EMAIL", "WHATSAPP"},
        )
        self.assertEqual(result.access_link.deliveries.count(), 3)
        self.assertTrue(result.secure_url.startswith("http://localhost:3000/documents/"))

    def test_email_share_requires_tenant_email(self):
        document = self._record("40000").rental_documents.get()
        document.tenant_email = ""
        document.save(update_fields=["tenant_email"])

        with self.assertRaisesMessage(ValidationError, "adresse email"):
            share_document(
                actor=self.owner,
                document=document,
                channels=[NotificationDelivery.Channel.EMAIL],
            )

    def test_manual_whatsapp_share_creates_link_without_queued_delivery(self):
        document = self._record("40000").rental_documents.get()

        result = prepare_manual_share(
            actor=self.owner,
            document=document,
            channel=ManualShareEvent.Channel.WHATSAPP,
        )

        self.assertTrue(result.action_url.startswith("https://wa.me/225"))
        self.assertIn("consultez%20votre", result.action_url)
        self.assertEqual(result.event.destination, document.tenant_phone)
        self.assertEqual(NotificationDelivery.objects.count(), 0)
        self.assertEqual(ManualShareEvent.objects.count(), 1)

    def test_otp_grant_opens_document(self):
        document = self._record("40000").rental_documents.get()
        shared = share_document(
            actor=self.owner,
            document=document,
            channels=[NotificationDelivery.Channel.SMS],
        )
        requested = request_document_otp(
            access_token=shared.access_token,
            channel=NotificationDelivery.Channel.SMS,
        )

        grant = verify_document_otp(
            challenge_id=requested.challenge.id,
            code=requested.code,
        )

        self.assertEqual(resolve_document_grant(grant), document)

    def test_wrong_otp_increments_attempt_counter(self):
        document = self._record("40000").rental_documents.get()
        shared = share_document(
            actor=self.owner,
            document=document,
            channels=[NotificationDelivery.Channel.SMS],
        )
        requested = request_document_otp(
            access_token=shared.access_token,
            channel=NotificationDelivery.Channel.SMS,
        )

        with self.assertRaises(ValidationError):
            verify_document_otp(
                challenge_id=requested.challenge.id,
                code="000000" if requested.code != "000000" else "999999",
            )

        requested.challenge.refresh_from_db()
        self.assertEqual(requested.challenge.attempts, 1)

    def test_repeated_otp_request_during_cooldown_reuses_challenge(self):
        document = self._record("40000").rental_documents.get()
        shared = share_document(
            actor=self.owner,
            document=document,
            channels=[NotificationDelivery.Channel.SMS],
        )

        first = request_document_otp(
            access_token=shared.access_token,
            channel=NotificationDelivery.Channel.SMS,
        )
        second = request_document_otp(
            access_token=shared.access_token,
            channel=NotificationDelivery.Channel.SMS,
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.challenge.id, second.challenge.id)
        self.assertEqual(
            NotificationDelivery.objects.filter(
                kind=NotificationDelivery.Kind.OTP
            ).count(),
            1,
        )
