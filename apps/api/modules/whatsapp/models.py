from django.db import models
from django.utils.translation import gettext_lazy as _


class WhatsAppInboundMessage(models.Model):
    """Message reçu d'un utilisateur WhatsApp via le webhook."""

    class MessageType(models.TextChoices):
        TEXT = "text", _("Texte")
        IMAGE = "image", _("Image")
        VIDEO = "video", _("Vidéo")
        AUDIO = "audio", _("Audio")
        DOCUMENT = "document", _("Document")
        STICKER = "sticker", _("Sticker")
        LOCATION = "location", _("Localisation")
        CONTACTS = "contacts", _("Contacts")
        BUTTON = "button", _("Bouton")
        INTERACTIVE = "interactive", _("Interactif")
        UNKNOWN = "unknown", _("Inconnu")

    message_id = models.CharField(max_length=255, unique=True)
    wa_id = models.CharField(_("numéro de l'expéditeur"), max_length=32, db_index=True)
    profile_name = models.CharField(max_length=255, blank=True)
    message_type = models.CharField(
        max_length=20, choices=MessageType.choices, default=MessageType.UNKNOWN
    )
    body = models.TextField(blank=True)
    media_id = models.CharField(max_length=255, blank=True)
    from_me = models.BooleanField(default=False)
    sent_at = models.DateTimeField()
    raw_payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-sent_at",)
        verbose_name = _("message WhatsApp entrant")
        verbose_name_plural = _("messages WhatsApp entrants")

    def __str__(self):
        return f"{self.wa_id} - {self.get_message_type_display()}"


class WhatsAppMessageStatus(models.Model):
    """Statut de livraison d'un message envoyé par ImmoLib."""

    class Status(models.TextChoices):
        SENT = "sent", _("Envoyé")
        DELIVERED = "delivered", _("Délivré")
        READ = "read", _("Lu")
        FAILED = "failed", _("Échec")

    message_id = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    status_timestamp = models.CharField(max_length=32, blank=True)
    errors = models.JSONField(default=list, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("message_id", "status"), name="one_whatsapp_status_per_message"
            )
        ]
        verbose_name = _("statut WhatsApp")
        verbose_name_plural = _("statuts WhatsApp")

    def __str__(self):
        return f"{self.message_id} - {self.get_status_display()}"
