from django.test import TestCase

from modules.documents.notifications import (
    DeliveryReceipt,
    NotificationMessage,
    PermanentNotificationError,
)
from modules.notifications.adapters import WhatsAppCloudApiAdapter


class FakeClient:
    def __init__(self, *, permanent=False):
        self.permanent = permanent
        self.calls = []

    def send_text_message(self, *, to, body):
        self.calls.append((to, body))
        if self.permanent:
            from modules.whatsapp.provider import WhatsAppProviderPermanentError

            raise WhatsAppProviderPermanentError("Numéro invalide.")
        return {"messages": [{"id": "wamid.ADAPTER1"}]}


def _message(*, destination="+2250700000001"):
    return NotificationMessage(
        delivery_id="delivery-1",
        channel="WHATSAPP",
        destination=destination,
        subject="Quittance",
        body="Votre quittance de loyer est disponible.",
        metadata={},
    )


class WhatsAppCloudApiAdapterTests(TestCase):
    def test_send_delegates_to_provider_and_returns_receipt(self):
        client = FakeClient()
        adapter = WhatsAppCloudApiAdapter(client=client)
        receipt = adapter.send(_message())

        self.assertIsInstance(receipt, DeliveryReceipt)
        self.assertEqual(receipt.provider_reference, "wamid.ADAPTER1")
        self.assertEqual(client.calls, [("+2250700000001", "Votre quittance de loyer est disponible.")])

    def test_permanent_provider_error_becomes_permanent_notification_error(self):
        adapter = WhatsAppCloudApiAdapter(client=FakeClient(permanent=True))
        with self.assertRaises(PermanentNotificationError):
            adapter.send(_message())
