import json

from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from modules.whatsapp.provider import (
    WhatsAppCloudApiClient,
    WhatsAppProviderError,
    WhatsAppProviderPermanentError,
)

MESSAGE_PAYLOAD = {
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": "2250700000001",
    "type": "text",
    "text": {"preview_url": False, "body": "Quittance de loyer"},
}

API_RESPONSE = {
    "messaging_product": "whatsapp",
    "contacts": [{"input": "2250700000001", "wa_id": "2250700000001"}],
    "messages": [{"id": "wamid.ABC123"}],
}


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    def post(self, url, *, json, headers, timeout):
        self.last_kwargs = {"url": url, "json": json, "headers": headers}
        return self.response


@override_settings(
    WHATSAPP_ACCESS_TOKEN="test-token",
    WHATSAPP_PHONE_NUMBER_ID="123456",
    WHATSAPP_API_VERSION="v24.0",
    WHATSAPP_GRAPH_BASE_URL="https://graph.facebook.com",
)
class WhatsAppCloudApiClientTests(TestCase):
    def test_unconfigured_client_raises(self):
        with override_settings(WHATSAPP_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID=""):
            with self.assertRaises(ImproperlyConfigured):
                WhatsAppCloudApiClient()

    def test_send_text_message_strips_plus_and_bears_token(self):
        session = FakeSession(FakeResponse(200, API_RESPONSE))
        client = WhatsAppCloudApiClient(session=session)
        result = client.send_text_message(to="+2250700000001", body="Quittance de loyer")

        self.assertEqual(result["messages"][0]["id"], "wamid.ABC123")
        self.assertIn("https://graph.facebook.com/v24.0/123456/messages", session.last_kwargs["url"])
        self.assertEqual(session.last_kwargs["headers"]["Authorization"], "Bearer test-token")
        self.assertEqual(session.last_kwargs["json"], MESSAGE_PAYLOAD)

    def test_send_text_message_truncates_long_body(self):
        session = FakeSession(FakeResponse(200, API_RESPONSE))
        client = WhatsAppCloudApiClient(session=session)
        client.send_text_message(to="2250700000001", body="x" * 5000)
        body = session.last_kwargs["json"]["text"]["body"]
        self.assertEqual(len(body), 4096)

    def test_send_template_message_builds_template_payload(self):
        session = FakeSession(FakeResponse(200, API_RESPONSE))
        client = WhatsAppCloudApiClient(session=session)
        client.send_template_message(
            to="2250700000001",
            template_name="quittance_loyer",
            language="fr",
            components=[{"type": "body", "parameters": [{"text": "Montant"}]}],
        )
        payload = session.last_kwargs["json"]
        self.assertEqual(payload["type"], "template")
        self.assertEqual(payload["template"]["name"], "quittance_loyer")
        self.assertEqual(payload["template"]["language"]["code"], "fr")
        self.assertIn("components", payload["template"])

    def test_permanent_error_code_raises_permanent_error(self):
        error = {
            "error": {
                "code": 131026,
                "message": "The phone number is not a valid phone number.",
            }
        }
        session = FakeSession(FakeResponse(404, error))
        client = WhatsAppCloudApiClient(session=session)
        with self.assertRaises(WhatsAppProviderPermanentError):
            client.send_text_message(to="2250700000001", body="Quittance")

    def test_transient_error_raises_provider_error(self):
        session = FakeSession(FakeResponse(500, {"error": {"message": "Server error"}}))
        client = WhatsAppCloudApiClient(session=session)
        with self.assertRaises(WhatsAppProviderError):
            client.send_text_message(to="2250700000001", body="Quittance")
