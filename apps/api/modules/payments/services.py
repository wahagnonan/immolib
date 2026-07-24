from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from uuid import NAMESPACE_URL, uuid5

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.accounts.models import User
from modules.billing.models import RentCharge
from modules.billing.services import temporal_status
from modules.leases.models import Tenant
from modules.leases.selectors import manageable_properties_for
from modules.properties.models import Ownership

from .models import (
    Payment,
    PaymentAllocation,
    PaymentEvent,
    PaymentProviderEvent,
    SecurityDepositMovement,
)


@dataclass(frozen=True)
class RecordOfflinePaymentData:
    amount: Decimal
    method: str
    idempotency_key: UUID
    received_at: datetime
    external_reference: str = ""
    note: str = ""


@dataclass(frozen=True)
class PaymentAllocationData:
    charge: RentCharge
    amount: Decimal


@dataclass(frozen=True)
class RecordedPaymentResult:
    payment: Payment
    created: bool


@dataclass(frozen=True)
class MobileMoneyPaymentData:
    provider: str
    external_event_id: str
    event_type: str
    event_status: str
    transaction_reference: str
    rent_charge_id: UUID
    amount: Decimal
    currency: str
    paid_at: datetime
    payload_digest: str


@dataclass(frozen=True)
class MobileMoneyPaymentResult:
    provider_event: PaymentProviderEvent
    payment: Payment | None
    created: bool


@dataclass(frozen=True)
class SettleSecurityDepositData:
    movement_type: str
    amount: Decimal
    idempotency_key: UUID
    occurred_at: datetime
    reason: str = ""
    agreement_confirmed: bool = False
    agreement_reference: str = ""
    target_rent_charge: RentCharge | None = None


@dataclass(frozen=True)
class SecurityDepositSettlementResult:
    movement: SecurityDepositMovement
    created: bool


def _assert_can_manage_charge(*, actor: User, charge: RentCharge) -> None:
    property_id = charge.lease.property_id
    if not manageable_properties_for(actor).filter(id=property_id).exists():
        raise PermissionDenied("Tu ne peux pas enregistrer un paiement pour cette maison.")


def _existing_payment_matches(
    *,
    payment: Payment,
    allocations: tuple[PaymentAllocationData, ...],
    data: RecordOfflinePaymentData,
) -> bool:
    existing_allocations = {
        item.rent_charge_id: item.amount for item in payment.allocations.all()
    }
    expected_allocations = {
        item.charge.id: item.amount for item in allocations
    }
    return bool(
        existing_allocations == expected_allocations
        and payment.amount == data.amount
        and payment.method == data.method
        and payment.received_at == data.received_at
    )


def _active_allocated_total(charge: RentCharge) -> Decimal:
    result = PaymentAllocation.objects.filter(rent_charge=charge).exclude(
        payment__status=Payment.Status.CANCELLED
    ).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0")


def _recalculate_charge(charge: RentCharge) -> RentCharge:
    charge = RentCharge.objects.select_for_update().get(id=charge.id)
    amount_paid = _active_allocated_total(charge)
    if amount_paid > charge.amount_due:
        raise ValidationError("Les paiements depassent le montant de l'echeance.")

    charge.amount_paid = amount_paid
    if amount_paid == 0:
        charge.status = temporal_status(
            due_date=charge.due_date, today=timezone.localdate()
        )
    elif amount_paid < charge.amount_due:
        charge.status = RentCharge.Status.PARTIALLY_PAID
    else:
        charge.status = RentCharge.Status.PAID
    charge.save(update_fields=["amount_paid", "status", "updated_at"])
    return charge


@transaction.atomic
def record_offline_payment(
    *, actor: User, charge: RentCharge, data: RecordOfflinePaymentData
) -> RecordedPaymentResult:
    """Compatibilité : enregistre un paiement affecté à une seule obligation."""

    return record_allocated_offline_payment(
        actor=actor,
        allocations=(PaymentAllocationData(charge=charge, amount=data.amount),),
        data=data,
    )


