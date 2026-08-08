import uuid
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from modules.properties.models import Property
from modules.accounts.phones import validate_e164


class Tenant(models.Model):
    """Identite du locataire telle qu'elle est connue pour une maison."""

    class Status(models.TextChoices):
        UNREGISTERED = "UNREGISTERED", _("Sans compte ImmoLib")
        INVITED = "INVITED", _("Invite")
        ACTIVE = "ACTIVE", _("Compte active")
        BLOCKED = "BLOCKED", _("Bloque")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="tenants",
        verbose_name="maison",
    )
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_profiles",
        verbose_name="compte ImmoLib",
    )
    full_name = models.CharField("nom complet", max_length=160)
    phone = models.CharField(
        "telephone",
        max_length=20,
        validators=[validate_e164],
    )
    email = models.EmailField("email", blank=True)
    status = models.CharField(
        "statut",
        max_length=20,
        choices=Status.choices,
        default=Status.UNREGISTERED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tenants",
        verbose_name="cree par",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "phone"],
                name="one_tenant_phone_per_property",
            )
        ]
        verbose_name = _("locataire")
        verbose_name_plural = _("locataires")

    def __str__(self) -> str:
        return f"{self.full_name} - {self.property}"


class TenantInvitation(models.Model):
    """Invitation signée permettant au locataire de réclamer sa fiche."""

    class Status(models.TextChoices):
        PENDING = "PENDING", _("En attente")
        ACCEPTED = "ACCEPTED", _("Acceptée")
        REVOKED = "REVOKED", _("Révoquée")
        EXPIRED = "EXPIRED", _("Expirée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="invitations",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_tenant_invitations",
    )
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="claimed_tenant_invitations",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="accepted_tenant_invitations",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    expires_at = models.DateTimeField()
    claimed_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant"],
                condition=Q(status="PENDING"),
                name="one_pending_invitation_per_tenant",
            )
        ]
        indexes = [
            models.Index(
                fields=["status", "expires_at"],
                name="tenant_invitation_status_idx",
            )
        ]

    @property
    def is_expired(self) -> bool:
        return self.status == self.Status.PENDING and self.expires_at <= timezone.now()

    def __str__(self) -> str:
        return f"{self.tenant.full_name} - {self.get_status_display()}"


class TenantInvitationShareEvent(models.Model):
    """Trace un partage préparé sur l'appareil du bailleur."""

    class Channel(models.TextChoices):
        WHATSAPP = "WHATSAPP", _("WhatsApp")
        EMAIL = "EMAIL", _("Email")
        SMS = "SMS", _("SMS")
        NATIVE = "NATIVE", _("Partage de l'appareil")
        COPY = "COPY", _("Copie du message")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.ForeignKey(
        TenantInvitation,
        on_delete=models.PROTECT,
        related_name="share_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tenant_invitation_share_events",
    )
    channel = models.CharField(max_length=12, choices=Channel.choices)
    destination = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.invitation} - {self.get_channel_display()}"


class Lease(models.Model):
    """Conditions de location d'une maison pour une periode donnee."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Brouillon")
        ACTIVE = "ACTIVE", _("Actif")
        ENDED = "ENDED", _("Termine")
        CANCELLED = "CANCELLED", _("Annule")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="leases",
        verbose_name="maison",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="leases",
        verbose_name="locataire",
    )
    status = models.CharField(
        "statut", max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    start_date = models.DateField("date de debut")
    end_date = models.DateField("date de fin", null=True, blank=True)
    monthly_rent = models.DecimalField(
        "loyer mensuel",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    monthly_charges = models.DecimalField(
        "charges mensuelles",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    due_day = models.PositiveSmallIntegerField(
        "jour limite de paiement",
        validators=[MinValueValidator(1), MaxValueValidator(28)],
    )
    security_deposit = models.DecimalField(
        "caution",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    rent_advance = models.DecimalField(
        "avance sur loyer",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField("devise", max_length=3, default="XOF")
    accepts_mobile_money = models.BooleanField(default=True)
    accepts_cash = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_leases",
        verbose_name="cree par",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["property"],
                condition=Q(status="ACTIVE"),
                name="one_active_lease_per_property",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="lease_end_on_or_after_start",
            ),
            models.CheckConstraint(
                condition=Q(monthly_rent__gt=0),
                name="lease_monthly_rent_positive",
            ),
            models.CheckConstraint(
                condition=Q(monthly_charges__gte=0),
                name="lease_monthly_charges_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(security_deposit__gte=0),
                name="lease_security_deposit_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(rent_advance__gte=0),
                name="lease_rent_advance_non_negative",
            ),
        ]
        verbose_name = _("bail")
        verbose_name_plural = _("baux")

    def clean(self) -> None:
        super().clean()
        if self.tenant_id and self.property_id:
            if self.tenant.property_id != self.property_id:
                raise ValidationError(
                    {"tenant": "Le locataire doit appartenir a la meme maison."}
                )

    def __str__(self) -> str:
        return f"{self.property} - {self.tenant.full_name}"
