from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from modules.sms.provider import (
    OrangeProviderError,
    OrangeProviderPermanentError,
    OrangeSmsApiClient,
)


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, *, json=None, data=None, headers=None, timeout=None):
        self.calls.append(
            {"url": url, "json": json, "data": data, "headers": headers}
        )
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return response


TOKEN_PAYLOAD = {"access_token": "t0k3n", "token_type": "Bearer"}
SEND_PAYLOAD = {
    "outboundSMSMessageRequest": {
        "address": "tel:+2250700000001",
        "senderAddress": "tel:+2250000",
        "outboundSMSTextMessage": {"message": "Quittance de loyer"},
        "clientCorrelator": "immolib-uuid-123",
        "senderName": "ImmoLib",
    }
}


@override_settings(
    ORANGE_SMS_CLIENT_ID="client-id",
    ORANGE_SMS_CLIENT_SECRET="client-secret",
    ORANGE_SMS_BASE_URL="https://api.orange.com",
    ORANGE_SMS_SENDER_ADDRESS="tel:+2250000",
    ORANGE_SMS_SENDER_NAME="ImmoLib",
)
class OrangeSmsApiClientTests(TestCase):
    def test_unconfigured_client_raises(self):
        with override_settings(ORANGE_SMS_CLIENT_ID="", ORANGE_SMS_CLIENT_SECRET=""):
            with self.assertRaises(ImproperlyConfigured):
                OrangeSmsApiClient()

    def test_send_sms_requests_token_then_message(self):
        session = FakeSession(
            FakeResponse(200, TOKEN_PAYLOAD),
            FakeResponse(
                201,
                {
                    "outboundSMSMessageRequest": {
                        "resourceURL": "https://api.orange.com/smsmessaging/v1/outbound/tel%3A%2B2250000/requests/abc123"
                    }
                },
            ),
        )
        client = OrangeSmsApiClient(session=session)
        resource_id = client.send_sms(recipient="+2250700000001", message="Quittance de loyer")

        self.assertEqual(resource_id, "abc123")
        token_call, send_call = session.calls
        self.assertIn("oauth/v3/token", token_call["url"])
        self.assertEqual(
            token_call["headers"]["Authorization"], "Basic Y2xpZW50LWlkOmNsaWVudC1zZWNyZXQ="
        )
        self.assertIn("messaging/v1/outbound", send_call["url"])
        self.assertEqual(
            send_call["headers"]["Authorization"], "Bearer t0k3n"
        )
        self.assertEqual(
            send_call["json"]["outboundSMSMessageRequest"]["address"],
            "tel:+2250700000001",
        )

    def test_token_is_reused_across_sends(self):
        session = FakeSession(
            FakeResponse(200, TOKEN_PAYLOAD),
            FakeResponse(
                201,
                {
                    "outboundSMSMessageRequest": {
                        "resourceURL": "https://api.orange.com/smsmessaging/v1/outbound/tel%3A%2B2250000/requests/one"
                    }
                },
            ),
            FakeResponse(
                201,
                {
                    "outboundSMSMessageRequest": {
                        "resourceURL": "https://api.orange.com/smsmessaging/v1/outbound/tel%3A%2B2250000/requests/two"
                    }
                },
            ),
        )
        client = OrangeSmsApiClient(session=session)
        client.send_sms(recipient="+2250700000001", message="un")
        client.send_sms(recipient="+2250700000001", message="deux")

        self.assertEqual(
            sum("/oauth/v3/token" in c["url"] for c in session.calls),
            1,
        )

    def test_sender_name_is_dropped_when_not_configured(self):
        with override_settings(ORANGE_SMS_SENDER_NAME=""):
            session = FakeSession(
                FakeResponse(200, TOKEN_PAYLOAD),
                FakeResponse(
                    201,
                    {
                        "outboundSMSMessageRequest": {
                            "resourceURL": "https://api.orange.com/smsmessaging/v1/outbound/tel%3A%2B2250000/requests/abc"
                        }
                    },
                ),
            )
            client = OrangeSmsApiClient(session=session)
            client.send_sms(recipient="+2250700000001", message="un")
        send_call = session.calls[1]
        self.assertNotIn(
            "senderName", send_call["json"]["outboundSMSMessageRequest"]
        )
        self.assertIn(
            "clientCorrelator", send_call["json"]["outboundSMSMessageRequest"]
        )

    def test_retryable_error_is_transient(self):
        session = FakeSession(
            FakeResponse(200, TOKEN_PAYLOAD),
            FakeResponse(500, {}),
        )
        client = OrangeSmsApiClient(session=session)
        with self.assertRaises(OrangeProviderError):
            client.send_sms(recipient="+2250700000001", message="un")

    def test_bad_sender_name_is_permanent(self):
        session = FakeSession(
            FakeResponse(200, TOKEN_PAYLOAD),
            FakeResponse(
                400,
                {
                    "requestError": {
                        "serviceException": {
                            "messageId": "SVC0004",
                            "text": "Invalid sender name",
                        }
                    }
                },
            ),
        )
        client = OrangeSmsApiClient(session=session)
        with self.assertRaises(OrangeProviderPermanentError):
            client.send_sms(recipient="+2250700000001", message="un")

    def test_expired_token_refreshes_once(self):
        expired = {
            "requestError": {
                "serviceException": {
                    "messageId": "42",
                    "text": "The provided token expired",
                }
            }
        }
        session = FakeSession(
            FakeResponse(200, TOKEN_PAYLOAD),
            FakeResponse(401, expired),
            FakeResponse(200, TOKEN_PAYLOAD),
            FakeResponse(
                201,
                {
                    "outboundSMSMessageRequest": {
                        "resourceURL": "https://api.orange.com/smsmessaging/v1/outbound/tel%3A%2B2250000/requests/abc"
                    }
                },
            ),
        )
        client = OrangeSmsApiClient(session=session)
        resource_id = client.send_sms(recipient="+2250700000001", message="un")

        self.assertEqual(resource_id, "abc")
        self.assertEqual(
            sum("/oauth/v3/token" in c["url"] for c in session.calls),
            2,
        )

    def test_second_401_after_refresh_is_permanent(self):
        expired = {
            "requestError": {
                "serviceException": {"messageId": "42", "text": "expired token"}
            }
        }
        session = FakeSession(
            FakeResponse(200, TOKEN_PAYLOAD),
            FakeResponse(401, expired),
            FakeResponse(200, TOKEN_PAYLOAD),
            FakeResponse(401, expired),
        )
        client = OrangeSmsApiClient(session=session)
        with self.assertRaises(OrangeProviderPermanentError):
            client.send_sms(recipient="+2250700000001", message="un")
