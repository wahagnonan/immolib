from html import escape
import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from modules.documents.notifications import (
    DeliveryReceipt,
    NotificationMessage,
    PermanentNotificationError,
)


class AmazonSesEmailAdapter:
    """Envoie les emails avec l'API Amazon SES compatible boto3."""

    def __init__(self, *, client=None, source: str | None = None):
        self.source = source if source is not None else settings.AWS_SES_FROM_EMAIL
        if not self.source:
            raise ImproperlyConfigured(_("AWS_SES_FROM_EMAIL doit être configuré."))
        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise ImproperlyConfigured(
                    _("Installez boto3 pour utiliser Amazon SES.")
                ) from exc
            client = boto3.client("ses", region_name=settings.AWS_SES_REGION)
        self.client = client

    def send(self, message: NotificationMessage) -> DeliveryReceipt:
        escaped_body = escape(message.body).replace("\n", "<br>")
        response = self.client.send_email(
            Source=self.source,
            Destination={"ToAddresses": [message.destination]},
            Message={
                "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": message.body, "Charset": "UTF-8"},
                    "Html": {
                        "Data": (
                            "<div style=\"font-family:Arial,sans-serif;"
                            "line-height:1.6;color:#17201d\">"
                            f"{escaped_body}</div>"
                        ),
                        "Charset": "UTF-8",
                    },
                },
            },
        )
        return DeliveryReceipt(provider_reference=response.get("MessageId", ""))


class FirebasePushAdapter:
    """Envoie un push FCM à un jeton navigateur sans exposer de secret au web."""

    def __init__(self, *, sender=None):
        self.sender = sender or self._build_sender()

    @staticmethod
    def _build_sender():
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
        except ImportError as exc:
            raise ImproperlyConfigured(
                "Installez firebase-admin pour utiliser les notifications push."
            ) from exc

        try:
            firebase_admin.get_app()
        except ValueError:
            options = (
                {"projectId": settings.FIREBASE_PROJECT_ID}
                if settings.FIREBASE_PROJECT_ID
                else None
            )
            if settings.FIREBASE_CREDENTIALS_FILE:
                firebase_admin.initialize_app(
                    credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE),
                    options=options,
                )
            else:
                firebase_admin.initialize_app(options=options)

        def send(message: NotificationMessage) -> str:
            data = {key: str(value) for key, value in message.metadata.items()}
            data.setdefault("url", "/")
            return messaging.send(
                messaging.Message(
                    token=message.destination,
                    notification=messaging.Notification(
                        title=message.subject,
                        body=message.body,
                    ),
                    data=data,
                )
            )

        return send

    def send(self, message: NotificationMessage) -> DeliveryReceipt:
        return DeliveryReceipt(provider_reference=self.sender(message))


class WhatsAppCloudApiAdapter:
    """Envoie les messages ImmoLib (quittances, rappels, invitations) via
    l'API WhatsApp Cloud. La destination est le numéro E.164 du locataire.
    """

    def __init__(self, *, client=None):
        from modules.whatsapp.provider import (
            WhatsAppCloudApiClient,
            WhatsAppProviderPermanentError,
        )

        self._permanent_error = WhatsAppProviderPermanentError
        self.client = client or WhatsAppCloudApiClient()

    def send(self, message: NotificationMessage) -> DeliveryReceipt:
        try:
            response = self.client.send_text_message(
                to=message.destination, body=message.body
            )
        except self._permanent_error as exc:
            raise PermanentNotificationError(str(exc)) from exc
        message_id = ""
        messages = response.get("messages")
        if messages:
            message_id = messages[0].get("id", "")
        return DeliveryReceipt(provider_reference=message_id)
