from django.test import SimpleTestCase, override_settings

from modules.documents.notifications import NotificationMessage

from ..adapters import AmazonSesEmailAdapter, FirebasePushAdapter


def message(channel: str, destination: str) -> NotificationMessage:
    return NotificationMessage(
        delivery_id="delivery-1",
        channel=channel,
        destination=destination,
        subject="Rappel ImmoLib",
        body="Bonjour, votre échéance est disponible.",
        metadata={"kind": "RENT_REMINDER", "url": "/echeances"},
    )


class FakeSesClient:
    def __init__(self):
        self.payload = None

    def send_email(self, **payload):
        self.payload = payload
        return {"MessageId": "ses-123"}


class NotificationAdapterTests(SimpleTestCase):
    @override_settings(AWS_SES_FROM_EMAIL="ImmoLib <no-reply@example.com>")
    def test_ses_adapter_sends_utf8_text_and_html(self):
        client = FakeSesClient()
        adapter = AmazonSesEmailAdapter(client=client)

        receipt = adapter.send(message("EMAIL", "tenant@example.com"))

        self.assertEqual(receipt.provider_reference, "ses-123")
        self.assertEqual(
            client.payload["Destination"]["ToAddresses"], ["tenant@example.com"]
        )
        self.assertEqual(client.payload["Message"]["Subject"]["Charset"], "UTF-8")
        self.assertIn(
            "votre échéance",
            client.payload["Message"]["Body"]["Text"]["Data"],
        )

    def test_firebase_adapter_returns_provider_reference(self):
        sent = []
        adapter = FirebasePushAdapter(
            sender=lambda notification: sent.append(notification) or "fcm-123"
        )

        receipt = adapter.send(message("PUSH", "token-123"))

        self.assertEqual(receipt.provider_reference, "fcm-123")
        self.assertEqual(sent[0].destination, "token-123")
