from django.db.models import QuerySet

from modules.accounts.models import User
from modules.leases.models import Tenant

from .models import MaintenanceIncident


def owner_visible_incidents_for(user: User) -> QuerySet[MaintenanceIncident]:
    return MaintenanceIncident.objects.filter(
        property__ownerships__user=user
    ).distinct()


def tenant_visible_incidents_for(user: User) -> QuerySet[MaintenanceIncident]:
    return MaintenanceIncident.objects.filter(
        tenant__linked_user=user,
        tenant__status=Tenant.Status.ACTIVE,
    ).distinct()
