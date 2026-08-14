import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.accounts.models import User


class SubscriptionPlan(models.Model):
    """Offre d'abonnement (Gratuit, Essentiel, Pro)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=255, blank=True, default="")
    price_monthly = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="XOF")
    max_houses = models.PositiveSmallIntegerField(default=1)
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_monthly"]

    def __str__(self) -> str:
        return f"{self.name} ({self.currency} {self.price_monthly}/mois)"


class Subscription(models.Model):
    """Abonnement actif d'un utilisateur.

    Les statuts sont extensibles (trial, paused, past_due) sans toucher à la
    logique : seul ACTIVE débloque le plan attaché.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", _("Actif")
        PENDING = "PENDING", _("En attente")
        EXPIRED = "EXPIRED", _("Expiré")
        CANCELLED = "CANCELLED", _("Annulé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    started_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="sub_status_expiry_idx"),
            models.Index(fields=["user", "status"], name="sub_user_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user.phone} - {self.plan.slug} - {self.status}"


class SubscriptionTransaction(models.Model):
    """Paiement d'un abonnement, tracé pour l'intégration PayDunya."""

    class Status(models.TextChoices):
        PENDING = "PENDING", _("En attente")
        SUCCESSFUL = "SUCCESSFUL", _("Réussi")
        FAILED = "FAILED", _("Échoué")
        CANCELLED = "CANCELLED", _("Annulé")
        EXPIRED = "EXPIRED", _("Expiré")

    class Provider(models.TextChoices):
        MANUAL = "MANUAL", _("Activation manuelle (pilote)")
        PAYDUNYA = "PAYDUNYA", "PayDunya"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="subscription_transactions",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default=settings.SUBSCRIPTION_CURRENCY)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    provider = models.CharField(
        max_length=16, choices=Provider.choices, default=Provider.PAYDUNYA
    )
    provider_reference = models.CharField(
        max_length=120, blank=True, default=""
    )
    provider_hash = models.CharField(max_length=255, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["provider_reference"], name="sub_txn_provider_ref_idx"
            ),
            models.Index(fields=["user", "status"], name="sub_txn_user_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user.phone} - {self.plan.slug} - {self.status}"
