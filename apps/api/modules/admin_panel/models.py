import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """Journal append-only des actions sensibles realisees par les admins.

    Ne contient jamais de mots de passe, tokens ou secrets : seuls les
    metadonnees utiles au support sont enregistrees.
    """

    class Action(models.TextChoices):
        ADMIN_LOGIN = "ADMIN_LOGIN", _("Connexion admin")
        USER_SUSPENDED = "USER_SUSPENDED", _("Utilisateur suspendu")
        USER_REACTIVATED = "USER_REACTIVATED", _("Utilisateur reactive")
        USER_ROLE_CHANGED = "USER_ROLE_CHANGED", _("Role utilisateur modifie")
        SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED", _("Abonnement modifie")
        SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED", _("Abonnement annule")
        SUBSCRIPTION_EXTENDED = "SUBSCRIPTION_EXTENDED", _("Abonnement prolonge")
        SUBSCRIPTION_ACTIVATED = "SUBSCRIPTION_ACTIVATED", _("Abonnement active")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("administrateur"),
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["admin", "created_at"], name="audit_admin_date_idx"),
            models.Index(fields=["action", "created_at"], name="audit_action_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} - {self.created_at.isoformat()}"
