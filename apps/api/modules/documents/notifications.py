import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F, Q
from django.utils import timezone
from django.utils.module_loading import import_string

from modules.billing.models import RentCharge

from .models import NotificationDelivery, RentalDocument
from .services import otp_code_for, sign_access_link


logger = logging.getLogger(__name__)


class PermanentNotificationError(Exception):
    """Erreur fonctionnelle qui ne sera pas corrigée par une nouvelle tentative."""


@dataclass(frozen=True)
class NotificationMessage:
    delivery_id: str
    channel: str
    destination: str
    subject: str
    body: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class DeliveryReceipt:
    provider_reference: str = ""


class NotificationAdapter(Protocol):
    def send(self, message: NotificationMessage) -> DeliveryReceipt: ...


@dataclass(frozen=True)
class ProcessingSummary:
    claimed: int
    sent: int
    requeued: int
    failed: int
    unavailable: int
    recovered: int


class SimulatedNotificationAdapter:
    """Adaptateur explicite de développement qui ne contacte aucun fournisseur."""

    def send(self, message: NotificationMessage) -> DeliveryReceipt:
        logger.info(
            "Notification simulee: id=%s canal=%s destination=%s",
            message.delivery_id,
            message.channel,
            _mask_destination(message.destination),
        )
        return DeliveryReceipt(provider_reference=f"SIM-{message.delivery_id}")


def _mask_destination(destination: str) -> str:
    if "@" in destination:
        name, domain = destination.split("@", 1)
        return f"{name[:2]}***@{domain}"
    return f"***{destination[-4:]}"


def load_configured_adapters() -> dict[str, NotificationAdapter]:
    adapters: dict[str, NotificationAdapter] = {}
    for channel, dotted_path in settings.NOTIFICATION_ADAPTERS.items():
        if not dotted_path:
            continue
        factory = import_string(dotted_path)
        adapter = factory()
        if not callable(getattr(adapter, "send", None)):
            raise ImproperlyConfigured(
                f"L'adaptateur {dotted_path} ne fournit pas de methode send()."
            )
        adapters[channel] = adapter
    return adapters


