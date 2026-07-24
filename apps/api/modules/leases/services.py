from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.accounts.models import User
from modules.accounts.phones import normalize_e164
from modules.properties.models import Property

from .models import (
    Lease,
    Tenant,
    TenantInvitation,
    TenantInvitationShareEvent,
)
from .selectors import manageable_properties_for


@dataclass(frozen=True)
class CreateTenantData:
    full_name: str
    phone: str
    email: str = ""


@dataclass(frozen=True)
class CreateLeaseData:
    start_date: date
    monthly_rent: Decimal
    due_day: int
    end_date: date | None = None
    monthly_charges: Decimal = Decimal("0")
    security_deposit: Decimal = Decimal("0")
    rent_advance: Decimal = Decimal("0")
    accepts_mobile_money: bool = True
    accepts_cash: bool = True


@dataclass(frozen=True)
class TenantInvitationShareResult:
    invitation: TenantInvitation
    secure_url: str
    subject: str
    message: str
    action_url: str
    share_event: TenantInvitationShareEvent | None = None
    delivery: object | None = None


TENANT_INVITATION_SALT = "immolib.tenant-invitation.v1"


def _assert_can_manage(*, actor: User, property: Property) -> None:
    if not manageable_properties_for(actor).filter(id=property.id).exists():
        raise PermissionDenied("Tu ne peux pas modifier cette maison.")


def _emails_match(first: str, second: str) -> bool:
    return bool(first and second and first.strip().casefold() == second.strip().casefold())


def sign_tenant_invitation(invitation: TenantInvitation) -> str:
    return signing.dumps(
        {"invitation_id": str(invitation.id)},
        salt=TENANT_INVITATION_SALT,
        compress=True,
    )


def tenant_invitation_url(invitation: TenantInvitation) -> str:
    return (
        f"{settings.PUBLIC_APP_URL}/invitation-locataire/"
        f"{sign_tenant_invitation(invitation)}"
    )


def resolve_tenant_invitation(token: str) -> TenantInvitation:
    max_age = (settings.TENANT_INVITATION_LIFETIME_DAYS + 1) * 24 * 60 * 60
    try:
        payload = signing.loads(
            token,
            salt=TENANT_INVITATION_SALT,
            max_age=max_age,
        )
        invitation = TenantInvitation.objects.select_related(
            "tenant__property",
            "tenant__linked_user",
            "invited_by",
            "claimed_by",
            "accepted_by",
        ).get(id=payload["invitation_id"])
    except (
        signing.BadSignature,
        KeyError,
        TenantInvitation.DoesNotExist,
    ) as exc:
        raise ValidationError("Invitation invalide ou expirée.") from exc

    if invitation.is_expired:
        TenantInvitation.objects.filter(
            id=invitation.id,
            status=TenantInvitation.Status.PENDING,
        ).update(status=TenantInvitation.Status.EXPIRED, updated_at=timezone.now())
        invitation.status = TenantInvitation.Status.EXPIRED
    return invitation


def _assert_active_invitation(invitation: TenantInvitation) -> None:
    if invitation.status != TenantInvitation.Status.PENDING:
        raise ValidationError("Cette invitation n'est plus active.")
    if invitation.expires_at <= timezone.now():
        raise ValidationError("Cette invitation est expirée.")


@transaction.atomic
def create_tenant_invitation(
    *, actor: User, tenant: Tenant
) -> TenantInvitation:
    tenant = (
        Tenant.objects.select_for_update()
        .select_related("property", "linked_user")
        .get(id=tenant.id)
    )
    _assert_can_manage(actor=actor, property=tenant.property)
    if tenant.linked_user_id:
        raise ValidationError("Ce locataire possède déjà un compte ImmoLib.")

    now = timezone.now()
    tenant.invitations.filter(
        status=TenantInvitation.Status.PENDING,
        expires_at__lte=now,
    ).update(status=TenantInvitation.Status.EXPIRED, updated_at=now)
    invitation = tenant.invitations.filter(
        status=TenantInvitation.Status.PENDING,
        expires_at__gt=now,
    ).first()
    if invitation is None:
        invitation = TenantInvitation.objects.create(
            tenant=tenant,
            invited_by=actor,
            expires_at=now
            + timedelta(days=settings.TENANT_INVITATION_LIFETIME_DAYS),
        )
    if tenant.status != Tenant.Status.INVITED:
        tenant.status = Tenant.Status.INVITED
        tenant.save(update_fields=["status", "updated_at"])
    return invitation