@transaction.atomic
def record_allocated_offline_payment(
    *,
    actor: User,
    allocations: tuple[PaymentAllocationData, ...],
    data: RecordOfflinePaymentData,
) -> RecordedPaymentResult:
    """Enregistre un paiement réparti entre une caution et/ou plusieurs loyers."""

    existing = Payment.objects.filter(
        recorded_by=actor, idempotency_key=data.idempotency_key
    ).prefetch_related("allocations").first()
    if existing:
        if not _existing_payment_matches(
            payment=existing, allocations=allocations, data=data
        ):
            raise ValidationError(
                "Cette cle d'idempotence a deja servi avec des donnees differentes."
            )
        if existing.status != Payment.Status.CANCELLED:
            from modules.documents.services import issue_documents_for_payment

            issue_documents_for_payment(payment=existing)
        return RecordedPaymentResult(payment=existing, created=False)

    if not allocations:
        raise ValidationError("Le paiement doit être affecté à au moins une obligation.")
    if len({item.charge.id for item in allocations}) != len(allocations):
        raise ValidationError("Une obligation ne peut apparaître qu'une seule fois.")

    locked_charges = {
        charge.id: charge
        for charge in RentCharge.objects.select_for_update()
        .select_related("lease__property", "lease__tenant")
        .filter(id__in=[item.charge.id for item in allocations])
        .order_by("id")
    }
    if len(locked_charges) != len(allocations):
        raise ValidationError("Une obligation de paiement est introuvable.")
    resolved_allocations = tuple(
        PaymentAllocationData(
            charge=locked_charges[item.charge.id],
            amount=item.amount,
        )
        for item in allocations
    )
    lease_ids = {item.charge.lease_id for item in resolved_allocations}
    if len(lease_ids) != 1:
        raise ValidationError(
            "Un paiement ne peut pas être réparti entre plusieurs baux."
        )
    currencies = {item.charge.currency for item in resolved_allocations}
    if len(currencies) != 1:
        raise ValidationError("Toutes les obligations doivent utiliser la même devise.")
    for item in resolved_allocations:
        _assert_can_manage_charge(actor=actor, charge=item.charge)

    if data.method not in (
        Payment.Method.CASH,
        Payment.Method.BANK_TRANSFER,
        Payment.Method.EXTERNAL_MOBILE_MONEY,
        Payment.Method.OTHER,
    ):
        raise ValidationError("Moyen de paiement hors ImmoLib invalide.")
    if data.amount <= 0:
        raise ValidationError("Le montant doit etre strictement positif.")
    allocation_total = sum(
        (item.amount for item in resolved_allocations), start=Decimal("0")
    )
    if allocation_total != data.amount:
        raise ValidationError(
            "Le montant du paiement doit être égal à la somme des affectations."
        )
    for item in resolved_allocations:
        if item.amount <= 0:
            raise ValidationError(
                "Chaque montant affecté doit être strictement positif."
            )
        if item.charge.status == RentCharge.Status.CANCELLED:
            raise ValidationError(
                "Une obligation annulée ne peut pas recevoir de paiement."
            )
        outstanding = item.charge.amount_due - _active_allocated_total(item.charge)
        if item.amount > outstanding:
            raise ValidationError(
                "Le montant affecte a "
                f"{item.charge.obligation_label} depasse le solde restant de "
                f"{outstanding} {item.charge.currency}."
            )

    payment = Payment(
        amount=data.amount,
        currency=next(iter(currencies)),
        method=data.method,
        received_at=data.received_at,
        external_reference=data.external_reference.strip(),
        note=data.note.strip(),
        idempotency_key=data.idempotency_key,
        recorded_by=actor,
    )
    payment.full_clean()
    payment.save()

    for item in resolved_allocations:
        allocation = PaymentAllocation(
            payment=payment,
            rent_charge=item.charge,
            amount=item.amount,
        )
        allocation.full_clean()
        allocation.save()
    PaymentEvent.objects.create(
        payment=payment,
        event_type=PaymentEvent.Type.RECORDED,
        actor_user=actor,
        metadata={
            "allocations": [
                {
                    "obligation_id": str(item.charge.id),
                    "type": item.charge.charge_type,
                    "amount": str(item.amount),
                }
                for item in resolved_allocations
            ]
        },
    )
    for item in resolved_allocations:
        _recalculate_charge(item.charge)
    from modules.documents.services import issue_documents_for_payment

    issue_documents_for_payment(payment=payment)
    return RecordedPaymentResult(payment=payment, created=True)


