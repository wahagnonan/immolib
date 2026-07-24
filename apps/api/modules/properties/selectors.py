from django.db.models import QuerySet

from modules.accounts.models import User

from .models import CoOwnerInvitation, Ownership, Property


def primary_owned_properties_for(user: User) -> QuerySet[Property]:
    return Property.objects.filter(
        ownerships__user=user,
        ownerships__role=Ownership.Role.PRIMARY,
    ).distinct()


def manageable_co_ownerships_for(user: User) -> QuerySet[Ownership]:
    return Ownership.objects.filter(
        role=Ownership.Role.CO_OWNER,
        property__ownerships__user=user,
        property__ownerships__role=Ownership.Role.PRIMARY,
    ).distinct()


def co_owner_invitations_for(user: User) -> QuerySet[CoOwnerInvitation]:
    return CoOwnerInvitation.objects.filter(
        property__ownerships__user=user,
        property__ownerships__role=Ownership.Role.PRIMARY,
    ).distinct()