def _invitation_message(
    invitation: TenantInvitation,
) -> tuple[str, str, str]:
    secure_url = tenant_invitation_url(invitation)
    owner_name = (
        invitation.invited_by.get_full_name() or invitation.invited_by.phone
    )
    subject = "Invitation à rejoindre ImmoLib"
    message = (
        f"Bonjour {invitation.tenant.full_name}, {owner_name} vous invite à "
        f"rejoindre ImmoLib pour la maison {invitation.tenant.property.name}. "
        f"Créez ou rattachez votre compte ici : {secure_url} "
        f"(invitation valable jusqu'au {invitation.expires_at:%d/%m/%Y})."
    )
    return secure_url, subject, message


@transaction.atomic
def share_tenant_invitation(
    *, actor: User, invitation: TenantInvitation, channel: str
) -> TenantInvitationShareResult:
    invitation = TenantInvitation.objects.select_related(
        "tenant__property", "invited_by"
    ).get(id=invitation.id)
    _assert_can_manage(actor=actor, property=invitation.tenant.property)
    _assert_active_invitation(invitation)
    secure_url, subject, message = _invitation_message(invitation)

    if channel == "EMAIL_AUTOMATIC":
        if not invitation.tenant.email:
            raise ValidationError("Le locataire ne possède pas d'adresse email.")
        from modules.documents.models import NotificationDelivery

        delivery, _ = NotificationDelivery.objects.get_or_create(
            tenant_invitation=invitation,
            kind=NotificationDelivery.Kind.TENANT_INVITATION,
            channel=NotificationDelivery.Channel.EMAIL,
            defaults={"destination": invitation.tenant.email},
        )
        return TenantInvitationShareResult(
            invitation=invitation,
            secure_url=secure_url,
            subject=subject,
            message=message,
            action_url=secure_url,
            delivery=delivery,
        )

    if channel not in TenantInvitationShareEvent.Channel.values:
        raise ValidationError("Canal de partage invalide.")

    destination = ""
    action_url = secure_url
    if channel == TenantInvitationShareEvent.Channel.WHATSAPP:
        destination = invitation.tenant.phone
        phone_digits = "".join(
            character for character in destination if character.isdigit()
        )
        action_url = f"https://wa.me/{phone_digits}?text={quote(message)}"
    elif channel == TenantInvitationShareEvent.Channel.SMS:
        destination = invitation.tenant.phone
        action_url = f"sms:{destination}?body={quote(message)}"
    elif channel == TenantInvitationShareEvent.Channel.EMAIL:
        if not invitation.tenant.email:
            raise ValidationError("Le locataire ne possède pas d'adresse email.")
        destination = invitation.tenant.email
        action_url = (
            f"mailto:{destination}?subject={quote(subject)}&body={quote(message)}"
        )

    share_event = TenantInvitationShareEvent.objects.create(
        invitation=invitation,
        actor=actor,
        channel=channel,
        destination=destination,
    )
    return TenantInvitationShareResult(
        invitation=invitation,
        secure_url=secure_url,
        subject=subject,
        message=message,
        action_url=action_url,
        share_event=share_event,
    )


@transaction.atomic
def revoke_tenant_invitation(
    *, actor: User, invitation: TenantInvitation
) -> TenantInvitation:
    invitation = (
        TenantInvitation.objects.select_for_update()
        .select_related("tenant__property")
        .get(id=invitation.id)
    )
    _assert_can_manage(actor=actor, property=invitation.tenant.property)
    _assert_active_invitation(invitation)
    now = timezone.now()
    invitation.status = TenantInvitation.Status.REVOKED
    invitation.revoked_at = now
    invitation.save(update_fields=["status", "revoked_at", "updated_at"])
    if invitation.tenant.linked_user_id is None:
        invitation.tenant.status = Tenant.Status.UNREGISTERED
        invitation.tenant.save(update_fields=["status", "updated_at"])
    return invitation


