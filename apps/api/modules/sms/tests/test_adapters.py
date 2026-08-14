from decimal import Decimal
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from modules.documents.notifications import (
    NotificationMessage,
    PermanentNotificationError,
)
from modules.sms.adapters import OrangeSmsAdapter
from modules.sms.models import SmsSendRecord
from modules.sms.provider import OrangeProviderPermanentError

from .helpers import build_delivery


class FakeClient:
    def __init__(self, resource_id="resource-123", permanent=False):
        self.resource_id = resource_id
        self.permanent = permanent
        self.calls = []

    def send_sms(self, *, recipient, message, client_correlator):
        self.calls.append((recipient, message, client_correlator))
        if self.permanent:
            raise OrangeProviderPermanentError("Numero invalide.")
        return self.resource_id


def message(
    *,
    destination="+2250700000001",
    body="Bonjour Yao",
    delivery_id="",
    metadata=None,
):
    return NotificationMessage(
        delivery_id=delivery_id,
        channel="SMS",
        destination=destination,
        subject="ImmoLib",
        body=body,
        metadata=metadata or {},
    )


@override_settings(ORANGE_SMS_COST_PER_SEGMENT_XOF=10)
class OrangeSmsAdapterTests(TestCase):
    def test_send_records_send_and_returns_receipt(self):
        client = FakeClient()
        adapter = OrangeSmsAdapter(client=client, rate_per_second=0)

        receipt = adapter.send(message())

        recipient, text, correlator = client.calls[0]
        self.assertEqual((recipient, text), ("+2250700000001", "Bonjour Yao"))
        # Sans delivery_id, l'adaptateur genere un correlator (echo Orange).
        self.assertEqual(receipt.provider_reference, correlator)
        self.assertEqual(len(correlator), 36)
        record = SmsSendRecord.objects.get(provider_message_id="resource-123")
        self.assertEqual(record.recipient, "+2250700000001")
        self.assertEqual(record.segments_count, 1)
        self.assertEqual(record.estimated_cost_xof, Decimal("10"))
        self.assertIsNone(record.delivery_id)

    def test_send_uses_delivery_id_as_correlator(self):
        delivery = build_delivery()
        client = FakeClient()
        adapter = OrangeSmsAdapter(client=client, rate_per_second=0)

        receipt = adapter.send(message(delivery_id=str(delivery.id)))

        recipient, text, correlator = client.calls[0]
        self.assertEqual(correlator, str(delivery.id))
        # Le correlator est l'echo du callbackData Orange : c'est lui qu'on
        # stocke comme reference pour correler le Delivery Receipt.
        self.assertEqual(receipt.provider_reference, str(delivery.id))

    def test_send_updates_delivery_segments_count(self):
        delivery = build_delivery()
        client = FakeClient()
        adapter = OrangeSmsAdapter(client=client, rate_per_second=0)

        adapter.send(message(delivery_id=str(delivery.id)))

        record = SmsSendRecord.objects.get(provider_message_id="resource-123")
        self.assertEqual(record.delivery_id, delivery.id)
        delivery.refresh_from_db()
        self.assertEqual(delivery.segments_count, 1)

    def test_permanent_provider_error_raises_permanent(self):
        client = FakeClient(permanent=True)
        adapter = OrangeSmsAdapter(client=client, rate_per_second=0)

        with self.assertRaises(PermanentNotificationError):
            adapter.send(message())

        self.assertEqual(SmsSendRecord.objects.count(), 0)

    def test_invalid_phone_raises_permanent_without_calling_provider(self):
        client = FakeClient()
        adapter = OrangeSmsAdapter(client=client, rate_per_second=0)

        with self.assertRaises(PermanentNotificationError):
            adapter.send(message(destination="12ab"))

        self.assertEqual(client.calls, [])
        self.assertEqual(SmsSendRecord.objects.count(), 0)

    def test_long_message_truncated_with_ellipsis(self):
        client = FakeClient()
        adapter = OrangeSmsAdapter(
            client=client, rate_per_second=0, max_chars=160
        )

        adapter.send(message(body="x" * 200))

        text = client.calls[0][1]
        self.assertEqual(len(text), 160)
        self.assertTrue(text.endswith("…"))

    def test_long_message_keeps_link(self):
        client = FakeClient()
        adapter = OrangeSmsAdapter(
            client=client, rate_per_second=0, max_chars=160
        )
        link = "https://app.immolib.ci/documents/abc"

        adapter.send(message(body="x" * 200, metadata={"url": link}))

        text = client.calls[0][1]
        self.assertLessEqual(len(text), 160)
        self.assertTrue(text.endswith(link))

    def test_short_message_with_link_is_not_truncated(self):
        client = FakeClient()
        adapter = OrangeSmsAdapter(client=client, rate_per_second=0)
        link = "https://app.immolib.ci/documents/abc"

        adapter.send(message(body="Quittance", metadata={"url": link}))

        self.assertEqual(client.calls[0][1], "Quittance")

    def test_resend_after_partial_failure_records_both_sends(self):
        delivery = build_delivery()
        client = FakeClient()
        adapter = OrangeSmsAdapter(client=client, rate_per_second=0)
        adapter.send(message(delivery_id=str(delivery.id)))

        # Le worker retente (file au moins une fois) : un second envoi reussi
        # ne doit pas faire planter l'enregistrement (OneToOne aurait leve
        # une IntegrityError).
        client.resource_id = "resource-456"
        adapter.send(message(delivery_id=str(delivery.id)))

        records = SmsSendRecord.objects.filter(delivery_id=delivery.id).order_by(
            "sent_at"
        )
        self.assertEqual(list(records.values_list("provider_message_id", flat=True)),
            ["resource-123", "resource-456"],
        )
        delivery.refresh_from_db()
        self.assertEqual(delivery.segments_count, 1)

    def test_pace_sleeps_between_sends(self):
        client = FakeClient()
        sleeps = []
        adapter = OrangeSmsAdapter(
            client=client,
            rate_per_second=2,
            _now=lambda: 0.0,
            _sleep=sleeps.append,
        )

        adapter.send(message())
        adapter.send(message())

        self.assertEqual(sleeps, [0.5, 0.5])

    def test_rate_limit_zero_disables_pacing(self):
        client = FakeClient()
        sleeps = []
        adapter = OrangeSmsAdapter(
            client=client,
            rate_per_second=0,
            _now=lambda: 0.0,
            _sleep=sleeps.append,
        )

        adapter.send(message())
        adapter.send(message())

        self.assertEqual(sleeps, [])

    def test_non_positive_max_chars_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            OrangeSmsAdapter(max_chars=0)
