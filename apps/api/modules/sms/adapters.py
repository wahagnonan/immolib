"""Adaptateur Orange pour le canal SMS de la file de notifications.

L'adaptateur transforme une ``NotificationMessage`` de la file en appel
Orange, normalise le numero ivoirien, compte les segments (cout), enregistre
la trace d'envoi et renvoie le ``DeliveryReceipt`` attendu par le processeur.
Il ne contient aucune regle metier ImmoLib.
"""

import logging
import time
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from modules.documents.models import NotificationDelivery
from modules.documents.notifications import (
    DeliveryReceipt,
    NotificationMessage,
    PermanentNotificationError,
)

from .models import SmsSendRecord
from .phones import InvalidPhoneNumber, normalize_ci_phone
from .provider import (
    OrangeProviderError,
    OrangeProviderPermanentError,
    OrangeSmsApiClient,
)
from .segments import count_segments

logger = logging.getLogger(__name__)


class OrangeSmsAdapter:
    """Envoie les SMS de la file via l'API Orange SMS Cote d'Ivoire."""

    def __init__(
        self,
        *,
        client=None,
        max_chars: int | None = None,
        rate_per_second: int | None = None,
        _now=None,
        _sleep=None,
    ):
        if client is None:
            client = OrangeSmsApiClient()
        self.client = client
        self.max_chars = (
            max_chars if max_chars is not None else settings.IMMOLIB_SMS_MAX_CHARS
        )
        if self.max_chars < 1:
            raise ImproperlyConfigured("IMMOLIB_SMS_MAX_CHARS doit etre positif.")
        self.rate_per_second = (
            rate_per_second
            if rate_per_second is not None
            else settings.IMMOLIB_SMS_RATE_PER_SECOND
        )
        self._now = _now or time.monotonic
        self._sleep = _sleep or time.sleep
        self._last_send_at = 0.0

    def _pace(self) -> None:
        """Espace les envois pour respecter la limite Orange de 5 SMS/s."""
        if self.rate_per_second < 1:
            return
        interval = 1.0 / self.rate_per_second
        elapsed = self._now() - self._last_send_at
        if elapsed < interval:
            self._sleep(interval - elapsed)
        self._last_send_at = self._now()

    @staticmethod
    def _recipient_for(message: NotificationMessage) -> str:
        try:
            return normalize_ci_phone(message.destination)
        except InvalidPhoneNumber as exc:
            raise PermanentNotificationError(str(exc)) from exc

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        """Coupe sur un mot quand c'est possible et ajoute une ellipse."""
        if limit <= 0:
            return ""
        cut = text[:limit]
        space = cut.rfind(" ")
        if space >= len(cut) // 2:
            cut = cut[:space]
        return cut.rstrip() + "…"

    def _message_text(self, message: NotificationMessage) -> str:
        text = message.body or message.subject
        if len(text) <= self.max_chars:
            return text
        logger.warning(
            "sms.send.long_message chars=%s threshold=%s", len(text), self.max_chars
        )
        link = message.metadata.get("url", "").strip()
        if link and len(link) < self.max_chars:
            head = self._truncate(text, self.max_chars - len(link) - 2)
            return f"{head} {link}"
        return self._truncate(text, self.max_chars - 1)

    def _record_send(
        self, *, delivery_id: str, resource_id: str, recipient: str, text: str
    ) -> None:
        segments = count_segments(text)
        cost = Decimal(segments) * Decimal(settings.ORANGE_SMS_COST_PER_SEGMENT_XOF)
        _, created = SmsSendRecord.objects.get_or_create(
            provider_message_id=resource_id,
            defaults={
                "delivery_id": delivery_id or None,
                "recipient": recipient,
                "segments_count": segments,
                "estimated_cost_xof": cost,
            },
        )
        if created and delivery_id:
            NotificationDelivery.objects.filter(id=delivery_id).update(
                segments_count=segments
            )
            logger.info("sms.record.created segments=%s", segments)

    def send(self, message: NotificationMessage) -> DeliveryReceipt:
        """Envoie le SMS et retourne un recu portant le correlator client.

        Le correlator (l'identifiant du delivery) est renvoye par Orange dans
        le callbackData du Delivery Receipt : le processeur le stocke dans
        ``provider_reference``, ce qui permet de correler la remise.
        """
        recipient = self._recipient_for(message)
        text = self._message_text(message)
        correlator = message.delivery_id or str(uuid.uuid4())
        self._pace()
        try:
            resource_id = self.client.send_sms(
                recipient=recipient,
                message=text,
                client_correlator=correlator,
            )
        except OrangeProviderPermanentError as exc:
            raise PermanentNotificationError(str(exc)) from exc
        self._record_send(
            delivery_id=message.delivery_id,
            resource_id=resource_id,
            recipient=recipient,
            text=text,
        )
        return DeliveryReceipt(provider_reference=correlator)
