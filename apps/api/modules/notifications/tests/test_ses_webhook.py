"""Tests du webhook SES (bounce/complaint) recu via SNS.

Le message SNS est signe (RSA) : on genere une vraie paire de cles + un
certificat auto-signe pour exercer le chemin de verification complet, le
telechargement du certificat AWS etant remplace par un mock.
"""

import base64
import json
from datetime import timedelta
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from modules.documents.models import NotificationDelivery
from modules.sms.tests.helpers import build_delivery

WEBHOOK_URL = reverse("ses-bounce-complaint-webhook")
TOPIC_ARN = "arn:aws:sns:af-south-1:123456789012:immolib-ses-bounces"
MAIL_MESSAGE_ID = "0100018e2f0b-5b1a4c3d-9e8f-4a1b-8c2d-3e4f5a6b7c8d@amazonses.com"

SIGNED_FIELDS = (
    "Message",
    "MessageId",
    "Subject",
    "Timestamp",
    "TopicArn",
    "Type",
    "UnsubscribeURL",
    "SubscribeURL",
    "Token",
)


def build_signer():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sns.immolib.test")])
    now = timezone.now()
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    return key, certificate


def canonical_string(message: dict) -> str:
    return "".join(
        f"{name}\n{message[name]}\n" for name in SIGNED_FIELDS if name in message
    )


def sign(message: dict, key) -> str:
    signature = key.sign(
        canonical_string(message).encode("utf-8"), padding.PKCS1v15(), hashes.SHA1()
    )
    return base64.b64encode(signature).decode("ascii")