def _assert_payment_belongs_to_tenant(*, payment: Payment, tenant: Tenant) -> None:
    belongs = payment.allocations.filter(rent_charge__lease__tenant=tenant).exists()
    if not belongs:
        raise PermissionDenied("Ce paiement n'appartient pas a ce locataire.")


@transaction.atomic
def confirm_payment_by_tenant(*, tenant: Tenant, payment: Payment) -> Payment:
    payment = Payment.objects.select_for_update().get(id=payment.id)
    _assert_payment_belongs_to_tenant(payment=payment, tenant=tenant)
    if payment.status == Payment.Status.CANCELLED:
        raise ValidationError("Un paiement annule ne peut pas etre confirme.")
    if payment.status == Payment.Status.CONFIRMED_BY_PROVIDER:
        return payment
    if payment.status == Payment.Status.CONFIRMED_BY_TENANT:
        return payment

    payment.status = Payment.Status.CONFIRMED_BY_TENANT
    payment.save(update_fields=["status", "updated_at"])
    PaymentEvent.objects.create(
        payment=payment,
        event_type=PaymentEvent.Type.TENANT_CONFIRMED,
        actor_tenant=tenant,
    )
    return payment


@transaction.atomic
def dispute_payment_by_tenant(
    *, tenant: Tenant, payment: Payment, reason: str
) -> Payment:
    payment = Payment.objects.select_for_update().get(id=payment.id)
    _assert_payment_belongs_to_tenant(payment=payment, tenant=tenant)
    if payment.status == Payment.Status.CANCELLED:
        raise ValidationError("Un paiement annule ne peut pas etre conteste.")
    if payment.status == Payment.Status.CONFIRMED_BY_PROVIDER:
        raise ValidationError(
            "Ce paiement a été confirmé par le prestataire Mobile Money."
        )
    if not reason.strip():
        raise ValidationError("Le motif de contestation est obligatoire.")
    if payment.status == Payment.Status.DISPUTED_BY_TENANT:
        return payment

    payment.status = Payment.Status.DISPUTED_BY_TENANT
    payment.save(update_fields=["status", "updated_at"])
    PaymentEvent.objects.create(
        payment=payment,
        event_type=PaymentEvent.Type.TENANT_DISPUTED,
        actor_tenant=tenant,
        reason=reason.strip(),
    )
    return payment