def validate_tenant_invitation_registration(
    *, token: str, phone: str, email: str
) -> TenantInvitation:
    invitation = resolve_tenant_invitation(token)
    _assert_active_invitation(invitation)
    tenant = invitation.tenant
    if normalize_e164(phone) != normalize_e164(tenant.phone):
        raise ValidationError(
            {"phone": "Utilisez le numéro de téléphone indiqué dans l'invitation."}
        )
    if tenant.email and not _emails_match(email, tenant.email):
        raise ValidationError(
            {"email": "Utilisez l'adresse email indiquée dans l'invitation."}
        )
    if not tenant.email and email:
        raise ValidationError(
            {
                "email": (
                    "Cette invitation doit d'abord être validée par le téléphone. "
                    "Vous pourrez ajouter un email ensuite."
                )
            }
        )
    return invitation


@transaction.atomic
def reserve_tenant_invitation(
    *, invitation: TenantInvitation, user: User
) -> TenantInvitation:
    invitation = TenantInvitation.objects.select_for_update().select_related(
        "tenant"
    ).get(id=invitation.id)
    _assert_active_invitation(invitation)
    if invitation.claimed_by_id and invitation.claimed_by_id != user.id:
        raise ValidationError("Cette invitation est déjà réclamée par un autre compte.")
    invitation.claimed_by = user
    invitation.claimed_at = timezone.now()
    invitation.save(update_fields=["claimed_by", "claimed_at", "updated_at"])
    return invitation


def _user_has_tenant_proof(*, invitation: TenantInvitation, user: User) -> bool:
    tenant = invitation.tenant
    phone_proven = (
        user.phone_verified_at is not None
        and normalize_e164(user.phone) == normalize_e164(tenant.phone)
    )
    email_proven = (
        user.email_verified_at is not None
        and _emails_match(user.email, tenant.email)
    )
    return phone_proven or email_proven


@transaction.atomic
def accept_tenant_invitation(
    *, invitation: TenantInvitation, user: User
) -> TenantInvitation:
    invitation = (
        TenantInvitation.objects.select_for_update()
        .select_related("tenant")
        .get(id=invitation.id)
    )
    _assert_active_invitation(invitation)
    if invitation.claimed_by_id and invitation.claimed_by_id != user.id:
        raise ValidationError("Cette invitation appartient à un autre compte.")
    if not _user_has_tenant_proof(invitation=invitation, user=user):
        raise ValidationError(
            "Vérifiez le téléphone ou l'email indiqué dans l'invitation."
        )

    now = timezone.now()
    tenant = Tenant.objects.select_for_update().get(id=invitation.tenant_id)
    if tenant.linked_user_id and tenant.linked_user_id != user.id:
        raise ValidationError("Ce locataire est déjà lié à un autre compte.")
    tenant.linked_user = user
    tenant.status = Tenant.Status.ACTIVE
    tenant.save(update_fields=["linked_user", "status", "updated_at"])

    invitation.claimed_by = user
    invitation.claimed_at = invitation.claimed_at or now
    invitation.accepted_by = user
    invitation.accepted_at = now
    invitation.status = TenantInvitation.Status.ACCEPTED
    invitation.save(
        update_fields=[
            "claimed_by",
            "claimed_at",
            "accepted_by",
            "accepted_at",
            "status",
            "updated_at",
        ]
    )
    TenantInvitation.objects.filter(
        tenant=tenant,
        status=TenantInvitation.Status.PENDING,
    ).exclude(id=invitation.id).update(
        status=TenantInvitation.Status.REVOKED,
        revoked_at=now,
        updated_at=now,
    )
    return invitation


