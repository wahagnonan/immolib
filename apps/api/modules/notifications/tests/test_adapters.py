import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from modules.documents.notifications import (
    NotificationMessage,
    PermanentNotificationError,
)

from ..adapters import AmazonSesEmailAdapter, FirebasePushAdapter, WebPushVapidAdapter


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

    @override_settings(
        AWS_SES_FROM_EMAIL="no-reply@example.com",
        AWS_SES_CONFIGURATION_SET="immolib-prod",
    )
    def test_ses_adapter_includes_configuration_set(self):
        client = FakeSesClient()
        adapter = AmazonSesEmailAdapter(client=client)

        adapter.send(message("EMAIL", "tenant@example.com"))

        self.assertEqual(
            client.payload["ConfigurationSetName"], "immolib-prod"
        )

    @override_settings(
        AWS_SES_FROM_EMAIL="no-reply@example.com",
        AWS_SES_CONFIGURATION_SET="",
    )
    def test_ses_adapter_omits_configuration_set_when_unset(self):
        client = FakeSesClient()
        adapter = AmazonSesEmailAdapter(client=client)

        adapter.send(message("EMAIL", "tenant@example.com"))

        self.assertNotIn("ConfigurationSetName", client.payload)

    def test_firebase_adapter_returns_provider_reference(self):
        sent = []
        adapter = FirebasePushAdapter(
            sender=lambda notification: sent.append(notification) or "fcm-123"
        )

        receipt = adapter.send(message("PUSH", "token-123"))

        self.assertEqual(receipt.provider_reference, "fcm-123")
        self.assertEqual(sent[0].destination, "token-123")


@override_settings(
    VAPID_PRIVATE_KEY="private-key",
    VAPID_SUBJECT="https://immolib.ci",
)
class WebPushVapidAdapterTests(SimpleTestCase):
    def _subscription_json(self) -> str:
        return json.dumps(
            {
                "endpoint": "https://push.example.com/abc",
                "keys": {"p256dh": "p256dh", "auth": "auth"},
            }
        )

    @patch("pywebpush.webpush")
    def test_sends_encrypted_payload_and_returns_reference(self, mock_webpush):
        class FakeResponse:
            headers = {"Location": "push-ref-42"}

        mock_webpush.return_value = FakeResponse()
        adapter = WebPushVapidAdapter()

        receipt = adapter.send(message("PUSH", self._subscription_json()))

        self.assertEqual(receipt.provider_reference, "push-ref-42")
        sent_kwargs = mock_webpush.call_args.kwargs
        self.assertEqual(sent_kwargs["ttl"], 604800)
        self.assertEqual(
            sent_kwargs["vapid_private_key"], "private-key"
        )
        self.assertEqual(sent_kwargs["vapid_claims"], {"sub": "https://immolib.ci"})
        payload = json.loads(sent_kwargs["data"])
        self.assertEqual(payload["title"], "Rappel ImmoLib")
        self.assertEqual(payload["url"], "/echeances")

    @patch("pywebpush.webpush")
    def test_expired_subscription_is_permanent(self, mock_webpush):
        from pywebpush import WebPushException

        def fail(**kwargs):
            response = type("Response", (), {"status_code": 410})()
            raise WebPushException("gone", response=response)

        mock_webpush.side_effect = fail
        adapter = WebPushVapidAdapter()

        with self.assertRaises(PermanentNotificationError):
            adapter.send(message("PUSH", self._subscription_json()))

    def test_unreadable_destination_is_permanent(self):
        adapter = WebPushVapidAdapter()

        with self.assertRaises(PermanentNotificationError):
            adapter.send(message("PUSH", "pas-du-json"))