@transaction.atomic
def cancel_payment(*, actor: User, payment: Payment, reason: str) -> Payment:
    payment = Payment.objects.select_for_update().prefetch_related(
        "allocations__rent_charge__lease__property"
    ).get(id=payment.id)
    if payment.status == Payment.Status.CANCELLED:
        return payment
    if not payment.is_cash_movement:
        raise ValidationError(
            "Une affectation de caution ne s'annule pas comme un encaissement. "
            "Consultez le journal de caution."
        )
    if payment.status == Payment.Status.CONFIRMED_BY_PROVIDER:
        raise ValidationError(
            "Un paiement confirmé par le prestataire ne peut pas être annulé manuellement."
        )
    if not reason.strip():
        raise ValidationError("Le motif d'annulation est obligatoire.")

    allocations = list(payment.allocations.all())
    for allocation in allocations:
        _assert_can_manage_charge(actor=actor, charge=allocation.rent_charge)
        charge = RentCharge.objects.select_for_update().get(
            id=allocation.rent_charge_id
        )
        if (
            charge.charge_type == RentCharge.Type.SECURITY_DEPOSIT
            and charge.amount_paid - allocation.amount < charge.amount_released
        ):
            raise ValidationError(
                "Ce versement de caution ne peut plus être annulé car une partie "
                "de la caution a déjà été libérée."
            )

    payment.status = Payment.Status.CANCELLED
    payment.save(update_fields=["status", "updated_at"])
    PaymentEvent.objects.create(
        payment=payment,
        event_type=PaymentEvent.Type.CANCELLED,
        actor_user=actor,
        reason=reason.strip(),
    )
    for allocation in allocations:
        _recalculate_charge(allocation.rent_charge)
    from modules.documents.services import void_documents_after_cancellation

    void_documents_after_cancellation(payment=payment)
    return payment


def _existing_deposit_movement_matches(
    *,
    movement: SecurityDepositMovement,
    deposit: RentCharge,
    data: SettleSecurityDepositData,
) -> bool:
    target_id = data.target_rent_charge.id if data.target_rent_charge else None
    return bool(
        movement.deposit_obligation_id == deposit.id
        and movement.movement_type == data.movement_type
        and movement.amount == data.amount
        and movement.target_rent_charge_id == target_id
        and movement.reason == data.reason.strip()
        and movement.agreement_reference == data.agreement_reference.strip()
    )


