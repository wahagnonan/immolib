from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.accounts.models import User
from modules.accounts.phones import normalize_e164

from .models import CoOwnerInvitation, Ownership, Property
from .selectors import primary_owned_properties_for


@dataclass(frozen=True)
class CreateHouseData:
    name: str
    address: str
    city: str
    commune: str = ""
    landmark: str = ""


@dataclass(frozen=True)
class InviteCoOwnerData:
    phone: str
    email: str = ""
    ownership_percentage: Decimal | None = None
    access_level: str = Ownership.AccessLevel.OBSERVER


@dataclass(frozen=True)
class UpdateCoOwnerData:
    ownership_percentage: Decimal | None
    access_level: str


def _assert_is_primary_owner(*, actor: User, property: Property) -> None:
    if not primary_owned_properties_for(actor).filter(id=property.id).exists():
        raise PermissionDenied(
            "Seul le propriétaire principal peut gérer les copropriétaires."
        )


def _assert_coowner_share_available(
    *,
    property: Property,
    percentage: Decimal | None,
    excluding=None,
    excluding_invitation=None,
) -> None:
    if percentage is None:
        return
    queryset = property.ownerships.filter(role=Ownership.Role.CO_OWNER)
    if excluding is not None:
        queryset = queryset.exclude(id=excluding.id)
    current_total = queryset.aggregate(total=Sum("ownership_percentage"))["total"]
    pending = property.co_owner_invitations.filter(
        status=CoOwnerInvitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    )
    if excluding_invitation is not None:
        pending = pending.exclude(id=excluding_invitation.id)
    pending_total = pending.aggregate(total=Sum("ownership_percentage"))["total"]
    total = (
        (current_total or Decimal("0"))
        + (pending_total or Decimal("0"))
        + percentage
    )
    if total >= Decimal("100"):
        raise ValidationError(
            {
                "ownership_percentage": (
                    "La somme des quote-parts des copropriétaires doit rester "
                    "inférieure à 100 %."
                )
            }
        )


def _recalculate_primary_share(*, property: Property) -> None:
    primary = property.ownerships.select_for_update().get(
        role=Ownership.Role.PRIMARY
    )
    coowners = property.ownerships.filter(role=Ownership.Role.CO_OWNER)
    if coowners.filter(ownership_percentage__isnull=True).exists():
        percentage = None
    else:
        total = coowners.aggregate(total=Sum("ownership_percentage"))["total"]
        percentage = Decimal("100") - (total or Decimal("0"))
    if primary.ownership_percentage != percentage:
        primary.ownership_percentage = percentage
        primary.save(update_fields=["ownership_percentage"])


@transaction.atomic
def create_house(*, owner: User, data: CreateHouseData) -> Property:
    """Crée toujours la maison et son propriétaire principal ensemble."""

    house = Property.objects.create(
        name=data.name,
        address=data.address,
        city=data.city,
        commune=data.commune,
        landmark=data.landmark,
    )
    Ownership.objects.create(
        property=house,
        user=owner,
        role=Ownership.Role.PRIMARY,
        access_level=Ownership.AccessLevel.ACTIVE,
        ownership_percentage=Decimal("100"),
    )
    return house


@transaction.atomic
def accept_coowner_invitation(
    *, invitation: CoOwnerInvitation, user: User
) -> Ownership:
    invitation = (
        CoOwnerInvitation.objects.select_for_update()
        .select_related("property")
        .get(id=invitation.id)
    )
    if invitation.status != CoOwnerInvitation.Status.PENDING:
        raise ValidationError("Cette invitation n'est plus en attente.")
    if invitation.expires_at <= timezone.now():
        raise ValidationError("Cette invitation a expiré.")
    if invitation.phone != user.phone:
        raise PermissionDenied("Cette invitation ne correspond pas à ce compte.")
    if invitation.property.ownerships.filter(user=user).exists():
        raise ValidationError("Ce compte possède déjà un rôle pour cette maison.")

    _assert_coowner_share_available(
        property=invitation.property,
        percentage=invitation.ownership_percentage,
        excluding_invitation=invitation,
    )
    ownership = Ownership.objects.create(
        property=invitation.property,
        user=user,
        role=Ownership.Role.CO_OWNER,
        access_level=invitation.access_level,
        ownership_percentage=invitation.ownership_percentage,
    )
    invitation.status = CoOwnerInvitation.Status.ACCEPTED
    invitation.accepted_by = user
    invitation.accepted_at = timezone.now()
    invitation.save(
        update_fields=["status", "accepted_by", "accepted_at", "updated_at"]
    )
    _recalculate_primary_share(property=invitation.property)
    return ownership


