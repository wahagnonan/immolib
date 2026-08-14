import uuid
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from modules.leases.models import Lease, Tenant
from modules.properties.models import Property


class MaintenanceIncident(models.Model):
    """Incident signalé pour une location et suivi jusqu'à sa clôture."""

    class Category(models.TextChoices):
        PLUMBING = "PLUMBING", _("Plomberie")
        ELECTRICITY = "ELECTRICITY", _("Électricité")
        SECURITY = "SECURITY", _("Sécurité")
        ROOF = "ROOF", _("Toiture")
        STRUCTURE = "STRUCTURE", _("Structure")
        EQUIPMENT = "EQUIPMENT", _("Équipement")
        OTHER = "OTHER", _("Autre")

    class Priority(models.TextChoices):
        LOW = "LOW", _("Faible")
        NORMAL = "NORMAL", _("Normale")
        HIGH = "HIGH", _("Élevée")
        URGENT = "URGENT", _("Urgente")

    class Status(models.TextChoices):
        REPORTED = "REPORTED", _("Signalé")
        ACKNOWLEDGED = "ACKNOWLEDGED", _("Pris en compte")
        IN_PROGRESS = "IN_PROGRESS", _("Intervention en cours")
        RESOLVED = "RESOLVED", _("Résolu par le bailleur")
        CLOSED = "CLOSED", _("Clôturé par le locataire")
        CANCELLED = "CANCELLED", _("Annulé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="maintenance_incidents",
        verbose_name="bien",
    )
    lease = models.ForeignKey(
        Lease,
        on_delete=models.PROTECT,
        related_name="maintenance_incidents",
        verbose_name="bail",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="maintenance_incidents",
        verbose_name="locataire",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_maintenance_incidents",
    )
    title = models.CharField("titre", max_length=160)
    description = models.TextField("description")
    category = models.CharField(
        "catégorie",
        max_length=20,
        choices=Category.choices,
    )
    priority = models.CharField(
        "priorité",
        max_length=12,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        "statut",
        max_length=20,
        choices=Status.choices,
        default=Status.REPORTED,
    )
    occurred_at = models.DateTimeField("constaté le", null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["property", "status", "priority"],
                name="maint_property_status_idx",
            ),
            models.Index(
                fields=["tenant", "created_at"],
                name="maintenance_tenant_date_idx",
            ),
        ]
        verbose_name = _("incident de maintenance")
        verbose_name_plural = _("incidents de maintenance")

    def clean(self) -> None:
        super().clean()
        if self.lease_id and self.property_id:
            if self.lease.property_id != self.property_id:
                raise ValidationError(
                    {"property": "Le bien doit correspondre au bail."}
                )
        if self.lease_id and self.tenant_id:
            if self.lease.tenant_id != self.tenant_id:
                raise ValidationError(
                    {"tenant": "Le locataire doit correspondre au bail."}
                )

    def __str__(self) -> str:
        return f"{self.title} - {self.property.name}"


class MaintenanceEvent(models.Model):
    """Journal append-only des échanges et transitions d'un incident."""

    class Type(models.TextChoices):
        REPORTED = "REPORTED", _("Incident signalé")
        STATUS_CHANGED = "STATUS_CHANGED", _("Statut modifié")
        COMMENTED = "COMMENTED", _("Commentaire ajouté")

    class ActorRole(models.TextChoices):
        OWNER = "OWNER", _("Bailleur")
        TENANT = "TENANT", _("Locataire")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        MaintenanceIncident,
        on_delete=models.PROTECT,
        related_name="events",
    )
    event_type = models.CharField(max_length=20, choices=Type.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="maintenance_events",
    )
    actor_role = models.CharField(max_length=12, choices=ActorRole.choices)
    from_status = models.CharField(
        max_length=20,
        choices=MaintenanceIncident.Status.choices,
        blank=True,
    )
    to_status = models.CharField(
        max_length=20,
        choices=MaintenanceIncident.Status.choices,
        blank=True,
    )
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("événement de maintenance")
        verbose_name_plural = _("événements de maintenance")

    def __str__(self) -> str:
        return f"{self.incident_id} - {self.get_event_type_display()}"