@transaction.atomic
def settle_security_deposit(
    *,
    actor: User,
    deposit: RentCharge,
    data: SettleSecurityDepositData,
) -> SecurityDepositSettlementResult:
    """Trace une libération de caution sans créer de portefeuille ImmoLib."""

    existing = (
        SecurityDepositMovement.objects.select_related(
            "deposit_obligation",
            "target_rent_charge",
            "resulting_payment",
        )
        .filter(created_by=actor, idempotency_key=data.idempotency_key)
        .first()
    )
    if existing:
        if not _existing_deposit_movement_matches(
            movement=existing,
            deposit=deposit,
            data=data,
        ):
            raise ValidationError(
                "Cette clé d'idempotence a déjà servi avec des données différentes."
            )
        from modules.documents.services import (
            issue_security_deposit_settlement_document,
        )

        issue_security_deposit_settlement_document(movement=existing)
        return SecurityDepositSettlementResult(movement=existing, created=False)

    deposit = (
        RentCharge.objects.select_for_update()
        .select_related("lease__property", "lease__tenant")
        .get(id=deposit.id)
    )
    existing = (
        SecurityDepositMovement.objects.select_related(
            "deposit_obligation",
            "target_rent_charge",
            "resulting_payment",
        )
        .filter(created_by=actor, idempotency_key=data.idempotency_key)
        .first()
    )
    if existing:
        if not _existing_deposit_movement_matches(
            movement=existing,
            deposit=deposit,
            data=data,
        ):
            raise ValidationError(
                "Cette clé d'idempotence a déjà servi avec des données différentes."
            )
        from modules.documents.services import (
            issue_security_deposit_settlement_document,
        )

        issue_security_deposit_settlement_document(movement=existing)
        return SecurityDepositSettlementResult(movement=existing, created=False)
    _assert_can_manage_charge(actor=actor, charge=deposit)
    if deposit.charge_type != RentCharge.Type.SECURITY_DEPOSIT:
        raise ValidationError("Cette obligation n'est pas une caution.")
    if data.movement_type not in SecurityDepositMovement.Type.values:
        raise ValidationError("Type de mouvement de caution invalide.")
    if data.amount <= 0:
        raise ValidationError("Le montant doit être strictement positif.")
    if data.amount > deposit.held_balance:
        raise ValidationError(
            "Le montant dépasse la caution encore détenue de "
            f"{deposit.held_balance} {deposit.currency}."
        )

    reason = data.reason.strip()
    agreement_reference = data.agreement_reference.strip()
    target = None
    resulting_payment = None
    if data.movement_type == SecurityDepositMovement.Type.RETENTION and not reason:
        raise ValidationError("Le motif de la retenue est obligatoire.")
    if data.movement_type == SecurityDepositMovement.Type.APPLY_TO_RENT:
        if not data.agreement_confirmed or not agreement_reference:
            raise ValidationError(
                "L'accord du locataire et sa référence sont obligatoires."
            )
        if data.target_rent_charge is None:
            raise ValidationError("Sélectionnez le loyer à solder.")
        target = (
            RentCharge.objects.select_for_update()
            .select_related("lease__property", "lease__tenant")
            .get(id=data.target_rent_charge.id)
        )
        if (
            target.charge_type != RentCharge.Type.RENT
            or target.lease_id != deposit.lease_id
        ):
            raise ValidationError(
                "La caution peut seulement être affectée à un loyer du même bail."
            )
        if target.status == RentCharge.Status.CANCELLED:
            raise ValidationError("Un loyer annulé ne peut pas recevoir la caution.")
        outstanding = target.amount_due - _active_allocated_total(target)
        if data.amount > outstanding:
            raise ValidationError(
                f"Le montant dépasse le solde du loyer de {outstanding} "
                f"{target.currency}."
            )
        payment_key = uuid5(
            NAMESPACE_URL,
            f"immolib:deposit-application:{actor.id}:{data.idempotency_key}",
        )
        resulting_payment = Payment.objects.create(
            amount=data.amount,
            currency=target.currency,
            method=Payment.Method.SECURITY_DEPOSIT_APPLICATION,
            status=Payment.Status.CONFIRMED_BY_TENANT,
            received_at=data.occurred_at,
            external_reference=agreement_reference,
            note=reason or "Affectation de la caution au loyer",
            is_cash_movement=False,
            idempotency_key=payment_key,
            recorded_by=actor,
        )
        PaymentAllocation.objects.create(
            payment=resulting_payment,
            rent_charge=target,
            amount=data.amount,
        )
        PaymentEvent.objects.create(
            payment=resulting_payment,
            event_type=PaymentEvent.Type.TENANT_CONFIRMED,
            actor_user=actor,
            metadata={
                "source": "SECURITY_DEPOSIT",
                "deposit_obligation_id": str(deposit.id),
                "agreement_reference": agreement_reference,
            },
        )
        _recalculate_charge(target)

    movement = SecurityDepositMovement.objects.create(
        deposit_obligation=deposit,
        movement_type=data.movement_type,
        amount=data.amount,
        reason=reason,
        agreement_confirmed=data.agreement_confirmed,
        agreement_reference=agreement_reference,
        target_rent_charge=target,
        resulting_payment=resulting_payment,
        idempotency_key=data.idempotency_key,
        created_by=actor,
        occurred_at=data.occurred_at,
    )
    deposit.amount_released += data.amount
    deposit.save(update_fields=["amount_released", "updated_at"])

    from modules.documents.services import (
        issue_documents_for_payment,
        issue_security_deposit_settlement_document,
    )

    if resulting_payment:
        issue_documents_for_payment(payment=resulting_payment)
    issue_security_deposit_settlement_document(movement=movement)
    return SecurityDepositSettlementResult(movement=movement, created=True)