@transaction.atomic
def invite_coowner(
    *, actor: User, property: Property, data: InviteCoOwnerData
) -> CoOwnerInvitation:
    property = Property.objects.select_for_update().get(id=property.id)
    _assert_is_primary_owner(actor=actor, property=property)
    phone = normalize_e164(data.phone)
    property.co_owner_invitations.filter(
        status=CoOwnerInvitation.Status.PENDING,
        expires_at__lte=timezone.now(),
    ).update(status=CoOwnerInvitation.Status.EXPIRED)
    if property.ownerships.filter(user__phone=phone).exists():
        raise ValidationError(
            {"phone": "Ce compte possède déjà un rôle pour cette maison."}
        )
    if property.co_owner_invitations.filter(
        phone=phone, status=CoOwnerInvitation.Status.PENDING
    ).exists():
        raise ValidationError(
            {"phone": "Une invitation est déjà en attente pour ce numéro."}
        )
    _assert_coowner_share_available(
        property=property, percentage=data.ownership_percentage
    )

    invitation = CoOwnerInvitation.objects.create(
        property=property,
        phone=phone,
        email=data.email.strip().lower(),
        ownership_percentage=data.ownership_percentage,
        access_level=data.access_level,
        invited_by=actor,
    )
    existing_user = User.objects.filter(
        phone=phone,
        is_active=True,
        phone_verified_at__isnull=False,
    ).first()
    if existing_user:
        accept_coowner_invitation(invitation=invitation, user=existing_user)
        invitation.refresh_from_db()
    return invitation


def accept_pending_coowner_invitations(*, user: User) -> tuple[Ownership, ...]:
    if user.phone_verified_at is None:
        return ()
    invitations = tuple(
        CoOwnerInvitation.objects.filter(
            phone=user.phone,
            status=CoOwnerInvitation.Status.PENDING,
            expires_at__gt=timezone.now(),
        )
    )
    accepted = []
    for invitation in invitations:
        accepted.append(
            accept_coowner_invitation(invitation=invitation, user=user)
        )
    return tuple(accepted)


@transaction.atomic
def update_coowner(
    *, actor: User, ownership: Ownership, data: UpdateCoOwnerData
) -> Ownership:
    ownership = (
        Ownership.objects.select_for_update()
        .select_related("property")
        .get(id=ownership.id, role=Ownership.Role.CO_OWNER)
    )
    _assert_is_primary_owner(actor=actor, property=ownership.property)
    _assert_coowner_share_available(
        property=ownership.property,
        percentage=data.ownership_percentage,
        excluding=ownership,
    )
    ownership.ownership_percentage = data.ownership_percentage
    ownership.access_level = data.access_level
    ownership.full_clean()
    ownership.save(update_fields=["ownership_percentage", "access_level"])
    _recalculate_primary_share(property=ownership.property)
    return ownership


@transaction.atomic
def remove_coowner(*, actor: User, ownership: Ownership) -> None:
    ownership = (
        Ownership.objects.select_for_update()
        .select_related("property")
        .get(id=ownership.id, role=Ownership.Role.CO_OWNER)
    )
    property = ownership.property
    _assert_is_primary_owner(actor=actor, property=property)
    ownership.delete()
    _recalculate_primary_share(property=property)


@transaction.atomic
def revoke_coowner_invitation(
    *, actor: User, invitation: CoOwnerInvitation
) -> CoOwnerInvitation:
    invitation = (
        CoOwnerInvitation.objects.select_for_update()
        .select_related("property")
        .get(id=invitation.id)
    )
    _assert_is_primary_owner(actor=actor, property=invitation.property)
    if invitation.status != CoOwnerInvitation.Status.PENDING:
        raise ValidationError("Seule une invitation en attente peut être révoquée.")
    invitation.status = CoOwnerInvitation.Status.REVOKED
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["status", "revoked_at", "updated_at"])
    return invitation
