from dataclasses import dataclass
from datetime import timedelta
from secrets import compare_digest, randbelow
from urllib.parse import quote
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone, translation
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext_lazy as _

from modules.accounts.models import User
from modules.billing.models import RentCharge
from modules.i18n.utils import resolve_language
from modules.leases.models import Tenant
from modules.leases.selectors import manageable_properties_for
from modules.payments.models import Payment, SecurityDepositMovement
from modules.properties.models import Ownership

from .models import (
    DocumentAccessLink,
    ManualShareEvent,
    NotificationDelivery,
    OtpChallenge,
    RentalDocument,
)


LINK_SALT = "immolib.document-link.v1"
GRANT_SALT = "immolib.document-grant.v1"
OTP_CODE_SALT = "immolib.document-otp-code.v2"
OTP_LIFETIME_MINUTES = 10
GRANT_LIFETIME_SECONDS = 24 * 60 * 60
MAX_OTP_ATTEMPTS = 5


@dataclass(frozen=True)
class IssuedDocuments:
    payment_receipt: RentalDocument
    rent_receipt: RentalDocument | None
    obligation_documents: tuple[RentalDocument, ...]


@dataclass(frozen=True)
class ShareResult:
    access_link: DocumentAccessLink
    access_token: str
    secure_url: str
    deliveries: tuple[NotificationDelivery, ...]


@dataclass(frozen=True)
class OtpRequestResult:
    challenge: OtpChallenge
    code: str
    masked_destination: str
    created: bool


@dataclass(frozen=True)
class ManualShareResult:
    event: ManualShareEvent
    access_link: DocumentAccessLink
    secure_url: str
    subject: str
    message: str
    action_url: str


def _document_reference(prefix: str, document_id) -> str:
    return f"IMM-{prefix}-{timezone.localdate():%Y}-{document_id.hex[:12].upper()}"


def _primary_owner(charge: RentCharge) -> User:
    ownership = charge.lease.property.ownerships.select_related("user").get(
        role=Ownership.Role.PRIMARY
    )
    return ownership.user


def _snapshot_defaults(
    *,
    charge: RentCharge,
    payment: Payment | None,
    amount,
    payment_method: str = "",
) -> dict:
    property = charge.lease.property
    tenant = charge.lease.tenant
    owner = _primary_owner(charge)
    return {
        "payment": payment,
        "rent_charge": charge,
        "amount": amount,
        "currency": charge.currency,
        "period_start": charge.period_start,
        "period_end": charge.period_end,
        "payment_method": (
            payment.get_method_display() if payment is not None else payment_method
        ),
        "house_name": property.name,
        "house_address": property.address,
        "tenant_name": tenant.full_name,
        "tenant_phone": tenant.phone,
        "tenant_email": tenant.email,
        "owner_name": owner.get_full_name() or owner.phone,
        "owner_phone": owner.phone,
    }


@transaction.atomic
def issue_documents_for_payment(*, payment: Payment) -> IssuedDocuments:
    allocations = list(
        payment.allocations.select_related(
        "rent_charge__lease__property", "rent_charge__lease__tenant"
        ).order_by("rent_charge__period_start", "created_at")
    )
    if not allocations:
        raise ValidationError("Le paiement ne possède aucune affectation.")
    charge = allocations[0].rent_charge
    breakdown = [
        {
            "obligation_id": str(item.rent_charge_id),
            "type": item.rent_charge.charge_type,
            "label": item.rent_charge.obligation_label,
            "period": item.rent_charge.period_label,
            "amount": str(item.amount),
        }
        for item in allocations
    ]
    payment_snapshot = _snapshot_defaults(
        charge=charge, payment=payment, amount=payment.amount
    )
    payment_snapshot["period_start"] = min(
        item.rent_charge.period_start for item in allocations
    )
    payment_snapshot["period_end"] = max(
        item.rent_charge.period_end for item in allocations
    )
    payment_snapshot["breakdown"] = breakdown

    payment_document_id = uuid4()
    payment_receipt, _ = RentalDocument.objects.get_or_create(
        payment=payment,
        document_type=RentalDocument.Type.PAYMENT_RECEIPT,
        status=RentalDocument.Status.ACTIVE,
        defaults={
            "id": payment_document_id,
            "reference": _document_reference("REC", payment_document_id),
            **payment_snapshot,
        },
    )

    rent_receipt = None
    obligation_documents: list[RentalDocument] = []
    for allocation in allocations:
        obligation = allocation.rent_charge
        obligation.refresh_from_db()
        if obligation.status != RentCharge.Status.PAID:
            continue
        if obligation.charge_type == RentCharge.Type.SECURITY_DEPOSIT:
            document_type = RentalDocument.Type.DEPOSIT_RECEIPT
            prefix = "CAU"
        else:
            document_type = RentalDocument.Type.RENT_RECEIPT
            prefix = "QUT"
        document_id = uuid4()
        obligation_document, _ = RentalDocument.objects.get_or_create(
            rent_charge=obligation,
            document_type=document_type,
            status=RentalDocument.Status.ACTIVE,
            defaults={
                "id": document_id,
                "reference": _document_reference(prefix, document_id),
                "breakdown": [
                    {
                        "obligation_id": str(obligation.id),
                        "type": obligation.charge_type,
                        "label": obligation.obligation_label,
                        "period": obligation.period_label,
                        "amount": str(obligation.amount_due),
                    }
                ],
                **_snapshot_defaults(
                    charge=obligation,
                    payment=payment,
                    amount=obligation.amount_due,
                ),
            },
        )
        obligation_documents.append(obligation_document)
        if document_type == RentalDocument.Type.RENT_RECEIPT and rent_receipt is None:
            rent_receipt = obligation_document
    return IssuedDocuments(
        payment_receipt=payment_receipt,
        rent_receipt=rent_receipt,
        obligation_documents=tuple(obligation_documents),
    )