def build_notification_message(
    delivery: NotificationDelivery, *, now=None
) -> NotificationMessage:
    now = now or timezone.now()
    if delivery.kind == NotificationDelivery.Kind.ACCOUNT_OTP:
        challenge = delivery.account_challenge
        if challenge is None:
            raise PermanentNotificationError("Le code de compte est introuvable.")
        if (
            challenge.expires_at <= now
            or challenge.verified_at is not None
            or challenge.consumed_at is not None
        ):
            raise PermanentNotificationError("Le code de compte n'est plus actif.")
        from modules.accounts.models import AccountOtpChallenge
        from modules.accounts.services import account_otp_code_for

        code = account_otp_code_for(challenge)
        if challenge.purpose == AccountOtpChallenge.Purpose.PASSWORD_RESET:
            subject = "Réinitialisation de votre mot de passe ImmoLib"
            action = "réinitialiser votre mot de passe"
        elif challenge.purpose == AccountOtpChallenge.Purpose.EMAIL_VERIFICATION:
            subject = "Vérification de votre email ImmoLib"
            action = "vérifier votre adresse email"
        else:
            subject = "Vérification de votre téléphone ImmoLib"
            action = "vérifier votre numéro de téléphone"
        return NotificationMessage(
            delivery_id=str(delivery.id),
            channel=delivery.channel,
            destination=delivery.destination,
            subject=subject,
            body=(
                f"Votre code ImmoLib pour {action} est {code}. "
                f"Il expire à {challenge.expires_at:%H:%M}. "
                "Ne le partagez avec personne."
            ),
            metadata={
                "kind": delivery.kind,
                "channel": delivery.channel,
                "purpose": challenge.purpose,
            },
        )

    if delivery.kind == NotificationDelivery.Kind.TENANT_INVITATION:
        invitation = delivery.tenant_invitation
        if invitation is None:
            raise PermanentNotificationError("L'invitation du locataire est introuvable.")
        if (
            invitation.status != invitation.Status.PENDING
            or invitation.expires_at <= now
        ):
            raise PermanentNotificationError(
                "L'invitation du locataire n'est plus active."
            )
        from modules.leases.services import tenant_invitation_url

        secure_url = tenant_invitation_url(invitation)
        owner_name = (
            invitation.invited_by.get_full_name() or invitation.invited_by.phone
        )
        return NotificationMessage(
            delivery_id=str(delivery.id),
            channel=delivery.channel,
            destination=delivery.destination,
            subject="Invitation à rejoindre ImmoLib",
            body=(
                f"Bonjour {invitation.tenant.full_name}, {owner_name} vous invite "
                f"à rejoindre ImmoLib pour la maison "
                f"{invitation.tenant.property.name}. Créez ou rattachez votre "
                f"compte ici : {secure_url} (invitation valable jusqu'au "
                f"{invitation.expires_at:%d/%m/%Y})."
            ),
            metadata={
                "kind": delivery.kind,
                "channel": delivery.channel,
                "tenant_invitation_id": str(invitation.id),
                "tenant_id": str(invitation.tenant_id),
                "property_id": str(invitation.tenant.property_id),
                "url": secure_url,
            },
        )

    if delivery.kind == NotificationDelivery.Kind.RENT_REMINDER:
        charge = delivery.rent_charge
        if charge is None:
            raise PermanentNotificationError("L'echeance du rappel est introuvable.")
        if charge.status in (
            RentCharge.Status.PAID,
            RentCharge.Status.DISPUTED,
            RentCharge.Status.CANCELLED,
        ) or charge.balance_due <= 0:
            raise PermanentNotificationError("L'echeance ne doit plus etre relancee.")
        today = timezone.localdate(now)
        days_after_due = (today - charge.due_date).days
        balance = f"{charge.balance_due:,.0f}".replace(",", " ")
        house = charge.lease.property.name
        tenant = charge.lease.tenant.full_name
        if days_after_due < 0:
            timing = f"arrive a echeance le {charge.due_date:%d/%m/%Y}"
        elif days_after_due == 0:
            timing = "est a regler aujourd'hui"
        else:
            suffix = "jour" if days_after_due == 1 else "jours"
            timing = (
                f"est en retard depuis {days_after_due} {suffix} "
                f"(echeance du {charge.due_date:%d/%m/%Y})"
            )
        return NotificationMessage(
            delivery_id=str(delivery.id),
            channel=delivery.channel,
            destination=delivery.destination,
            subject=f"ImmoLib - Rappel de loyer {charge.period_label}",
            body=(
                f"Bonjour {tenant}, votre loyer pour {house} ({charge.period_label}), "
                f"avec un solde de {balance} {charge.currency}, {timing}."
            ),
            metadata={
                "kind": delivery.kind,
                "channel": delivery.channel,
                "rent_charge_id": str(charge.id),
                "property_id": str(charge.lease.property_id),
                "due_date": charge.due_date.isoformat(),
            },
        )

    link = delivery.access_link
    if link is None:
        raise PermanentNotificationError("Le lien de notification est introuvable.")
    document = link.document
    metadata = {
        "kind": delivery.kind,
        "channel": delivery.channel,
        "document_reference": document.reference,
    }

    if delivery.kind == NotificationDelivery.Kind.DOCUMENT_LINK:
        if link.revoked_at or link.expires_at <= now:
            raise PermanentNotificationError("Le lien du document n'est plus actif.")
        if document.status != RentalDocument.Status.ACTIVE:
            raise PermanentNotificationError("Le document n'est plus actif.")
        token = sign_access_link(link)
        secure_url = f"{settings.PUBLIC_APP_URL}/documents/{token}"
        body = (
            f"Bonjour {document.tenant_name}, consultez votre "
            f"{document.get_document_type_display().lower()} ImmoLib : {secure_url} "
            f"(lien valable jusqu'au {link.expires_at:%d/%m/%Y})."
        )
        return NotificationMessage(
            delivery_id=str(delivery.id),
            channel=delivery.channel,
            destination=delivery.destination,
            subject=f"ImmoLib - {document.get_document_type_display()}",
            body=body,
            metadata=metadata,
        )

    if delivery.kind == NotificationDelivery.Kind.OTP:
        challenge = delivery.otp_challenge
        if challenge is None:
            raise PermanentNotificationError("Le code OTP est introuvable.")
        if challenge.expires_at <= now or challenge.verified_at:
            raise PermanentNotificationError("Le code OTP n'est plus actif.")
        code = otp_code_for(challenge)
        return NotificationMessage(
            delivery_id=str(delivery.id),
            channel=delivery.channel,
            destination=delivery.destination,
            subject="Votre code de verification ImmoLib",
            body=(
                f"Votre code ImmoLib est {code}. Il expire dans 10 minutes. "
                "Ne le partagez avec personne."
            ),
            metadata=metadata,
        )

    raise PermanentNotificationError("Type de notification inconnu.")


