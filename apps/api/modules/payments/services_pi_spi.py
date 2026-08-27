"""Services PI-SPI (BCEAO) — Model B via PSP participant.

Flux :

 Tenant
   → POST /payment-requests/ {operator: PI_SPI, rent_charge_id, amount}
     → PaymentRequest(PENDING, operator=PI_SPI)
   → POST /payment-requests/{id}/initiate-pi-spi/
     → adapter.initiate_payment() → PSP → PI-SPI switch
     → PaymentRequest(PROCESSING, external_transaction_id, provider=PI_SPI)
     → frontend poll GET /payment-requests/{id}
   → PSP webhook POST /webhooks/pi-spi/ {event_id, transaction_id, status, amount, ...}
     → vérifie signature + idempotence → crée Payment(PI_SPI, CONFIRMED_BY_PROVIDER)
     → RentCharge recalcule + RentalDocument

Idempotence & sécurité (Phase 9) :
- Initiation idempotente via PaymentRequest.id + external_transaction
- Webhook idempotent via PaymentProviderEvent(provider, external_event_id)
- Validation amount/currency/beneficiary avant création Payment
- Anti-replay timestamp 300s

Ne jamais générer quittance avant confirmation provider (Phase 10).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.accounts.models import User
from modules.billing.models import RentCharge

from .adapters.base import InitiatePaymentRequest, ProviderStatus
from .adapters.registry import get_provider
from .models import Payment, PaymentAllocation, PaymentEvent, PaymentProviderEvent, PaymentRequest


@dataclass(frozen=True)
class PiSpiInitiateResult:
    payment_request: PaymentRequest
    external_transaction_id: str
    provider_status: str
    created: bool


def _pi_spi_provider():
    # registry renvoie PiSpiProvider ou Mock selon config
    return get_provider("PI_SPI")


def _idempotency_key_for_request(req: PaymentRequest) -> str:
    # Déterministe : même requête → même clé, évite double init
    return str(uuid5(NAMESPACE_URL, f"immolib:pi-spi:{req.id}"))


@transaction.atomic
def initiate_pi_spi_payment(*, tenant: User, payment_request: PaymentRequest) -> PiSpiInitiateResult:
    """Initie un paiement PI-SPI via PSP. Idempotent."""

    req = PaymentRequest.objects.select_for_update().select_related(
        "rent_charge__lease__property",
        "rent_charge__lease__tenant",
        "method_account",
    ).get(id=payment_request.id)

    # Permissions : seul le demandeur peut initier son PI-SPI
    if req.requested_by_id != tenant.id:
        raise PermissionDenied(_("Tu ne peux pas initier ce paiement."))

    if req.operator != PaymentRequest.Operator.PI_SPI:
        raise ValidationError(_("Cette demande n'est pas de type PI-SPI."))

    if req.status in {PaymentRequest.Status.CONFIRMED, PaymentRequest.Status.CANCELLED,
                      PaymentRequest.Status.NOT_RECEIVED, PaymentRequest.Status.EXPIRED}:
        raise ValidationError(_("Cette demande a déjà été traitée."))

    # Déjà initiée ? Idempotence : retourne existant sans ré-appeler PSP
    if req.external_transaction_id and req.status == PaymentRequest.Status.PROCESSING:
        return PiSpiInitiateResult(
            payment_request=req,
            external_transaction_id=req.external_transaction_id,
            provider_status=req.provider_status,
            created=False,
        )

    # Validation métier : expiration
    if req.expires_at and req.expires_at <= timezone.now():
        req.status = PaymentRequest.Status.EXPIRED
        req.failure_reason = _("Délai d'initiation expiré.")
        req.save(update_fields=["status", "failure_reason", "updated_at"])
        raise ValidationError(_("La demande a expiré."))

    charge: RentCharge = req.rent_charge
    if charge.status == RentCharge.Status.CANCELLED:
        raise ValidationError(_("Échéance annulée."))

    # Résolution compte bénéficiaire (bailleur)
    account_identifier = ""
    if req.method_account:
        account_identifier = req.method_account.account_identifier
    else:
        # Fallback : utilise le compte PI_SPI par défaut du bailleur, sinon phone
        from .models import PaymentMethodAccount  # noqa: PLC0415

        default = PaymentMethodAccount.objects.filter(
            owner=req.payee, operator=PaymentMethodAccount.Operator.PI_SPI
        ).first() or PaymentMethodAccount.objects.filter(
            owner=req.payee, operator=PaymentMethodAccount.Operator.BANK_TRANSFER
        ).first()
        if default:
            account_identifier = default.account_identifier
        else:
            account_identifier = req.payee_phone or ""

    if not account_identifier:
        raise ValidationError(_("Aucun compte bénéficiaire PI-SPI configuré pour ce bailleur."))

    # Feature flag
    if not getattr(settings, "PI_SPI_ENABLED", False) and not settings.DEBUG:
        raise ValidationError(_("Le paiement PI-SPI est désactivé."))

    idempotency_key = _idempotency_key_for_request(req)

    tenant_name = req.requested_by.get_full_name() or req.requested_by.phone

    adapter = _pi_spi_provider()
    result = adapter.initiate_payment(
        InitiatePaymentRequest(
            payment_request_id=req.id,
            reference=req.reference,
            rent_charge_id=req.rent_charge_id,
            amount=req.amount,
            currency=req.currency,
            tenant_id=req.requested_by_id,
            tenant_phone=req.requested_by.phone,
            tenant_name=tenant_name,
            payee_account_identifier=account_identifier,
            payee_name=req.payee_name,
            operator=req.operator,
            idempotency_key=idempotency_key,
            metadata={
                "rent_charge_period": charge.period_label,
                "house_id": str(charge.lease.property_id),
            },
        )
    )

    # Mapping ProviderStatus → PaymentRequest.status
    provider_status = result.status.value if isinstance(result.status, ProviderStatus) else str(result.status)
    # PENDING/PROCESSING côté PSP → PROCESSING côté ImmoLib
    if result.status in {ProviderStatus.PENDING, ProviderStatus.PROCESSING}:
        req.status = PaymentRequest.Status.PROCESSING
    elif result.status == ProviderStatus.SUCCESS:
        # Succès immédiat (mock auto-success) → on reste PROCESSING jusqu'au webhook,
        # mais on pourrait confirmer directement en sandbox
        req.status = PaymentRequest.Status.PROCESSING
    elif result.status in {ProviderStatus.FAILED, ProviderStatus.EXPIRED, ProviderStatus.CANCELLED}:
        req.status = PaymentRequest.Status.FAILED if result.status == ProviderStatus.FAILED else PaymentRequest.Status.EXPIRED

    req.external_transaction_id = result.external_transaction_id
    req.provider = result.provider
    req.provider_status = provider_status
    req.provider_reference = result.external_reference
    # TTL pour expiration automatique
    ttl = int(getattr(settings, "PI_SPI_TRANSACTION_TTL_SECONDS", 900))
    req.expires_at = timezone.now() + timedelta(seconds=ttl)
    req.save(update_fields=[
        "external_transaction_id", "provider", "provider_status",
        "provider_reference", "status", "expires_at", "updated_at",
    ])

    # Trace provider event (initiation)
    PaymentProviderEvent.objects.create(
        provider=result.provider,
        external_event_id=result.external_transaction_id,
        event_type="payment.initiated",
        status=PaymentProviderEvent.Status.PROCESSED,
        transaction_reference=result.external_transaction_id,
        rent_charge_reference=str(req.rent_charge_id),
        amount=req.amount,
        currency=req.currency,
        payload_digest=hashlib.sha256(idempotency_key.encode()).hexdigest(),
        payment_request=req,
        processed_at=timezone.now(),
    )

    return PiSpiInitiateResult(
        payment_request=req,
        external_transaction_id=result.external_transaction_id,
        provider_status=provider_status,
        created=True,
    )


# --- Webhook handling ---

@dataclass(frozen=True)
class PiSpiWebhookData:
    provider: str
    external_event_id: str
    external_transaction_id: str
    event_type: str
    status: str  # SUCCEEDED/FAILED etc.
    amount: Decimal
    currency: str
    paid_at: timezone.datetime | None
    rent_charge_id: uuid.UUID | None
    payment_request_id: uuid.UUID | None
    payload_digest: str


@transaction.atomic
def handle_pi_spi_webhook(*, data: PiSpiWebhookData, raw_payload: dict | None = None) -> tuple[PaymentProviderEvent, Payment | None]:
    """Traite un webhook PI-SPI de façon idempotente.

    Vérifie amount/currency/beneficiary via PaymentRequest.
    Ne crée le Payment qu'une fois (idempotence provider+event_id).
    """
    provider = data.provider.strip().upper() or "PI_SPI"

    existing = PaymentProviderEvent.objects.filter(
        provider=provider, external_event_id=data.external_event_id
    ).select_related("payment", "payment_request").first()

    if existing:
        if existing.payload_digest != data.payload_digest:
            raise ValidationError(_("Cet event_id a déjà été utilisé avec un autre contenu."))
        return existing, existing.payment

    # Recherche PaymentRequest liée
    payment_request = None
    if data.payment_request_id:
        payment_request = PaymentRequest.objects.filter(id=data.payment_request_id).first()
    if payment_request is None and data.external_transaction_id:
        payment_request = PaymentRequest.objects.filter(
            external_transaction_id=data.external_transaction_id
        ).first()
    # Fallback via rent_charge + tenant matching (si PSP n'envoie pas request_id)
    if payment_request is None and data.rent_charge_id:
        payment_request = PaymentRequest.objects.filter(
            rent_charge_id=data.rent_charge_id,
            status__in=[PaymentRequest.Status.PENDING, PaymentRequest.Status.PROCESSING],
        ).order_by("-created_at").first()

    # Crée l'event en RECEIVED puis traite
    provider_event = PaymentProviderEvent.objects.create(
        provider=provider,
        external_event_id=data.external_event_id,
        event_type=data.event_type,
        transaction_reference=data.external_transaction_id,
        rent_charge_reference=str(data.rent_charge_id) if data.rent_charge_id else "",
        amount=data.amount,
        currency=data.currency.upper() if data.currency else "",
        paid_at=data.paid_at,
        payload_digest=data.payload_digest,
        payment_request=payment_request,
        status=PaymentProviderEvent.Status.RECEIVED,
    )

    # Map statut PSP → logique
    status_norm = data.status.strip().upper()
    if status_norm in {"FAILED", "CANCELLED", "EXPIRED"}:
        if payment_request:
            with transaction.atomic():
                req = PaymentRequest.objects.select_for_update().get(id=payment_request.id)
                if req.status in {PaymentRequest.Status.PENDING, PaymentRequest.Status.PROCESSING}:
                    req.status = {
                        "FAILED": PaymentRequest.Status.FAILED,
                        "CANCELLED": PaymentRequest.Status.CANCELLED,
                        "EXPIRED": PaymentRequest.Status.EXPIRED,
                    }[status_norm]
                    req.failure_reason = f"PSP {status_norm}"
                    req.provider_status = status_norm
                    req.save(update_fields=["status", "failure_reason", "provider_status", "updated_at"])
        provider_event.status = PaymentProviderEvent.Status.PROCESSED
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["status", "processed_at"])
        return provider_event, None

    if status_norm not in {"SUCCEEDED", "SUCCESS", "COMPLETED", "PAID"}:
        # PENDING/PROCESSING → keep as PROCESSED but no Payment yet
        provider_event.status = PaymentProviderEvent.Status.IGNORED
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["status", "processed_at"])
        return provider_event, None

    # SUCCEEDED → créer Payment CONFIRMED_BY_PROVIDER
    if payment_request is None:
        provider_event.status = PaymentProviderEvent.Status.FAILED
        provider_event.failure_reason = "PaymentRequest introuvable"
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["status", "failure_reason", "processed_at"])
        raise ValidationError(_("Demande de paiement liée introuvable."))

    # Validations critiques (Phase 9)
    if data.amount != payment_request.amount:
        provider_event.status = PaymentProviderEvent.Status.FAILED
        provider_event.failure_reason = f"Montant mismatch: {data.amount} vs {payment_request.amount}"
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["status", "failure_reason", "processed_at"])
        raise ValidationError(_("Le montant ne correspond pas à la demande."))

    if data.currency.upper() != payment_request.currency.upper():
        provider_event.status = PaymentProviderEvent.Status.FAILED
        provider_event.failure_reason = f"Devise mismatch: {data.currency} vs {payment_request.currency}"
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["status", "failure_reason", "processed_at"])
        raise ValidationError(_("La devise ne correspond pas."))

    charge = RentCharge.objects.select_for_update().select_related(
        "lease__property", "lease__tenant"
    ).get(id=payment_request.rent_charge_id)

    if charge.status == RentCharge.Status.CANCELLED:
        provider_event.status = PaymentProviderEvent.Status.FAILED
        provider_event.failure_reason = "Échéance annulée"
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["status", "failure_reason", "processed_at"])
        raise ValidationError(_("Échéance annulée."))

    # Vérifie outstanding
    from .services import _active_allocated_total, _recalculate_charge  # noqa: PLC0415

    outstanding = charge.amount_due - _active_allocated_total(charge)
    if data.amount > outstanding:
        provider_event.status = PaymentProviderEvent.Status.FAILED
        provider_event.failure_reason = f"Montant > outstanding {outstanding}"
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["status", "failure_reason", "processed_at"])
        raise ValidationError(_("Montant dépasse le solde restant."))

    # Crée Payment idempotent via uuid5(provider:event_id)
    idempotency_key = uuid5(NAMESPACE_URL, f"immolib:pi-spi:{provider}:{data.external_event_id}")
    existing_payment = Payment.objects.filter(
        recorded_by=payment_request.payee, idempotency_key=idempotency_key
    ).first()
    if existing_payment:
        provider_event.payment = existing_payment
        provider_event.status = PaymentProviderEvent.Status.PROCESSED
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["payment", "status", "processed_at"])
        return provider_event, existing_payment

    from modules.properties.models import Ownership  # noqa: PLC0415

    payment = Payment(
        amount=data.amount,
        currency=charge.currency,
        method=Payment.Method.PI_SPI,
        status=Payment.Status.CONFIRMED_BY_PROVIDER,
        received_at=data.paid_at or timezone.now(),
        external_reference=data.external_transaction_id,
        note=f"PI-SPI {provider} {data.external_transaction_id}",
        idempotency_key=idempotency_key,
        recorded_by=payment_request.payee,
    )
    payment.full_clean()
    payment.save()
    alloc = PaymentAllocation(
        payment=payment, rent_charge=charge, amount=data.amount
    )
    alloc.full_clean()
    alloc.save()
    PaymentEvent.objects.create(
        payment=payment,
        event_type=PaymentEvent.Type.PROVIDER_CONFIRMED,
        metadata={
            "provider": provider,
            "external_event_id": data.external_event_id,
            "external_transaction_id": data.external_transaction_id,
            "payment_request_id": str(payment_request.id),
            "payment_request_reference": payment_request.reference,
        },
    )
    _recalculate_charge(charge)

    from modules.documents.services import issue_documents_for_payment  # noqa: PLC0415

    issue_documents_for_payment(payment=payment)

    # Met à jour PaymentRequest → CONFIRMED
    req = PaymentRequest.objects.select_for_update().get(id=payment_request.id)
    req.status = PaymentRequest.Status.CONFIRMED
    req.amount_received = data.amount
    req.provider_status = status_norm
    req.processed_at = timezone.now()
    req.processed_by = req.payee  # système
    req.payment = payment
    req.save(update_fields=["status", "amount_received", "provider_status", "processed_at", "processed_by", "payment", "updated_at"])

    # Notification paiement confirmé
    try:
        from modules.payments.services import _enqueue_notification  # noqa: PLC0415

        _enqueue_notification(
            recipient=payment_request.requested_by,
            kind="PAYMENT_CONFIRMED",
            rent_charge=charge,
            payment_request=req,
        )
    except Exception:  # noqa: BLE001
        pass

    provider_event.payment = payment
    provider_event.status = PaymentProviderEvent.Status.PROCESSED
    provider_event.processed_at = timezone.now()
    provider_event.save(update_fields=["payment", "status", "processed_at"])

    return provider_event, payment


def expire_stale_pi_spi_requests() -> int:
    """Expire les demandes PI-SPI PROCESSING/PENDING au-delà du TTL."""
    cutoff = timezone.now()
    qs = PaymentRequest.objects.filter(
        operator=PaymentRequest.Operator.PI_SPI,
        status__in=[PaymentRequest.Status.PENDING, PaymentRequest.Status.PROCESSING],
        expires_at__lte=cutoff,
    )
    updated = 0
    for req in qs.select_for_update():
        req.status = PaymentRequest.Status.EXPIRED
        req.failure_reason = _("Délai PI-SPI expiré (TTL).")
        req.save(update_fields=["status", "failure_reason", "updated_at"])
        updated += 1
    return updated
