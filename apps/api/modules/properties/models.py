import builtins
import uuid
from datetime import timedelta
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from modules.accounts.phones import validate_e164


def default_invitation_expiry():
    return timezone.now() + timedelta(days=30)


class Property(models.Model):
    """Bien locatif : maison, appartement, terrain ou local commercial."""

    class Type(models.TextChoices):
        HOUSE = "HOUSE", _("Maison")
        APARTMENT = "APARTMENT", _("Appartement")
        LAND = "LAND", _("Terrain")
        COMMERCIAL = "COMMERCIAL", _("Local commercial")

    class Status(models.TextChoices):
        VACANT = "VACANT", _("Vacante")
        OCCUPIED = "OCCUPIED", _("Occupee")
        UNAVAILABLE = "UNAVAILABLE", _("Indisponible")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property_type = models.CharField(
        "type de bien",
        max_length=20,
        choices=Type.choices,
        default=Type.HOUSE,
    )
    name = models.CharField("nom", max_length=120)
    address = models.CharField("adresse", max_length=255)
    commune = models.CharField("commune", max_length=120, blank=True)
    city = models.CharField("ville", max_length=120)
    landmark = models.CharField("repere", max_length=255, blank=True)
    status = models.CharField(
        "statut", max_length=20, choices=Status.choices, default=Status.VACANT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    owners = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Ownership",
        related_name="owned_properties",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("bien")
        verbose_name_plural = _("biens")

    def __str__(self) -> str:
        return self.name


class Ownership(models.Model):
    """Separe ce qu'une personne possede de ce qu'elle peut faire."""

    class Role(models.TextChoices):
        PRIMARY = "PRIMARY", _("Proprietaire principal")
        CO_OWNER = "CO_OWNER", _("Coproprietaire")

    class AccessLevel(models.TextChoices):
        ACTIVE = "ACTIVE", _("Actif")
        OBSERVER = "OBSERVER", _("Observateur")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="ownerships",
        verbose_name="bien",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ownerships",
        verbose_name="utilisateur",
    )
    role = models.CharField("role", max_length=20, choices=Role.choices)
    access_level = models.CharField(
        "niveau d'acces",
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.OBSERVER,
    )
    ownership_percentage = models.DecimalField(
        "quote-part",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["property", "role", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "user"],
                name="one_ownership_per_user_and_property",
            ),
            models.UniqueConstraint(
                fields=["property"],
                condition=Q(role="PRIMARY"),
                name="one_primary_owner_per_property",
            ),
        ]
        verbose_name = _("propriete")
        verbose_name_plural = _("proprietes")

    def __str__(self) -> str:
        return f"{self.user} - {self.property} ({self.get_role_display()})"


class CoOwnerInvitation(models.Model):
    """Invitation traçable avant qu'un copropriétaire possède un compte."""

    class Status(models.TextChoices):
        PENDING = "PENDING", _("En attente")
        ACCEPTED = "ACCEPTED", _("Acceptée")
        REVOKED = "REVOKED", _("Révoquée")
        EXPIRED = "EXPIRED", _("Expirée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="co_owner_invitations",
        verbose_name="bien",
    )
    phone = models.CharField(
        "téléphone",
        max_length=20,
        validators=[validate_e164],
    )
    email = models.EmailField("email", blank=True)
    ownership_percentage = models.DecimalField(
        "quote-part proposée",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("99.99")),
        ],
    )
    access_level = models.CharField(
        "niveau d'accès proposé",
        max_length=20,
        choices=Ownership.AccessLevel.choices,
        default=Ownership.AccessLevel.OBSERVER,
    )
    status = models.CharField(
        "statut",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_co_owner_invitations",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="accepted_co_owner_invitations",
        null=True,
        blank=True,
    )
    expires_at = models.DateTimeField(default=default_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "phone"],
                condition=Q(status="PENDING"),
                name="one_pending_coowner_invitation_per_phone_and_property",
            )
        ]
        verbose_name = _("invitation de copropriétaire")
        verbose_name_plural = _("invitations de copropriétaires")

    @builtins.property
    def is_expired(self) -> bool:
        return self.status == self.Status.EXPIRED or (
            self.status == self.Status.PENDING and self.expires_at <= timezone.now()
        )

    def __str__(self) -> str:
        return f"{self.phone} - {self.property} ({self.get_status_display()})"
