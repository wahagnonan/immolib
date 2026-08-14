import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class SmsSendRecord(models.Model):
    """Trace d'un SMS reellement accepte par Orange.

    Cree par l'adaptateur a la reussite de l'envoi. ``provider_message_id``
    (le resource_id Orange) est unique : il garantit l'idempotence de
    l'enregistrement. Un retraitement du worker peut re-envoyer un SMS (file
    au moins une fois) : chaque envoi a sa propre trace, la plus recente
    prevaut pour le ``segments_count`` de la notification.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(
        "documents.NotificationDelivery",
        on_delete=models.PROTECT,
        related_name="sms_send_records",
        null=True,
        blank=True,
        verbose_name="message en file",
    )
    provider_message_id = models.CharField(
        "identifiant Orange", max_length=160, unique=True
    )
    recipient = models.CharField("destinataire", max_length=20)
    segments_count = models.PositiveSmallIntegerField("segments", default=1)
    estimated_cost_xof = models.DecimalField(
        "cout estime (FCFA)",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(
                fields=["sent_at", "segments_count"],
                name="sms_send_record_stats_idx",
            )
        ]
        verbose_name = _("SMS envoye")
        verbose_name_plural = _("SMS envoyes")

    def __str__(self) -> str:
        return f"{self.provider_message_id} ({self.segments_count} segment(s))"


class SmsDeliveryReceipt(models.Model):
    """Accuse de reception Orange (Delivery Receipt), idempotent.

    Orange ne signe pas ses webhooks : la validation repose sur la structure
    du payload, la liste blanche d'IP et la contrainte d'unicite
    (provider_message_id, delivery_status) qui absorbe les repetitions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_message_id = models.CharField(
        "identifiant Orange", max_length=160, db_index=True
    )
    delivery_status = models.CharField("statut Orange", max_length=32)
    address = models.CharField("destinataire", max_length=20, blank=True)
    raw_payload = models.JSONField("payload brut", default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("provider_message_id", "delivery_status"),
                name="one_sms_dr_per_message_status",
            )
        ]
        verbose_name = _("accuse de reception SMS")
        verbose_name_plural = _("accuses de reception SMS")

    def __str__(self) -> str:
        return f"{self.provider_message_id} - {self.delivery_status}"