def base_message(*, message_type: str = "Notification", **overrides) -> dict:
    message = {
        "Type": message_type,
        "MessageId": "sns-00000000-0000-0000-0000-000000000001",
        "TopicArn": TOPIC_ARN,
        "Timestamp": (
            timezone.now() - timedelta(seconds=30)
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "SignatureVersion": "1",
        "SigningCertURL": (
            "https://sns.af-south-1.amazonaws.com/SimpleNotificationService-test.pem"
        ),
    }
    message.update(overrides)
    return message


def sns_notification(*, key, ses_event, **overrides) -> dict:
    message = base_message(
        message_type="Notification", Message=json.dumps(ses_event), **overrides
    )
    message["Signature"] = sign(message, key)
    return message


def ses_bounce(
    *,
    bounce_type: str = "Permanent",
    subtype: str = "General",
    destination: str = "yao@example.com",
    message_id: str = MAIL_MESSAGE_ID,
) -> dict:
    return {
        "notificationType": "Bounce",
        "bounce": {
            "bounceType": bounce_type,
            "bounceSubType": subtype,
            "bouncedRecipients": [
                {
                    "emailAddress": destination,
                    "action": "failed",
                    "status": "5.1.1",
                    "diagnosticCode": "smtp; 550 5.1.1 user unknown",
                }
            ],
            "timestamp": "2026-08-14T10:00:00.000Z",
            "feedbackId": "0100018e-feedback-0001",
        },
        "mail": {
            "timestamp": "2026-08-14T09:59:00.000Z",
            "messageId": message_id,
            "source": "no-reply@immolib.ci",
            "destination": [destination],
        },
    }


def ses_complaint(
    *, destination: str = "yao@example.com", message_id: str = MAIL_MESSAGE_ID
) -> dict:
    return {
        "notificationType": "Complaint",
        "complaint": {
            "complainedRecipients": [{"emailAddress": destination}],
            "timestamp": "2026-08-14T10:00:00.000Z",
            "feedbackId": "0100018e-feedback-0002",
            "complaintFeedbackType": "abuse",
        },
        "mail": {
            "timestamp": "2026-08-14T09:59:00.000Z",
            "messageId": message_id,
            "source": "no-reply@immolib.ci",
            "destination": [destination],
        },
    }


@override_settings(AWS_SES_SNS_TOPIC_ARN=TOPIC_ARN)
class SesBounceComplaintWebhookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.key, cls.certificate = build_signer()
        cls.sms_delivery = build_delivery()
        cls.link = cls.sms_delivery.access_link

    def email_delivery(self) -> NotificationDelivery:
        """Une delivery EMAIL SENT correlee a MAIL_MESSAGE_ID, vierge a
        chaque test (la transaction du test precedent est annulee)."""
        return NotificationDelivery.objects.create(
            access_link=self.link,
            kind=NotificationDelivery.Kind.DOCUMENT_LINK,
            channel=NotificationDelivery.Channel.EMAIL,
            destination="yao@example.com",
            status=NotificationDelivery.Status.SENT,
            provider_reference=MAIL_MESSAGE_ID,
            subject="ImmoLib - Quittance",
            body="Consultez votre quittance.",
        )

    def post_payload(self, payload: dict):
        return self.client.post(
            WEBHOOK_URL, payload, content_type="application/json"
        )

    def test_webhook_503_when_topic_not_configured(self):
        with override_settings(AWS_SES_SNS_TOPIC_ARN=""):
            response = self.post_payload(base_message())

        self.assertEqual(response.status_code, 503)

    def test_webhook_400_for_invalid_json(self):
        response = self.client.post(
            WEBHOOK_URL, "{pas-du-json", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_webhook_400_for_unknown_sns_type(self):
        response = self.post_payload(
            sns_notification(
                key=self.key, ses_event=ses_bounce(), Type="Bogus"
            )
        )

        self.assertEqual(response.status_code, 400)

    def test_webhook_400_when_required_fields_missing(self):
        response = self.post_payload(
            sns_notification(key=self.key, ses_event=ses_bounce(), TopicArn="")
        )

        self.assertEqual(response.status_code, 400)

    def test_webhook_403_when_topic_arn_does_not_match(self):
        response = self.post_payload(
            sns_notification(
                key=self.key,
                ses_event=ses_bounce(),
                TopicArn="arn:aws:sns:af-south-1:123456789012:autre-topic",
            )
        )

        self.assertEqual(response.status_code, 403)

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_403_for_bad_signature(self, load_certificate):
        load_certificate.return_value = self.certificate
        other_key, _ = build_signer()
        payload = sns_notification(
            key=self.key, ses_event=ses_bounce()
        )
        payload["Signature"] = sign(payload, other_key)

        response = self.post_payload(payload)

        self.assertEqual(response.status_code, 403)

    def test_webhook_403_for_certificate_from_unexpected_host(self):
        payload = sns_notification(
            key=self.key,
            ses_event=ses_bounce(),
            SigningCertURL="https://evil.example.com/cert.pem",
        )

        response = self.post_payload(payload)

        self.assertEqual(response.status_code, 403)

    def test_webhook_400_for_stale_notification(self):
        stale = (
            timezone.now() - timedelta(seconds=600)
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        response = self.post_payload(
            sns_notification(key=self.key, ses_event=ses_bounce(), Timestamp=stale)
        )

        self.assertEqual(response.status_code, 400)

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_permanent_bounce_marks_delivery_failed(
        self, load_certificate
    ):
        load_certificate.return_value = self.certificate
        delivery = self.email_delivery()

        response = self.post_payload(
            sns_notification(key=self.key, ses_event=ses_bounce())
        )

        self.assertEqual(response.status_code, 200)
        received = response.json()["received"]
        self.assertEqual(received["notification_type"], "Bounce")
        self.assertEqual(received["bounce_type"], "Permanent")
        self.assertTrue(received["correlated"])
        self.assertEqual(received["destinations"], ["ya***@example.com"])
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)
        self.assertEqual(delivery.delivery_status, "FAILED")
        self.assertIsNone(delivery.next_attempt_at)
        self.assertIn("SES bounce permanent", delivery.failure_reason)

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_replayed_bounce_is_idempotent(self, load_certificate):
        load_certificate.return_value = self.certificate
        delivery = self.email_delivery()
        payload = sns_notification(key=self.key, ses_event=ses_bounce())

        first = self.post_payload(payload)
        second = self.post_payload(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(first.json()["received"]["correlated"])
        self.assertFalse(second.json()["received"]["correlated"])
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_transient_bounce_does_not_fail_delivery(
        self, load_certificate
    ):
        load_certificate.return_value = self.certificate
        delivery = self.email_delivery()

        response = self.post_payload(
            sns_notification(
                key=self.key,
                ses_event=ses_bounce(
                    bounce_type="Transient", subtype="MailboxFull"
                ),
            )
        )

        self.assertEqual(response.status_code, 200)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertFalse(response.json()["received"]["correlated"])

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_complaint_only_logs(self, load_certificate):
        load_certificate.return_value = self.certificate
        delivery = self.email_delivery()

        response = self.post_payload(
            sns_notification(key=self.key, ses_event=ses_complaint())
        )

        self.assertEqual(response.status_code, 200)
        received = response.json()["received"]
        self.assertEqual(received["notification_type"], "Complaint")
        self.assertFalse(received["handled"])
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_permanent_bounce_never_downgrades_delivered(
        self, load_certificate
    ):
        load_certificate.return_value = self.certificate
        delivery = self.email_delivery()
        delivery.delivery_status = "DELIVERED"
        delivery.delivered_at = timezone.now()
        delivery.save()

        response = self.post_payload(
            sns_notification(key=self.key, ses_event=ses_bounce())
        )

        self.assertEqual(response.status_code, 200)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.delivery_status, "DELIVERED")

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_bounce_without_reference_is_accepted(self, load_certificate):
        load_certificate.return_value = self.certificate

        response = self.post_payload(
            sns_notification(
                key=self.key,
                ses_event=ses_bounce(message_id=""),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["received"]["correlated"])

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_delivery_event_is_ignored(self, load_certificate):
        load_certificate.return_value = self.certificate

        response = self.post_payload(
            sns_notification(
                key=self.key,
                ses_event={
                    "notificationType": "Delivery",
                    "mail": {"messageId": MAIL_MESSAGE_ID},
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["received"]["handled"])

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    @patch("urllib.request.urlopen")
    def test_webhook_subscription_confirmation_auto_confirms(
        self, urlopen, load_certificate
    ):
        load_certificate.return_value = self.certificate
        urlopen.return_value.__enter__.return_value = type(
            "Response", (), {"status": 200}
        )()
        urlopen.return_value.__exit__.return_value = None
        payload = base_message(
            message_type="SubscriptionConfirmation",
            Token="sns-token-abc",
            SubscribeURL=(
                "https://sns.af-south-1.amazonaws.com/"
                "?Action=ConfirmSubscription&TopicArn=arn:aws:sns:af-south-1:"
                "123456789012:immolib-ses-bounces&Token=sns-token-abc"
            ),
        )
        payload["Signature"] = sign(payload, self.key)

        response = self.post_payload(payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["received"]["confirmed"])
        self.assertEqual(
            urlopen.call_args.args[0],
            "https://sns.af-south-1.amazonaws.com/"
            "?Action=ConfirmSubscription&TopicArn=arn:aws:sns:af-south-1:"
            "123456789012:immolib-ses-bounces&Token=sns-token-abc",
        )

    @patch("modules.notifications.api.ses_notifications._load_certificate")
    def test_webhook_subscription_confirmation_rejects_foreign_url(
        self, load_certificate
    ):
        load_certificate.return_value = self.certificate
        payload = base_message(
            message_type="SubscriptionConfirmation",
            Token="sns-token-abc",
            SubscribeURL="https://evil.example.com/confirm",
        )
        payload["Signature"] = sign(payload, self.key)

        with patch(
            "modules.notifications.api.ses_notifications.urllib.request.urlopen"
        ) as urlopen:
            response = self.post_payload(payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["received"]["confirmed"])
        urlopen.assert_not_called()