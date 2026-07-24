from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.accounts.models import User
from modules.leases.models import Lease, Tenant
from modules.leases.selectors import manageable_properties_for

from .models import MaintenanceEvent, MaintenanceIncident


@dataclass(frozen=True)
class CreateIncidentData:
    title: str
    description: str
    category: str
    priority: str = MaintenanceIncident.Priority.NORMAL
    occurred_at: datetime | None = None


OWNER_TRANSITIONS = {
    MaintenanceIncident.Status.REPORTED: {
        MaintenanceIncident.Status.ACKNOWLEDGED,
        MaintenanceIncident.Status.CANCELLED,
    },
    MaintenanceIncident.Status.ACKNOWLEDGED: {
        MaintenanceIncident.Status.IN_PROGRESS,
        MaintenanceIncident.Status.CANCELLED,
    },
    MaintenanceIncident.Status.IN_PROGRESS: {
        MaintenanceIncident.Status.RESOLVED,
        MaintenanceIncident.Status.CANCELLED,
    },
    MaintenanceIncident.Status.RESOLVED: {
        MaintenanceIncident.Status.IN_PROGRESS,
    },
}


def _actor_role(*, actor: User, lease: Lease) -> str:
    if lease.tenant.linked_user_id == actor.id:
        return MaintenanceEvent.ActorRole.TENANT
    if manageable_properties_for(actor).filter(id=lease.property_id).exists():
        return MaintenanceEvent.ActorRole.OWNER
    raise PermissionDenied("Tu ne peux pas signaler un incident pour ce bail.")


def _assert_tenant_access(*, actor: User, incident: MaintenanceIncident) -> None:
    if (
        incident.tenant.linked_user_id != actor.id
        or incident.tenant.status != Tenant.Status.ACTIVE
    ):
        raise PermissionDenied("Cet incident n'appartient pas à ce locataire.")


def _assert_owner_can_manage(*, actor: User, incident: MaintenanceIncident) -> None:
    if not manageable_properties_for(actor).filter(
        id=incident.property_id
    ).exists():
        raise PermissionDenied("Tu ne peux pas modifier cet incident.")


@transaction.atomic
def create_incident(
    *, actor: User, lease: Lease, data: CreateIncidentData
) -> MaintenanceIncident:
    lease = Lease.objects.select_for_update().select_related(
        "property",
        "tenant__linked_user",
    ).get(id=lease.id)
    if lease.status != Lease.Status.ACTIVE:
        raise ValidationError("Un incident doit concerner un bail actif.")
    actor_role = _actor_role(actor=actor, lease=lease)
    if data.category not in MaintenanceIncident.Category.values:
        raise ValidationError("Catégorie d'incident invalide.")
    if data.priority not in MaintenanceIncident.Priority.values:
        raise ValidationError("Priorité d'incident invalide.")
    if not data.title.strip() or not data.description.strip():
        raise ValidationError("Le titre et la description sont obligatoires.")

    incident = MaintenanceIncident(
        property=lease.property,
        lease=lease,
        tenant=lease.tenant,
        reported_by=actor,
        title=data.title.strip(),
        description=data.description.strip(),
        category=data.category,
        priority=data.priority,
        occurred_at=data.occurred_at,
    )
    incident.full_clean()
    incident.save()
    MaintenanceEvent.objects.create(
        incident=incident,
        event_type=MaintenanceEvent.Type.REPORTED,
        actor=actor,
        actor_role=actor_role,
        to_status=MaintenanceIncident.Status.REPORTED,
        message=incident.description,
    )
    return incident


@transaction.atomic
def change_incident_status_by_owner(
    *,
    actor: User,
    incident: MaintenanceIncident,
    target_status: str,
    message: str = "",
) -> MaintenanceIncident:
    incident = (
        MaintenanceIncident.objects.select_for_update()
        .select_related("property", "tenant")
        .get(id=incident.id)
    )
    _assert_owner_can_manage(actor=actor, incident=incident)
    allowed = OWNER_TRANSITIONS.get(incident.status, set())
    if target_status not in allowed:
        raise ValidationError(
            f"Le passage de {incident.get_status_display()} vers ce statut est interdit."
        )
    previous_status = incident.status
    now = timezone.now()
    incident.status = target_status
    if target_status == MaintenanceIncident.Status.RESOLVED:
        incident.resolved_at = now
    elif previous_status == MaintenanceIncident.Status.RESOLVED:
        incident.resolved_at = None
    if target_status == MaintenanceIncident.Status.CANCELLED:
        incident.closed_at = now
    incident.save(
        update_fields=[
            "status",
            "resolved_at",
            "closed_at",
            "updated_at",
        ]
    )
    MaintenanceEvent.objects.create(
        incident=incident,
        event_type=MaintenanceEvent.Type.STATUS_CHANGED,
        actor=actor,
        actor_role=MaintenanceEvent.ActorRole.OWNER,
        from_status=previous_status,
        to_status=target_status,
        message=message.strip(),
    )
    return incident


@transaction.atomic
def respond_to_resolution_by_tenant(
    *,
    actor: User,
    incident: MaintenanceIncident,
    action: str,
    message: str = "",
) -> MaintenanceIncident:
    incident = (
        MaintenanceIncident.objects.select_for_update()
        .select_related("tenant", "property")
        .get(id=incident.id)
    )
    _assert_tenant_access(actor=actor, incident=incident)
    if incident.status != MaintenanceIncident.Status.RESOLVED:
        raise ValidationError(
            "Le locataire peut répondre uniquement après une résolution."
        )
    if action not in ("CLOSE", "REOPEN"):
        raise ValidationError("Réponse locataire invalide.")
    if action == "REOPEN" and not message.strip():
        raise ValidationError("Expliquez pourquoi le problème persiste.")

    previous_status = incident.status
    now = timezone.now()
    if action == "CLOSE":
        incident.status = MaintenanceIncident.Status.CLOSED
        incident.closed_at = now
    else:
        incident.status = MaintenanceIncident.Status.IN_PROGRESS
        incident.resolved_at = None
    incident.save(
        update_fields=[
            "status",
            "resolved_at",
            "closed_at",
            "updated_at",
        ]
    )
    MaintenanceEvent.objects.create(
        incident=incident,
        event_type=MaintenanceEvent.Type.STATUS_CHANGED,
        actor=actor,
        actor_role=MaintenanceEvent.ActorRole.TENANT,
        from_status=previous_status,
        to_status=incident.status,
        message=message.strip(),
    )
    return incident


@transaction.atomic
def add_incident_comment(
    *,
    actor: User,
    incident: MaintenanceIncident,
    message: str,
    as_tenant: bool,
) -> MaintenanceEvent:
    incident = MaintenanceIncident.objects.select_related(
        "tenant",
        "property",
    ).get(id=incident.id)
    if as_tenant:
        _assert_tenant_access(actor=actor, incident=incident)
        actor_role = MaintenanceEvent.ActorRole.TENANT
    else:
        _assert_owner_can_manage(actor=actor, incident=incident)
        actor_role = MaintenanceEvent.ActorRole.OWNER
    if incident.status in (
        MaintenanceIncident.Status.CLOSED,
        MaintenanceIncident.Status.CANCELLED,
    ):
        raise ValidationError("Cet incident est clôturé.")
    if not message.strip():
        raise ValidationError("Le commentaire ne peut pas être vide.")
    return MaintenanceEvent.objects.create(
        incident=incident,
        event_type=MaintenanceEvent.Type.COMMENTED,
        actor=actor,
        actor_role=actor_role,
        message=message.strip(),
    )
