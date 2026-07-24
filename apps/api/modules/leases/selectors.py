from django.db.models import QuerySet

from modules.accounts.models import User
from modules.properties.models import Ownership, Property

from .models import Lease, Tenant


def visible_properties_for(user: User) -> QuerySet[Property]:
    return Property.objects.filter(ownerships__user=user).distinct()


def manageable_properties_for(user: User) -> QuerySet[Property]:
    return Property.objects.filter(
        ownerships__user=user,
        ownerships__access_level=Ownership.AccessLevel.ACTIVE,
    ).distinct()


def visible_tenants_for(user: User) -> QuerySet[Tenant]:
    return Tenant.objects.filter(property__ownerships__user=user).distinct()


def visible_leases_for(user: User) -> QuerySet[Lease]:
    return Lease.objects.filter(property__ownerships__user=user).distinct()