def record_mobile_money_provider_event(
    *, data: MobileMoneyPaymentData
) -> MobileMoneyPaymentResult:
    provider = data.provider.strip().upper()
    existing = PaymentProviderEvent.objects.filter(
        provider=provider,
        external_event_id=data.external_event_id,
    ).select_related("payment").first()
    if existing:
        if existing.payload_digest != data.payload_digest:
            raise ValidationError(
                "Cet identifiant d'événement a déjà été utilisé avec un autre contenu."
            )
        return MobileMoneyPaymentResult(
            provider_event=existing,
            payment=existing.payment,
            created=False,
        )

    provider_event = PaymentProviderEvent.objects.create(
        provider=provider,
        external_event_id=data.external_event_id,
        event_type=data.event_type,
        transaction_reference=data.transaction_reference,
        rent_charge_reference=str(data.rent_charge_id),
        amount=data.amount,
        currency=data.currency.upper(),
        paid_at=data.paid_at,
        payload_digest=data.payload_digest,
    )
    if data.event_status != "SUCCEEDED":
        provider_event.status = PaymentProviderEvent.Status.IGNORED
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["status", "processed_at"])
        return MobileMoneyPaymentResult(
            provider_event=provider_event,
            payment=None,
            created=True,
        )

    try:
        with transaction.atomic():
            charge = (
                RentCharge.objects.select_for_update()
                .select_related("lease__property", "lease__tenant")
                .get(id=data.rent_charge_id)
            )
            if charge.status == RentCharge.Status.CANCELLED:
                raise ValidationError(
                    "Une échéance annulée ne peut pas recevoir de paiement."
                )
            if data.amount <= 0:
                raise ValidationError(
                    "Le montant Mobile Money doit être strictement positif."
                )
            if data.currency.upper() != charge.currency:
                raise ValidationError("La devise ne correspond pas à l'échéance.")
            outstanding = charge.amount_due - _active_allocated_total(charge)
            if data.amount > outstanding:
                raise ValidationError(
                    f"Le montant dépasse le solde restant de {outstanding} {charge.currency}."
                )
            owner = charge.lease.property.ownerships.select_related("user").get(
                role=Ownership.Role.PRIMARY
            ).user
            idempotency_key = uuid5(
                NAMESPACE_URL,
                f"immolib:{provider}:{data.external_event_id}",
            )
            payment = Payment(
                amount=data.amount,
                currency=charge.currency,
                method=Payment.Method.MOBILE_MONEY,
                status=Payment.Status.CONFIRMED_BY_PROVIDER,
                received_at=data.paid_at,
                external_reference=data.transaction_reference.strip(),
                note=f"Confirmation automatique {provider}",
                idempotency_key=idempotency_key,
                recorded_by=owner,
            )
            payment.full_clean()
            payment.save()
            allocation = PaymentAllocation(
                payment=payment,
                rent_charge=charge,
                amount=data.amount,
            )
            allocation.full_clean()
            allocation.save()
            PaymentEvent.objects.create(
                payment=payment,
                event_type=PaymentEvent.Type.PROVIDER_CONFIRMED,
                metadata={
                    "provider": provider,
                    "external_event_id": data.external_event_id,
                    "transaction_reference": data.transaction_reference,
                },
            )
            _recalculate_charge(charge)
            from modules.documents.services import issue_documents_for_payment

            issue_documents_for_payment(payment=payment)
            provider_event.payment = payment
            provider_event.status = PaymentProviderEvent.Status.PROCESSED
            provider_event.processed_at = timezone.now()
            provider_event.save(
                update_fields=[
                    "payment",
                    "status",
                    "processed_at",
                ]
            )
    except (RentCharge.DoesNotExist, ValidationError) as exc:
        message = (
            "Échéance inconnue."
            if isinstance(exc, RentCharge.DoesNotExist)
            else "; ".join(exc.messages)
        )
        provider_event.status = PaymentProviderEvent.Status.FAILED
        provider_event.failure_reason = message
        provider_event.processed_at = timezone.now()
        provider_event.save(
            update_fields=[
                "status",
                "failure_reason",
                "processed_at",
            ]
        )
        raise ValidationError(message) from exc

    return MobileMoneyPaymentResult(
        provider_event=provider_event,
        payment=payment,
        created=True,
    )
