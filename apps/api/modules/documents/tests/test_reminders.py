from datetime import date, datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.billing.models import RentCharge
from modules.billing.services import generate_monthly_charges
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house
from modules.subscriptions.services import upgrade

from ..models import NotificationDelivery
from ..notifications import build_notification_message, process_notification_batch
from ..reminders import queue_rent_reminders


class RecordingAdapter:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class RentReminderTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            phone="+2250700000910", password="password"
        )
        self.outsider = get_user_model().objects.create_user(
            phone="+2250700000911", password="password"
        )
        upgrade(self.owner, "essential")
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Rappels",
                address="Yopougon Niangon",
                city="Abidjan",
                commune="Yopougon",
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Mariam Koffi",
                phone="+2250500000910",
                email="mariam@example.com",
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
        self.charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]

    def test_due_soon_reminders_are_idempotent_per_channel(self):
        first = queue_rent_reminders(
            today=date(2026, 8, 2),
            offsets=(-3,),
            channels=("SMS", "EMAIL"),
        )
        second = queue_rent_reminders(
            today=date(2026, 8, 2),
            offsets=(-3,),
            channels=("SMS", "EMAIL"),
        )

        self.assertEqual(first.eligible_charges, 1)
        self.assertEqual(first.created, 2)
        self.assertEqual(second.created, 0)
        self.assertEqual(second.existing, 2)
        self.assertEqual(NotificationDelivery.objects.count(), 2)
        self.assertFalse(
            NotificationDelivery.objects.exclude(
                kind=NotificationDelivery.Kind.RENT_REMINDER,
                scheduled_for=date(2026, 8, 2),
                access_link=None,
            ).exists()
        )

    def test_auto_route_uses_email_for_unregistered_tenant(self):
        summary = queue_rent_reminders(
            today=date(2026, 8, 2),
            offsets=(-3,),
            channels=("AUTO",),
        )

        self.assertEqual(summary.created, 1)
        delivery = NotificationDelivery.objects.get()
        self.assertEqual(delivery.channel, NotificationDelivery.Channel.EMAIL)
        self.assertEqual(delivery.destination, "mariam@example.com")

    def test_paid_disputed_or_cancelled_charge_is_not_reminded(self):
        for charge_status in (
            RentCharge.Status.PAID,
            RentCharge.Status.DISPUTED,
            RentCharge.Status.CANCELLED,
        ):
            self.charge.status = charge_status
            if charge_status == RentCharge.Status.PAID:
                self.charge.amount_paid = self.charge.amount_due
            else:
                self.charge.amount_paid = Decimal("0")
            self.charge.save(update_fields=["status", "amount_paid"])

            summary = queue_rent_reminders(
                today=date(2026, 8, 2), offsets=(-3,), channels=("SMS",)
            )

            self.assertEqual(summary.created, 0)

    def test_missing_email_is_skipped_without_blocking_sms(self):
        tenant = self.charge.lease.tenant
        tenant.email = ""
        tenant.save(update_fields=["email"])

        summary = queue_rent_reminders(
            today=date(2026, 8, 2),
            offsets=(-3,),
            channels=("EMAIL", "SMS"),
        )

        self.assertEqual(summary.created, 1)
        self.assertEqual(summary.skipped_destinations, 1)
        self.assertEqual(NotificationDelivery.objects.get().channel, "SMS")

    def test_message_uses_current_balance_and_delay(self):
        queue_rent_reminders(
            today=date(2026, 8, 8), offsets=(3,), channels=("SMS",)
        )
        delivery = NotificationDelivery.objects.select_related(
            "rent_charge__lease__tenant", "rent_charge__lease__property"
        ).get()

        message = build_notification_message(
            delivery,
            now=timezone.make_aware(datetime(2026, 8, 8, 8, 0)),
        )

        self.assertIn("100 000 FCFA", message.body)
        self.assertIn("retard depuis 3 jours", message.body)
        self.assertIn("Maison Rappels", message.body)
        self.assertEqual(message.metadata["rent_charge_id"], str(self.charge.id))

    def test_queued_reminder_is_cancelled_if_charge_gets_paid(self):
        queue_rent_reminders(
            today=date(2026, 8, 2), offsets=(-3,), channels=("SMS",)
        )
        self.charge.amount_paid = self.charge.amount_due
        self.charge.status = RentCharge.Status.PAID
        self.charge.save(update_fields=["amount_paid", "status"])
        adapter = RecordingAdapter()

        summary = process_notification_batch(adapters={"SMS": adapter})

        delivery = NotificationDelivery.objects.get()
        self.assertEqual(summary.failed, 1)
        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)
        self.assertEqual(adapter.messages, [])

    @override_settings(
        RENT_REMINDER_OFFSETS_DAYS=(-3,), RENT_REMINDER_CHANNELS=("SMS",)
    )
    def test_billing_cycle_queues_reminders_and_can_be_replayed(self):
        first_output = StringIO()
        second_output = StringIO()

        call_command(
            "run_billing_cycle",
            "--period",
            "2026-08",
            "--today",
            "2026-08-02",
            stdout=first_output,
        )
        call_command(
            "run_billing_cycle",
            "--period",
            "2026-08",
            "--today",
            "2026-08-02",
            stdout=second_output,
        )

        self.assertIn("1 rappel(s) cree(s)", first_output.getvalue())
        self.assertIn("1 rappel(s) deja present(s)", second_output.getvalue())
        self.assertEqual(NotificationDelivery.objects.count(), 1)

    def test_owner_sees_reminder_context_but_outsider_does_not(self):
        queue_rent_reminders(
            today=date(2026, 8, 2), offsets=(-3,), channels=("SMS",)
        )
        self.client.force_authenticate(self.owner)

        owner_response = self.client.get("/api/v1/notification-deliveries/")
        self.client.force_authenticate(self.outsider)
        outsider_response = self.client.get("/api/v1/notification-deliveries/")

        self.assertEqual(owner_response.status_code, status.HTTP_200_OK)
        self.assertEqual(owner_response.data[0]["kind"], "RENT_REMINDER")
        self.assertEqual(owner_response.data[0]["context_label"], "Loyer 2026-08")
        self.assertEqual(owner_response.data[0]["house_name"], "Maison Rappels")
        self.assertEqual(owner_response.data[0]["tenant_name"], "Mariam Koffi")
        self.assertIsNone(owner_response.data[0]["document_id"])
        self.assertEqual(outsider_response.status_code, status.HTTP_200_OK)
        self.assertEqual(outsider_response.data, [])