@transaction.atomic
def issue_security_deposit_settlement_document(
    *, movement: SecurityDepositMovement
) -> RentalDocument:
    movement = SecurityDepositMovement.objects.select_related(
        "deposit_obligation__lease__property",
        "deposit_obligation__lease__tenant",
        "resulting_payment",
        "target_rent_charge",
    ).get(id=movement.id)
    charge = movement.deposit_obligation
    document_id = uuid4()
    target_label = (
        movement.target_rent_charge.obligation_label
        if movement.target_rent_charge_id
        else ""
    )
    document, _ = RentalDocument.objects.get_or_create(
        deposit_movement=movement,
        document_type=RentalDocument.Type.DEPOSIT_SETTLEMENT,
        status=RentalDocument.Status.ACTIVE,
        defaults={
            "id": document_id,
            "reference": _document_reference("SOL", document_id),
            "breakdown": [
                {
                    "type": movement.movement_type,
                    "label": movement.get_movement_type_display(),
                    "amount": str(movement.amount),
                    "reason": movement.reason,
                    "agreement_reference": movement.agreement_reference,
                    "target": target_label,
                }
            ],
            **_snapshot_defaults(
                charge=charge,
                payment=movement.resulting_payment,
                amount=movement.amount,
                payment_method=movement.get_movement_type_display(),
            ),
        },
    )
    return document


@transaction.atomic
def void_documents_after_cancellation(*, payment: Payment) -> int:
    now = timezone.now()
    updated = RentalDocument.objects.filter(
        payment=payment,
        document_type=RentalDocument.Type.PAYMENT_RECEIPT,
        status=RentalDocument.Status.ACTIVE,
    ).update(
        status=RentalDocument.Status.VOIDED,
        voided_at=now,
        void_reason="Paiement annule",
    )
    for allocation in payment.allocations.select_related("rent_charge"):
        allocation.rent_charge.refresh_from_db()
        if allocation.rent_charge.status != RentCharge.Status.PAID:
            updated += RentalDocument.objects.filter(
                rent_charge=allocation.rent_charge,
                document_type__in=(
                    RentalDocument.Type.RENT_RECEIPT,
                    RentalDocument.Type.DEPOSIT_RECEIPT,
                ),
                status=RentalDocument.Status.ACTIVE,
            ).update(
                status=RentalDocument.Status.VOIDED,
                voided_at=now,
                void_reason="L'obligation n'est plus entièrement payée",
            )
    return updated


def _assert_can_share(*, actor: User, document: RentalDocument) -> None:
    property_id = document.rent_charge.lease.property_id
    if not manageable_properties_for(actor).filter(id=property_id).exists():
        raise PermissionDenied(_("Tu ne peux pas partager ce document."))


def sign_access_link(link: DocumentAccessLink) -> str:
    return signing.dumps({"link_id": str(link.id)}, salt=LINK_SALT, compress=True)


def resolve_access_link(token: str) -> DocumentAccessLink:
    try:
        payload = signing.loads(token, salt=LINK_SALT, max_age=31 * 24 * 60 * 60)
        link = DocumentAccessLink.objects.select_related(
            "document__rent_charge__lease__tenant"
        ).get(id=payload["link_id"])
    except (signing.BadSignature, KeyError, DocumentAccessLink.DoesNotExist) as exc:
        raise ValidationError(_("Lien invalide ou expire.")) from exc
    if link.revoked_at or link.expires_at <= timezone.now():
        raise ValidationError(_("Lien invalide ou expire."))
    if link.document.status != RentalDocument.Status.ACTIVE:
        raise ValidationError(_("Ce document n'est plus valide."))
    return link


