import uuid
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    """Choix de canaux d'un compte, séparés de ses coordonnées."""

    class PreferredChannel(models.TextChoices):
        AUTO = "AUTO", _("Automatique")
        PUSH = "PUSH", _("Notification push")
        EMAIL = "EMAIL", _("Email")
        WHATSAPP = "WHATSAPP", _("WhatsApp")
        SMS = "SMS", _("SMS")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    preferred_channel = models.CharField(
        max_length=12,
        choices=PreferredChannel.choices,
        default=PreferredChannel.AUTO,
    )
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=False)
    sms_enabled = models.BooleanField(default=False)
    whatsapp_opted_in_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__phone"]

    def __str__(self) -> str:
        return f"Préférences de {self.user}"


class PushSubscription(models.Model):
    """Jeton FCM d'un navigateur autorisé par son utilisateur."""

    class Platform(models.TextChoices):
        WEB = "WEB", _("Navigateur web")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    token = models.TextField(unique=True)
    platform = models.CharField(
        max_length=12, choices=Platform.choices, default=Platform.WEB
    )
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [
            models.Index(
                fields=["user", "is_active", "last_seen_at"],
                name="push_subscription_lookup_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.device_name or self.platform}"