def recover_stale_deliveries(*, now=None) -> int:
    now = now or timezone.now()
    cutoff = now - timedelta(
        seconds=settings.NOTIFICATION_PROCESSING_TIMEOUT_SECONDS
    )
    stale = NotificationDelivery.objects.filter(
        status=NotificationDelivery.Status.PROCESSING,
        last_attempt_at__lt=cutoff,
    )
    exhausted = stale.filter(
        attempt_count__gte=settings.NOTIFICATION_MAX_ATTEMPTS
    ).update(
        status=NotificationDelivery.Status.FAILED,
        next_attempt_at=None,
        failure_reason="Traitement interrompu apres la derniere tentative.",
    )
    requeued = stale.filter(
        attempt_count__lt=settings.NOTIFICATION_MAX_ATTEMPTS
    ).update(
        status=NotificationDelivery.Status.QUEUED,
        next_attempt_at=now,
        failure_reason="Traitement interrompu puis remis en file.",
    )
    return exhausted + requeued


def _eligible_deliveries(*, channels, now):
    return NotificationDelivery.objects.filter(
        status=NotificationDelivery.Status.QUEUED,
        attempt_count__lt=settings.NOTIFICATION_MAX_ATTEMPTS,
        channel__in=channels,
    ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))


def _claim_next_delivery(*, channels, now) -> NotificationDelivery | None:
    while True:
        delivery_id = (
            _eligible_deliveries(channels=channels, now=now)
            .order_by("created_at")
            .values_list("id", flat=True)
            .first()
        )
        if delivery_id is None:
            return None
        claimed = NotificationDelivery.objects.filter(
            id=delivery_id,
            status=NotificationDelivery.Status.QUEUED,
        ).update(
            status=NotificationDelivery.Status.PROCESSING,
            attempt_count=F("attempt_count") + 1,
            last_attempt_at=now,
            next_attempt_at=None,
        )
        if claimed:
            return NotificationDelivery.objects.select_related(
                "access_link__document",
                "otp_challenge",
                "account_challenge",
                "rent_charge__lease__tenant",
                "rent_charge__lease__property",
                "tenant_invitation__tenant__property",
                "tenant_invitation__invited_by",
            ).get(id=delivery_id)


def _mark_sent(
    delivery: NotificationDelivery, receipt: DeliveryReceipt, *, now
) -> None:
    NotificationDelivery.objects.filter(
        id=delivery.id, status=NotificationDelivery.Status.PROCESSING
    ).update(
        status=NotificationDelivery.Status.SENT,
        sent_at=now,
        next_attempt_at=None,
        provider_reference=receipt.provider_reference[:160],
        failure_reason="",
    )


def _mark_failed(
    delivery: NotificationDelivery, error: Exception, *, now, permanent: bool
) -> str:
    reason = f"{error.__class__.__name__}: {error}"[:500]
    if permanent or delivery.attempt_count >= settings.NOTIFICATION_MAX_ATTEMPTS:
        NotificationDelivery.objects.filter(id=delivery.id).update(
            status=NotificationDelivery.Status.FAILED,
            next_attempt_at=None,
            failure_reason=reason,
        )
        return NotificationDelivery.Status.FAILED

    delay = settings.NOTIFICATION_RETRY_SECONDS * (2 ** (delivery.attempt_count - 1))
    NotificationDelivery.objects.filter(id=delivery.id).update(
        status=NotificationDelivery.Status.QUEUED,
        next_attempt_at=now + timedelta(seconds=delay),
        failure_reason=reason,
    )
    return NotificationDelivery.Status.QUEUED


def process_notification_batch(
    *, adapters: Mapping[str, NotificationAdapter], limit: int = 50, now=None
) -> ProcessingSummary:
    if limit < 1:
        raise ValueError("La limite doit etre superieure a zero.")
    now = now or timezone.now()
    recovered = recover_stale_deliveries(now=now)
    configured_channels = tuple(adapters.keys())
    claimed = sent = requeued = failed = 0

    if configured_channels:
        for _ in range(limit):
            delivery = _claim_next_delivery(channels=configured_channels, now=now)
            if delivery is None:
                break
            claimed += 1
            try:
                message = build_notification_message(delivery, now=now)
                receipt = adapters[delivery.channel].send(message)
                if receipt is None:
                    receipt = DeliveryReceipt()
            except PermanentNotificationError as exc:
                _mark_failed(delivery, exc, now=now, permanent=True)
                failed += 1
            except Exception as exc:  # L'adaptateur definit ses erreurs techniques.
                status = _mark_failed(delivery, exc, now=now, permanent=False)
                if status == NotificationDelivery.Status.FAILED:
                    failed += 1
                else:
                    requeued += 1
            else:
                _mark_sent(delivery, receipt, now=now)
                sent += 1

    unavailable = (
        NotificationDelivery.objects.filter(
            status=NotificationDelivery.Status.QUEUED,
            attempt_count__lt=settings.NOTIFICATION_MAX_ATTEMPTS,
        )
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .exclude(channel__in=configured_channels)
        .count()
    )
    return ProcessingSummary(
        claimed=claimed,
        sent=sent,
        requeued=requeued,
        failed=failed,
        unavailable=unavailable,
        recovered=recovered,
    )