def _destination_for(document: RentalDocument, channel: str) -> str:
    if channel == NotificationDelivery.Channel.EMAIL:
        if not document.tenant_email:
            raise ValidationError(_("Le locataire ne possede pas d'adresse email."))
        return document.tenant_email
    if channel in [
        NotificationDelivery.Channel.SMS,
        NotificationDelivery.Channel.WHATSAPP,
    ]:
        return document.tenant_phone
    raise ValidationError(_("Canal d'envoi invalide."))


def _document_link_message(
    *, document: RentalDocument, secure_url: str, expires_at
) -> tuple[str, str]:
    subject = _("ImmoLib - {document_type}").format(
        document_type=document.get_document_type_display()
    )
    message = _(
        "Bonjour {tenant}, consultez votre {document_type} ImmoLib : {url} "
        "(lien valable jusqu'au {expires_at})."
    ).format(
        tenant=document.tenant_name,
        document_type=document.get_document_type_display().lower(),
        url=secure_url,
        expires_at=timezone.localtime(expires_at).strftime("%d/%m/%Y"),
    )
    return subject, message


@transaction.atomic
def share_document(
    *, actor: User, document: RentalDocument, channels: list[str]
) -> ShareResult:
    _assert_can_share(actor=actor, document=document)
    if document.status != RentalDocument.Status.ACTIVE:
        raise ValidationError(_("Un document invalide ne peut pas etre partage."))
    unique_channels = tuple(dict.fromkeys(channels))
    if not unique_channels:
        raise ValidationError(_("Selectionne au moins un canal d'envoi."))

    link = DocumentAccessLink.objects.create(
        document=document,
        created_by=actor,
        expires_at=timezone.now() + timedelta(days=30),
    )
    recipient = document.rent_charge.lease.tenant.linked_user
    deliveries = []
    for channel in unique_channels:
        deliveries.append(
            NotificationDelivery.objects.create(
                access_link=link,
                kind=NotificationDelivery.Kind.DOCUMENT_LINK,
                channel=channel,
                destination=_destination_for(document, channel),
                language=resolve_language(user=recipient or actor),
            )
        )
    token = sign_access_link(link)
    return ShareResult(
        access_link=link,
        access_token=token,
        secure_url=f"{settings.PUBLIC_APP_URL}/documents/{token}",
        deliveries=tuple(deliveries),
    )


@transaction.atomic
def prepare_manual_share(
    *, actor: User, document: RentalDocument, channel: str
) -> ManualShareResult:
    _assert_can_share(actor=actor, document=document)
    if document.status != RentalDocument.Status.ACTIVE:
        raise ValidationError(_("Un document invalide ne peut pas être partagé."))
    if channel not in ManualShareEvent.Channel.values:
        raise ValidationError(_("Canal de partage manuel invalide."))

    link = DocumentAccessLink.objects.create(
        document=document,
        created_by=actor,
        expires_at=timezone.now() + timedelta(days=30),
    )
    token = sign_access_link(link)
    secure_url = f"{settings.PUBLIC_APP_URL}/documents/{token}"
    subject, message = _document_link_message(
        document=document,
        secure_url=secure_url,
        expires_at=link.expires_at,
    )

    destination = ""
    action_url = secure_url
    if channel == ManualShareEvent.Channel.WHATSAPP:
        destination = document.tenant_phone
        phone_digits = "".join(character for character in destination if character.isdigit())
        action_url = f"https://wa.me/{phone_digits}?text={quote(message)}"
    elif channel == ManualShareEvent.Channel.SMS:
        destination = document.tenant_phone
        action_url = f"sms:{destination}?body={quote(message)}"
    elif channel == ManualShareEvent.Channel.EMAIL:
        if not document.tenant_email:
            raise ValidationError(_("Le locataire ne possède pas d'adresse email."))
        destination = document.tenant_email
        action_url = (
            f"mailto:{destination}?subject={quote(subject)}&body={quote(message)}"
        )

    event = ManualShareEvent.objects.create(
        document=document,
        access_link=link,
        actor=actor,
        channel=channel,
        destination=destination,
    )
    return ManualShareResult(
        event=event,
        access_link=link,
        secure_url=secure_url,
        subject=subject,
        message=message,
        action_url=action_url,
    )


