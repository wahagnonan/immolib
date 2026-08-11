from datetime import datetime, timezone

from django.test import TestCase, override_settings

from modules.whatsapp.models import WhatsAppInboundMessage, WhatsAppMessageStatus

WEBHOOK_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "102290129340398",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550783881",
                            "phone_number_id": "106540352242922",
                        },
                        "contacts": [
                            {
                                "profile": {"name": "Sheena Nelson"},
                                "wa_id": "16505551234",
                            }
                        ],
                        "messages": [
                            {
                                "from": "16505551234",
                                "id": "wamid.HBgLMTY1MDM4Nzk0MzkVAgASGBQzQTRBNjU5OUFFRTAzODEwMTQ0RgA=",
                                "timestamp": "1749416383",
                                "type": "text",
                                "text": {"body": "Does it come in another color?"},
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


@override_settings(WHATSAPP_WEBHOOK_VERIFY_TOKEN="demo-verify-token")
class WhatsAppWebhookViewTests(TestCase):
    def test_handshake_success_returns_raw_challenge(self):
        response = self.client.get(
            "/api/v1/webhooks/whatsapp/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "demo-verify-token",
                "hub.challenge": "1158201444",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "1158201444")
        self.assertIn("text/plain", response["Content-Type"])

    def test_handshake_wrong_token_is_forbidden(self):
        response = self.client.get(
            "/api/v1/webhooks/whatsapp/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "1158201444",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_handshake_wrong_mode_is_forbidden(self):
        response = self.client.get(
            "/api/v1/webhooks/whatsapp/",
            {
                "hub.mode": "unsubscribe",
                "hub.verify_token": "demo-verify-token",
                "hub.challenge": "1158201444",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_handshake_without_configured_token_is_forbidden(self):
        with override_settings(WHATSAPP_WEBHOOK_VERIFY_TOKEN=""):
            response = self.client.get(
                "/api/v1/webhooks/whatsapp/",
                {
                    "hub.mode": "subscribe",
                    "hub.verify_token": "demo-verify-token",
                    "hub.challenge": "1158201444",
                },
            )
        self.assertEqual(response.status_code, 403)

    def test_post_records_inbound_message(self):
        response = self.client.post(
            "/api/v1/webhooks/whatsapp/",
            data=WEBHOOK_PAYLOAD,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["received"], {"messages": 1, "statuses": 0})

        message = WhatsAppInboundMessage.objects.get()
        self.assertEqual(message.wa_id, "16505551234")
        self.assertEqual(message.profile_name, "Sheena Nelson")
        self.assertEqual(message.message_type, "text")
        self.assertEqual(message.body, "Does it come in another color?")
        self.assertEqual(message.sent_at, datetime(2025, 6, 8, 20, 59, 43, tzinfo=timezone.utc))

    def test_post_duplicate_message_is_idempotent(self):
        for _ in range(2):
            response = self.client.post(
                "/api/v1/webhooks/whatsapp/",
                data=WEBHOOK_PAYLOAD,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(WhatsAppInboundMessage.objects.count(), 1)

    def test_post_records_delivery_statuses(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "102290129340398",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550783881",
                                    "phone_number_id": "106540352242922",
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.OUTBOUND1",
                                        "status": "delivered",
                                        "timestamp": "1749416383",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        response = self.client.post(
            "/api/v1/webhooks/whatsapp/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        status_update = WhatsAppMessageStatus.objects.get()
        self.assertEqual(status_update.message_id, "wamid.OUTBOUND1")
        self.assertEqual(status_update.status, "delivered")

    def test_post_unknown_object_is_rejected(self):
        response = self.client.post(
            "/api/v1/webhooks/whatsapp/",
            data={"object": "some_other_object", "entry": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_document_message_extracts_caption_and_media_id(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "102290129340398",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550783881",
                                    "phone_number_id": "106540352242922",
                                },
                                "contacts": [
                                    {"profile": {"name": "Locataire"}, "wa_id": "16505551234"}
                                ],
                                "messages": [
                                    {
                                        "from": "16505551234",
                                        "id": "wamid.DOC1",
                                        "timestamp": "1749416383",
                                        "type": "document",
                                        "document": {
                                            "id": "MEDIA-42",
                                            "caption": "Ma quittance",
                                        },
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        self.client.post(
            "/api/v1/webhooks/whatsapp/",
            data=payload,
            content_type="application/json",
        )
        message = WhatsAppInboundMessage.objects.get()
        self.assertEqual(message.message_type, "document")
        self.assertEqual(message.body, "Ma quittance")
        self.assertEqual(message.media_id, "MEDIA-42")