@transaction.atomic
def claim_tenant_invitation(
    *, token: str, user: User
) -> TenantInvitation:
    invitation = resolve_tenant_invitation(token)
    _assert_active_invitation(invitation)
    tenant = invitation.tenant
    contact_matches = (
        normalize_e164(user.phone) == normalize_e164(tenant.phone)
        or _emails_match(user.email, tenant.email)
    )
    if not contact_matches:
        raise ValidationError(
            "Ce compte ne correspond pas aux coordonnées de l'invitation."
        )
    reserve_tenant_invitation(invitation=invitation, user=user)
    return accept_tenant_invitation(invitation=invitation, user=user)


def accept_pending_tenant_invitations(*, user: User) -> tuple[TenantInvitation, ...]:
    candidates = TenantInvitation.objects.filter(
        status=TenantInvitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).filter(
        Q(claimed_by=user)
        | Q(
            tenant__phone=user.phone,
            claimed_by__isnull=True,
        )
    )
    accepted = []
    for invitation in candidates.select_related("tenant"):
        try:
            accepted.append(
                accept_tenant_invitation(invitation=invitation, user=user)
            )
        except ValidationError:
            continue
    return tuple(accepted)


@transaction.atomic
def create_tenant(
    *, actor: User, property: Property, data: CreateTenantData
) -> Tenant:
    _assert_can_manage(actor=actor, property=property)
    phone = normalize_e164(data.phone)
    linked_user = User.objects.filter(
        phone=phone,
        is_active=True,
        phone_verified_at__isnull=False,
    ).first()
    tenant = Tenant(
        property=property,
        full_name=data.full_name.strip(),
        phone=phone,
        email=data.email.strip(),
        linked_user=linked_user,
        status=Tenant.Status.ACTIVE if linked_user else Tenant.Status.UNREGISTERED,
        created_by=actor,
    )
    tenant.full_clean()
    tenant.save()
    return tenant


@transaction.atomic
def create_lease(
    *, actor: User, property: Property, tenant: Tenant, data: CreateLeaseData
) -> Lease:
    _assert_can_manage(actor=actor, property=property)
    lease = Lease(
        property=property,
        tenant=tenant,
        start_date=data.start_date,
        end_date=data.end_date,
        monthly_rent=data.monthly_rent,
        monthly_charges=data.monthly_charges,
        due_day=data.due_day,
        security_deposit=data.security_deposit,
        rent_advance=data.rent_advance,
        accepts_mobile_money=data.accepts_mobile_money,
        accepts_cash=data.accepts_cash,
        created_by=actor,
    )
    lease.full_clean()
    lease.save()
    return lease


@transaction.atomic
def activate_lease(*, actor: User, lease: Lease) -> Lease:
    lease = Lease.objects.select_for_update().select_related("property").get(id=lease.id)
    _assert_can_manage(actor=actor, property=lease.property)

    if lease.status != Lease.Status.DRAFT:
        raise ValidationError("Seul un bail brouillon peut etre active.")
    if lease.property.status == Property.Status.UNAVAILABLE:
        raise ValidationError("Une maison indisponible ne peut pas etre louee.")
    if Lease.objects.filter(
        property=lease.property, status=Lease.Status.ACTIVE
    ).exists():
        raise ValidationError("Cette maison possede deja un bail actif.")

    lease.status = Lease.Status.ACTIVE
    lease.activated_at = timezone.now()
    lease.save(update_fields=["status", "activated_at", "updated_at"])

    lease.property.status = Property.Status.OCCUPIED
    lease.property.save(update_fields=["status", "updated_at"])
    return lease


@transaction.atomic
def close_lease(*, actor: User, lease: Lease) -> Lease:
    """Termine immediatement un bail actif et libere la maison."""

    lease = Lease.objects.select_for_update().select_related("property").get(id=lease.id)
    _assert_can_manage(actor=actor, property=lease.property)

    if lease.status != Lease.Status.ACTIVE:
        raise ValidationError("Seul un bail actif peut etre termine.")

    lease.status = Lease.Status.ENDED
    lease.ended_at = timezone.now()
    lease.save(update_fields=["status", "ended_at", "updated_at"])

    lease.property.status = Property.Status.VACANT
    lease.property.save(update_fields=["status", "updated_at"])
    return lease