def _otp_code() -> str:
    return f"{randbelow(1_000_000):06d}"


def _otp_code_hash(challenge_id: str, code: str) -> str:
    return salted_hmac(
        OTP_CODE_SALT, f"{challenge_id}:{code.strip()}"
    ).hexdigest()


def _mask_destination(destination: str) -> str:
    if "@" in destination:
        name, domain = destination.split("@", 1)
        return f"{name[:2]}***@{domain}"
    return f"***{destination[-4:]}"


@transaction.atomic
def request_document_otp(*, access_token: str, channel: str) -> OtpRequestResult:
    link = resolve_access_link(access_token)
    destination = _destination_for(link.document, channel)
    now = timezone.now()
    latest = (
        OtpChallenge.objects.select_for_update()
        .filter(
            access_link=link,
            channel=channel,
            verified_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )
    cooldown = timedelta(seconds=settings.DOCUMENT_OTP_COOLDOWN_SECONDS)
    if latest and latest.created_at > now - cooldown:
        return OtpRequestResult(
            challenge=latest,
            code="",
            masked_destination=_mask_destination(latest.destination),
            created=False,
        )
    OtpChallenge.objects.filter(
        access_link=link,
        channel=channel,
        verified_at__isnull=True,
        expires_at__gt=now,
    ).update(expires_at=now)
    code = _otp_code()
    challenge = OtpChallenge.objects.create(
        access_link=link,
        channel=channel,
        destination=destination,
        expires_at=now + timedelta(minutes=OTP_LIFETIME_MINUTES),
    )
    challenge.code_hash = _otp_code_hash(challenge.id, code)
    challenge.save(update_fields=["code_hash"])
    recipient = link.document.rent_charge.lease.tenant.linked_user
    language = resolve_language(user=recipient)
    with translation.override(language):
        subject = _("Votre code de verification ImmoLib")
        body = _(
            "Votre code ImmoLib est {code}. Il expire dans 10 minutes. "
            "Ne le partagez avec personne."
        ).format(code=code)
    NotificationDelivery.objects.create(
        access_link=link,
        otp_challenge=challenge,
        kind=NotificationDelivery.Kind.OTP,
        channel=channel,
        destination=destination,
        language=language,
        subject=subject,
        body=body,
    )
    return OtpRequestResult(
        challenge=challenge,
        code=code,
        masked_destination=_mask_destination(destination),
        created=True,
    )


def verify_document_otp(*, challenge_id, code: str) -> str:
    invalid_code = False
    with transaction.atomic():
        try:
            challenge = OtpChallenge.objects.select_for_update().select_related(
                "access_link__document"
            ).get(id=challenge_id)
        except OtpChallenge.DoesNotExist as exc:
            raise ValidationError(_("Code invalide ou expire.")) from exc
        resolve_access_link(sign_access_link(challenge.access_link))
        if (
            challenge.expires_at <= timezone.now()
            or challenge.attempts >= MAX_OTP_ATTEMPTS
        ):
            raise ValidationError(_("Code invalide ou expire."))
        if not challenge.code_hash or not compare_digest(
            challenge.code_hash, _otp_code_hash(challenge.id, code)
        ):
            challenge.attempts += 1
            update_fields = ["attempts"]
            if challenge.attempts >= MAX_OTP_ATTEMPTS:
                challenge.expires_at = timezone.now()
                update_fields.append("expires_at")
            challenge.save(update_fields=update_fields)
            invalid_code = True
        else:
            challenge.verified_at = timezone.now()
            challenge.save(update_fields=["verified_at"])

    if invalid_code:
        raise ValidationError(_("Code invalide ou expire."))
    return signing.dumps(
        {"challenge_id": str(challenge.id)}, salt=GRANT_SALT, compress=True
    )


def resolve_document_grant(grant_token: str) -> RentalDocument:
    try:
        payload = signing.loads(
            grant_token, salt=GRANT_SALT, max_age=GRANT_LIFETIME_SECONDS
        )
        challenge = OtpChallenge.objects.select_related(
            "access_link__document__rent_charge__lease__tenant",
        ).get(id=payload["challenge_id"])
    except (signing.BadSignature, KeyError, OtpChallenge.DoesNotExist) as exc:
        raise ValidationError(_("Acces invalide ou expire.")) from exc
    if not challenge.verified_at:
        raise ValidationError(_("Acces non verifie."))
    resolve_access_link(sign_access_link(challenge.access_link))
    return challenge.access_link.document


def tenant_for_document(document: RentalDocument) -> Tenant:
    return document.rent_charge.lease.tenant
