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


# Le payload chiffre d'une notification web ne doit pas depasser 4096 octets.
_WEB_PUSH_PAYLOAD_LIMIT = 3800
# La notification reste en file 7 jours chez le fournisseur si l'appareil est
# hors ligne (ttl=0 ferait tomber le message immediatement).
_WEB_PUSH_TTL_SECONDS = 604800


class WebPushVapidAdapter:
    """Envoie des notifications via le protocole Web Push standard (clés VAPID).

    Aucun fournisseur externe : le navigateur s'abonne au service de push de son
    fabricant (FCM, Mozilla Autopush, WNS) et ImmoLib signe ses requêtes avec sa
    paire de clés VAPID. La destination est l'abonnement JSON complet du navigateur.
    """

    def __init__(self, *, private_key=None, claims=None):
        try:
            from pywebpush import WebPushException, webpush
        except ImportError as exc:
            raise ImproperlyConfigured(
                "Installez pywebpush pour utiliser les notifications push."
            ) from exc
        self._webpush = webpush
        self._WebPushException = WebPushException
        self._private_key = private_key or settings.VAPID_PRIVATE_KEY
        if not self._private_key:
            raise ImproperlyConfigured(
                "VAPID_PRIVATE_KEY doit être configuré pour le Web Push."
            )
        self._claims = claims or {"sub": settings.VAPID_SUBJECT or settings.PUBLIC_APP_URL}

    def send(self, message: NotificationMessage) -> DeliveryReceipt:
        try:
            subscription_info = json.loads(message.destination)
        except (TypeError, ValueError) as exc:
            raise PermanentNotificationError(
                "L'abonnement push est illisible."
            ) from exc

        url = message.metadata.get("url", "/")
        payload = json.dumps(
            {"title": message.subject, "body": message.body, "url": url},
            ensure_ascii=False,
        ).encode("utf-8")
        if len(payload) > _WEB_PUSH_PAYLOAD_LIMIT:
            body = message.body[: _WEB_PUSH_PAYLOAD_LIMIT - 128] + "…"
            payload = json.dumps(
                {"title": message.subject, "body": body, "url": url},
                ensure_ascii=False,
            ).encode("utf-8")

        try:
            response = self._webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self._private_key,
                vapid_claims=self._claims,
                ttl=_WEB_PUSH_TTL_SECONDS,
            )
        except self._WebPushException as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                raise PermanentNotificationError(
                    "L'abonnement push a expiré."
                ) from exc
            raise
        reference = ""
        if response is not None and hasattr(response, "headers"):
            reference = response.headers.get("Location", "")
        return DeliveryReceipt(provider_reference=reference)
