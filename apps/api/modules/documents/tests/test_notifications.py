from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from modules.billing.services import generate_monthly_charges
from modules.accounts.models import AccountOtpChallenge
from modules.accounts.services import issue_account_otp
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
from ..notifications import (
    DeliveryReceipt,
    SimulatedNotificationAdapter,
    build_notification_message,
    process_notification_batch,
)
from ..services import request_document_otp, share_document


class RecordingAdapter:
    def __init__(self, failures=0):
        self.failures = failures
        self.messages = []

    def send(self, message):
        self.messages.append(message)
        if len(self.messages) <= self.failures:
            raise RuntimeError("Fournisseur temporairement indisponible")
        return DeliveryReceipt(provider_reference=f"provider-{len(self.messages)}")


class NotificationProcessingTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            phone="+2250700000990",
            password="password",
            first_name="Awa",
            last_name="Kone",
        )
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Notifications",
                address="Cocody Riviera",
                city="Abidjan",
                commune="Cocody",
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Yao Kouassi",
                phone="+2250500000990",
                email="yao@example.com",
            ),
        )
        lease = create_lease(
            actor=self.owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("100000"),
                due_day=5,
            ),
        )
        activate_lease(actor=self.owner, lease=lease)
        charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]
        payment = record_offline_payment(
            actor=self.owner,
            charge=charge,
            data=RecordOfflinePaymentData(
                amount=Decimal("40000"),
                method=Payment.Method.CASH,
                idempotency_key=uuid4(),
                received_at=timezone.make_aware(datetime(2026, 8, 4, 12, 0)),
            ),
        ).payment
        self.document = payment.rental_documents.get(
            document_type=RentalDocument.Type.PAYMENT_RECEIPT
        )

    def _share(self, *channels):
        return share_document(
            actor=self.owner,
            document=self.document,
            channels=list(channels),
        )

    def test_messages_are_built_from_current_link_and_otp(self):
        shared = self._share(NotificationDelivery.Channel.SMS)
        link_delivery = shared.deliveries[0]
        link_message = build_notification_message(link_delivery)
        requested = request_document_otp(
            access_token=shared.access_token,
            channel=NotificationDelivery.Channel.SMS,
        )
        otp_delivery = NotificationDelivery.objects.get(
            otp_challenge=requested.challenge
        )
        otp_message = build_notification_message(otp_delivery)

        self.assertIn("/documents/", link_message.body)
        self.assertIn(self.document.get_document_type_display().lower(), link_message.body)
        self.assertEqual(link_message.destination, "+2250500000990")
        self.assertIn(requested.code, otp_message.body)
        self.assertNotIn(requested.code, otp_message.metadata.values())

    def test_account_otp_uses_the_same_notification_queue(self):
        issue = issue_account_otp(
            user=self.owner,
            purpose=AccountOtpChallenge.Purpose.PASSWORD_RESET,
        )
        delivery = NotificationDelivery.objects.get(
            account_challenge=issue.challenge
        )

        message = build_notification_message(delivery)

        self.assertEqual(delivery.kind, NotificationDelivery.Kind.ACCOUNT_OTP)
        self.assertEqual(delivery.channel, NotificationDelivery.Channel.SMS)
        self.assertIn(issue.code, message.body)
        self.assertEqual(
            message.metadata["purpose"],
            AccountOtpChallenge.Purpose.PASSWORD_RESET,
        )

    def test_simulation_processes_all_three_channels(self):
        self._share(
            NotificationDelivery.Channel.SMS,
            NotificationDelivery.Channel.EMAIL,
            NotificationDelivery.Channel.WHATSAPP,
        )
        adapter = SimulatedNotificationAdapter()
        summary = process_notification_batch(
            adapters={channel: adapter for channel, _ in NotificationDelivery.Channel.choices}
        )

        self.assertEqual(summary.claimed, 3)
        self.assertEqual(summary.sent, 3)
        self.assertEqual(summary.failed, 0)
        self.assertFalse(
            NotificationDelivery.objects.exclude(
                status=NotificationDelivery.Status.SENT,
                attempt_count=1,
            ).exists()
        )
        self.assertEqual(
            NotificationDelivery.objects.filter(
                provider_reference__startswith="SIM-"
            ).count(),
            3,
        )

    @override_settings(NOTIFICATION_RETRY_SECONDS=60, NOTIFICATION_MAX_ATTEMPTS=3)
    def test_temporary_error_is_retried_with_delay(self):
        delivery = self._share(NotificationDelivery.Channel.SMS).deliveries[0]
        adapter = RecordingAdapter(failures=1)
        now = timezone.now()

        first = process_notification_batch(
            adapters={NotificationDelivery.Channel.SMS: adapter}, now=now
        )
        delivery.refresh_from_db()
        self.assertEqual(first.requeued, 1)
        self.assertEqual(delivery.status, NotificationDelivery.Status.QUEUED)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(delivery.next_attempt_at, now + timedelta(seconds=60))

        too_early = process_notification_batch(
            adapters={NotificationDelivery.Channel.SMS: adapter},
            now=now + timedelta(seconds=59),
        )
        self.assertEqual(too_early.claimed, 0)

        retried = process_notification_batch(
            adapters={NotificationDelivery.Channel.SMS: adapter},
            now=now + timedelta(seconds=60),
        )
        delivery.refresh_from_db()
        self.assertEqual(retried.sent, 1)
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.attempt_count, 2)
        self.assertEqual(delivery.provider_reference, "provider-2")

    def test_missing_adapter_keeps_delivery_untouched(self):
        delivery = self._share(NotificationDelivery.Channel.EMAIL).deliveries[0]

        summary = process_notification_batch(
            adapters={NotificationDelivery.Channel.SMS: RecordingAdapter()}
        )
        delivery.refresh_from_db()

        self.assertEqual(summary.claimed, 0)
        self.assertEqual(summary.unavailable, 1)
        self.assertEqual(delivery.status, NotificationDelivery.Status.QUEUED)
        self.assertEqual(delivery.attempt_count, 0)

    def test_expired_otp_fails_without_retry(self):
        shared = self._share(NotificationDelivery.Channel.SMS)
        requested = request_document_otp(
            access_token=shared.access_token,
            channel=NotificationDelivery.Channel.SMS,
        )
        NotificationDelivery.objects.filter(
            kind=NotificationDelivery.Kind.DOCUMENT_LINK
        ).update(status=NotificationDelivery.Status.SENT)
        requested.challenge.expires_at = timezone.now() - timedelta(seconds=1)
        requested.challenge.save(update_fields=["expires_at"])
        delivery = NotificationDelivery.objects.get(
            otp_challenge=requested.challenge
        )

        summary = process_notification_batch(
            adapters={NotificationDelivery.Channel.SMS: RecordingAdapter()}
        )
        delivery.refresh_from_db()

        self.assertEqual(summary.failed, 1)
        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)
        self.assertIsNone(delivery.next_attempt_at)
        self.assertEqual(delivery.attempt_count, 1)

    @override_settings(NOTIFICATION_PROCESSING_TIMEOUT_SECONDS=300)
    def test_stale_processing_is_recovered(self):
        delivery = self._share(NotificationDelivery.Channel.WHATSAPP).deliveries[0]
        now = timezone.now()
        NotificationDelivery.objects.filter(id=delivery.id).update(
            status=NotificationDelivery.Status.PROCESSING,
            attempt_count=1,
            last_attempt_at=now - timedelta(seconds=301),
        )

        summary = process_notification_batch(
            adapters={
                NotificationDelivery.Channel.WHATSAPP: SimulatedNotificationAdapter()
            },
            now=now,
        )
        delivery.refresh_from_db()

        self.assertEqual(summary.recovered, 1)
        self.assertEqual(summary.sent, 1)
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.attempt_count, 2)

    def test_command_requires_configuration_or_explicit_simulation(self):
        self._share(NotificationDelivery.Channel.SMS)
        with override_settings(
            NOTIFICATION_ADAPTERS={"SMS": "", "EMAIL": "", "WHATSAPP": ""}
        ):
            with self.assertRaises(CommandError):
                call_command("process_notifications")

        output = StringIO()
        call_command("process_notifications", "--simulate", stdout=output)

        self.assertIn("Mode simulation", output.getvalue())
        self.assertIn("envoyees: 1", output.getvalue())
        self.assertEqual(
            NotificationDelivery.objects.get().status,
            NotificationDelivery.Status.SENT,
        )
