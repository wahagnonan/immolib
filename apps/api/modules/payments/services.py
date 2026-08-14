from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

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
    PaymentMethodAccount,
    PaymentProviderEvent,
    PaymentRequest,
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
        raise PermissionDenied(_("Tu ne peux pas enregistrer un paiement pour ce bien."))


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
        raise ValidationError(_("Les paiements depassent le montant de l'echeance."))

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
                _("Cette cle d'idempotence a deja servi avec des donnees differentes.")
            )
        if existing.status != Payment.Status.CANCELLED:
            from modules.documents.services import issue_documents_for_payment

            issue_documents_for_payment(payment=existing)
        return RecordedPaymentResult(payment=existing, created=False)

    if not allocations:
        raise ValidationError(_("Le paiement doit être affecté à au moins une obligation."))
    if len({item.charge.id for item in allocations}) != len(allocations):
        raise ValidationError(_("Une obligation ne peut apparaître qu'une seule fois."))

    locked_charges = {
        charge.id: charge
        for charge in RentCharge.objects.select_for_update()
        .select_related("lease__property", "lease__tenant")
        .filter(id__in=[item.charge.id for item in allocations])
        .order_by("id")
    }
    if len(locked_charges) != len(allocations):
        raise ValidationError(_("Une obligation de paiement est introuvable."))
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
            _("Un paiement ne peut pas être réparti entre plusieurs baux.")
        )
    currencies = {item.charge.currency for item in resolved_allocations}
    if len(currencies) != 1:
        raise ValidationError(_("Toutes les obligations doivent utiliser la même devise."))
    for item in resolved_allocations:
        _assert_can_manage_charge(actor=actor, charge=item.charge)

    if data.method not in (
        Payment.Method.CASH,
        Payment.Method.BANK_TRANSFER,
        Payment.Method.EXTERNAL_MOBILE_MONEY,
        Payment.Method.OTHER,
    ):
        raise ValidationError(_("Moyen de paiement hors ImmoLib invalide."))
    if data.amount <= 0:
        raise ValidationError(_("Le montant doit etre strictement positif."))
    allocation_total = sum(
        (item.amount for item in resolved_allocations), start=Decimal("0")
    )
    if allocation_total != data.amount:
        raise ValidationError(
            _("Le montant du paiement doit être égal à la somme des affectations.")
        )
    for item in resolved_allocations:
        if item.amount <= 0:
            raise ValidationError(
                _("Chaque montant affecté doit être strictement positif.")
            )
        if item.charge.status == RentCharge.Status.CANCELLED:
            raise ValidationError(
                _("Une obligation annulée ne peut pas recevoir de paiement.")
            )
        outstanding = item.charge.amount_due - _active_allocated_total(item.charge)
        if item.amount > outstanding:
            raise ValidationError(
                _("Le montant affecte a {label} depasse le solde restant de "
                  "{outstanding} {currency}.").format(
                    label=item.charge.obligation_label,
                    outstanding=outstanding,
                    currency=item.charge.currency,
                )
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
        raise PermissionDenied(_("Ce paiement n'appartient pas a ce locataire."))


@transaction.atomic
def confirm_payment_by_tenant(*, tenant: Tenant, payment: Payment) -> Payment:
    payment = Payment.objects.select_for_update().get(id=payment.id)
    _assert_payment_belongs_to_tenant(payment=payment, tenant=tenant)
    if payment.status == Payment.Status.CANCELLED:
        raise ValidationError(_("Un paiement annule ne peut pas etre confirme."))
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
        raise ValidationError(_("Un paiement annule ne peut pas etre conteste."))
    if payment.status == Payment.Status.CONFIRMED_BY_PROVIDER:
        raise ValidationError(
            _("Ce paiement a été confirmé par le prestataire Mobile Money.")
        )
    if not reason.strip():
        raise ValidationError(_("Le motif de contestation est obligatoire."))
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
            _("Une affectation de caution ne s'annule pas comme un encaissement. "
            "Consultez le journal de caution.")
        )
    if payment.status == Payment.Status.CONFIRMED_BY_PROVIDER:
        raise ValidationError(
            _("Un paiement confirmé par le prestataire ne peut pas être annulé manuellement.")
        )
    if not reason.strip():
        raise ValidationError(_("Le motif d'annulation est obligatoire."))

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
                _("Ce versement de caution ne peut plus être annulé car une partie "
                "de la caution a déjà été libérée.")
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
                _("Cette clé d'idempotence a déjà servi avec des données différentes.")
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
                _("Cette clé d'idempotence a déjà servi avec des données différentes.")
            )
        from modules.documents.services import (
            issue_security_deposit_settlement_document,
        )

        issue_security_deposit_settlement_document(movement=existing)
        return SecurityDepositSettlementResult(movement=existing, created=False)
    _assert_can_manage_charge(actor=actor, charge=deposit)
    if deposit.charge_type != RentCharge.Type.SECURITY_DEPOSIT:
        raise ValidationError(_("Cette obligation n'est pas une caution."))
    if data.movement_type not in SecurityDepositMovement.Type.values:
        raise ValidationError(_("Type de mouvement de caution invalide."))
    if data.amount <= 0:
        raise ValidationError(_("Le montant doit être strictement positif."))
    if data.amount > deposit.held_balance:
        raise ValidationError(
            _("Le montant dépasse la caution encore détenue de "
            "{held_balance} {currency}.").format(
                held_balance=deposit.held_balance, currency=deposit.currency
            )
        )

    reason = data.reason.strip()
    agreement_reference = data.agreement_reference.strip()
    target = None
    resulting_payment = None
    if data.movement_type == SecurityDepositMovement.Type.RETENTION and not reason:
        raise ValidationError(_("Le motif de la retenue est obligatoire."))
    if data.movement_type == SecurityDepositMovement.Type.APPLY_TO_RENT:
        if not data.agreement_confirmed or not agreement_reference:
            raise ValidationError(
                _("L'accord du locataire et sa référence sont obligatoires.")
            )
        if data.target_rent_charge is None:
            raise ValidationError(_("Sélectionnez le loyer à solder."))
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
                _("La caution peut seulement être affectée à un loyer du même bail.")
            )
        if target.status == RentCharge.Status.CANCELLED:
            raise ValidationError(_("Un loyer annulé ne peut pas recevoir la caution."))
        outstanding = target.amount_due - _active_allocated_total(target)
        if data.amount > outstanding:
            raise ValidationError(
                _("Le montant dépasse le solde du loyer de {outstanding} "
                "{currency}.").format(outstanding=outstanding, currency=target.currency)
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
            note=reason or _("Affectation de la caution au loyer"),
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
                _("Cet identifiant d'événement a déjà été utilisé avec un autre contenu.")
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
_("Une échéance annulée ne peut pas recevoir de paiement.")
                )
            if data.amount <= 0:
                raise ValidationError(
                    _("Le montant Mobile Money doit être strictement positif.")
                )
            if data.currency.upper() != charge.currency:
                raise ValidationError(_("La devise ne correspond pas à l'échéance."))
            outstanding = charge.amount_due - _active_allocated_total(charge)
            if data.amount > outstanding:
                raise ValidationError(
                    _("Le montant dépasse le solde restant de {outstanding} {currency}.").format(
                        outstanding=outstanding, currency=charge.currency
                    )
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
            _("Échéance inconnue.")
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


@dataclass(frozen=True)
class InitiatePaymentRequestData:
    rent_charge_id: UUID
    amount: Decimal
    operator: str
    method_account_id: UUID | None = None
    note: str = ""


def _assert_tenant_of_charge(*, user: User, charge: RentCharge) -> Tenant:
    tenant = (
        Tenant.objects.select_related("linked_user")
        .filter(linked_user=user, leases__property=charge.lease.property)
        .order_by("-created_at")
        .first()
    )
    if tenant is None:
        raise PermissionDenied(_("Cette échéance ne t'appartient pas."))
    return tenant


def _primary_payee(*, charge: RentCharge) -> User:
    try:
        ownership = charge.lease.property.ownerships.select_related("user").get(
            role=Ownership.Role.PRIMARY
        )
    except Ownership.DoesNotExist as exc:
        raise ValidationError(_("Le bien n'a pas de bailleur principal.")) from exc
    return ownership.user


def _outstanding_balance(charge: RentCharge) -> Decimal:
    return charge.amount_due - _active_allocated_total(charge)


def _enqueue_notification(
    *,
    recipient: User,
    kind: str,
    rent_charge: RentCharge,
    payment_request: PaymentRequest | None = None,
) -> None:
    from modules.documents.models import NotificationDelivery
    from modules.i18n.utils import resolve_language
    from modules.notifications.services import available_routes_for_user

    route = None
    routes = available_routes_for_user(recipient)
    if routes:
        route = routes[0]
    if route is None:
        return
    NotificationDelivery.objects.create(
        kind=kind,
        channel=route.channel,
        destination=route.destination,
        language=resolve_language(user=recipient),
        rent_charge=rent_charge,
        payment_request=payment_request,
    )


def _next_payment_request_reference() -> str:
    from .models import PaymentRequest

    for _ in range(10):
        candidate = f"PR-{uuid4().hex[:8].upper()}"
        if not PaymentRequest.objects.filter(reference=candidate).exists():
            return candidate
    raise ValidationError(_("Impossible de générer une référence unique."))


@transaction.atomic
def initiate_payment_request(
    *, tenant: User, data: InitiatePaymentRequestData
) -> PaymentRequest:
    """Le locataire demande un paiement au bailleur de la maison."""

    charge = (
        RentCharge.objects.select_for_update()
        .select_related(
            "lease__tenant",
            "lease__property",
        )
        .filter(id=data.rent_charge_id)
        .first()
    )
    if charge is None:
        raise ValidationError(_("Cette échéance est introuvable."))
    _assert_tenant_of_charge(user=tenant, charge=charge)
    if charge.status == RentCharge.Status.CANCELLED:
        raise ValidationError(_("Une échéance annulée ne peut pas recevoir de demande."))
    if charge.charge_type == RentCharge.Type.SECURITY_DEPOSIT:
        raise ValidationError(
            _("La caution ne se règle pas par demande de paiement.")
        )
    if data.amount <= 0:
        raise ValidationError(_("Le montant doit être strictement positif."))
    outstanding = _outstanding_balance(charge)
    if data.amount > outstanding:
        raise ValidationError(
            _("Le montant dépasse le solde restant de {outstanding} {currency}.").format(
                outstanding=outstanding, currency=charge.currency
            )
        )
    if PaymentRequest.objects.filter(
        rent_charge=charge, status=PaymentRequest.Status.PENDING
    ).exists():
        raise ValidationError(
            _("Une demande est déjà en attente pour cette échéance.")
        )
    if data.operator not in PaymentRequest.Operator.values:
        raise ValidationError(_("Moyen de paiement invalide."))

    payee = _primary_payee(charge=charge)
    method_account = None
    if data.method_account_id:
        method_account = (
            PaymentMethodAccount.objects.select_related("owner")
            .filter(id=data.method_account_id, owner=payee)
            .first()
        )
        if method_account is None:
            raise ValidationError(
                _("Ce compte de réception n'appartient pas au bailleur du bien.")
            )
        if method_account.operator != data.operator:
            raise ValidationError(
                _("Le compte choisi ne correspond pas au moyen de paiement.")
            )

    payment_request = PaymentRequest(
        reference=_next_payment_request_reference(),
        rent_charge=charge,
        amount=data.amount,
        currency=charge.currency,
        operator=data.operator,
        method_account=method_account,
        payee=payee,
        payee_name=payee.get_full_name() or payee.phone,
        payee_phone=payee.phone,
        requested_by=tenant,
        note=data.note.strip(),
    )
    payment_request.full_clean()
    payment_request.save()

    _enqueue_notification(
        recipient=payee,
        kind="PAYMENT_REQUEST",
        rent_charge=charge,
        payment_request=payment_request,
    )
    return payment_request


def _payment_method_for_operator(operator: str) -> str:
    return {
        PaymentRequest.Operator.CASH: Payment.Method.CASH,
        PaymentRequest.Operator.BANK_TRANSFER: Payment.Method.BANK_TRANSFER,
        PaymentRequest.Operator.MTN_MOMO: Payment.Method.EXTERNAL_MOBILE_MONEY,
        PaymentRequest.Operator.ORANGE_MONEY: Payment.Method.EXTERNAL_MOBILE_MONEY,
        PaymentRequest.Operator.MOOV_MONEY: Payment.Method.EXTERNAL_MOBILE_MONEY,
        PaymentRequest.Operator.WAVE: Payment.Method.EXTERNAL_MOBILE_MONEY,
        PaymentRequest.Operator.OTHER: Payment.Method.OTHER,
    }[operator]


@transaction.atomic
def confirm_payment_request(
    *,
    owner: User,
    payment_request: PaymentRequest,
    received_amount: Decimal | None = None,
    note: str = "",
) -> PaymentRequest:
    """Le bailleur confirme la réception ; crée le paiement et la quittance."""

    payment_request = (
        PaymentRequest.objects.select_for_update()
        .select_related("rent_charge__lease__tenant", "rent_charge__lease__property")
        .get(id=payment_request.id)
    )
    charge = payment_request.rent_charge
    if payment_request.status != PaymentRequest.Status.PENDING:
        raise ValidationError(_("Cette demande a déjà été traitée."))
    if charge.status == RentCharge.Status.CANCELLED:
        raise ValidationError(_("Une échéance annulée ne peut pas recevoir de paiement."))
    _assert_can_manage_charge(actor=owner, charge=charge)

    received = received_amount if received_amount is not None else payment_request.amount
    if received <= 0:
        raise ValidationError(_("Le montant reçu doit être strictement positif."))
    outstanding = _outstanding_balance(charge)
    if received > outstanding:
        raise ValidationError(
            _("Le montant reçu dépasse le solde restant de {outstanding} "
            "{currency}.").format(outstanding=outstanding, currency=charge.currency)
        )

    idempotency_key = uuid5(
        NAMESPACE_URL, f"immolib:payment-request:{payment_request.id}"
    )
    payment = Payment(
        amount=received,
        currency=payment_request.currency,
        method=_payment_method_for_operator(payment_request.operator),
        status=Payment.Status.RECORDED_BY_OWNER,
        received_at=timezone.now(),
        external_reference=payment_request.reference,
        note=note.strip() or f"Demande {payment_request.reference}",
        idempotency_key=idempotency_key,
        recorded_by=owner,
    )
    payment.full_clean()
    payment.save()
    allocation = PaymentAllocation(
        payment=payment,
        rent_charge=charge,
        amount=received,
    )
    allocation.full_clean()
    allocation.save()
    PaymentEvent.objects.create(
        payment=payment,
        event_type=PaymentEvent.Type.RECORDED,
        actor_user=owner,
        metadata={
            "source": "PAYMENT_REQUEST",
            "payment_request_id": str(payment_request.id),
            "payment_request_reference": payment_request.reference,
        },
    )
    _recalculate_charge(charge)

    payment_request.status = PaymentRequest.Status.CONFIRMED
    payment_request.amount_received = received
    payment_request.processing_note = note.strip()
    payment_request.processed_by = owner
    payment_request.processed_at = timezone.now()
    payment_request.payment = payment
    payment_request.save(
        update_fields=[
            "status",
            "amount_received",
            "processing_note",
            "processed_by",
            "processed_at",
            "payment",
            "updated_at",
        ]
    )

    from modules.documents.services import issue_documents_for_payment

    issue_documents_for_payment(payment=payment)
    _enqueue_notification(
        recipient=payment_request.requested_by,
        kind="PAYMENT_CONFIRMED",
        rent_charge=charge,
        payment_request=payment_request,
    )
    return payment_request


@transaction.atomic
def refuse_payment_request(
    *, owner: User, payment_request: PaymentRequest, reason: str
) -> PaymentRequest:
    """Le bailleur signale qu'il n'a pas reçu les fonds."""

    payment_request = PaymentRequest.objects.select_for_update().get(
        id=payment_request.id
    )
    if payment_request.status != PaymentRequest.Status.PENDING:
        raise ValidationError(_("Cette demande a déjà été traitée."))
    if not reason.strip():
        raise ValidationError(_("Le motif est obligatoire."))
    _assert_can_manage_charge(actor=owner, charge=payment_request.rent_charge)

    payment_request.status = PaymentRequest.Status.NOT_RECEIVED
    payment_request.processing_note = reason.strip()
    payment_request.processed_by = owner
    payment_request.processed_at = timezone.now()
    payment_request.save(
        update_fields=[
            "status",
            "processing_note",
            "processed_by",
            "processed_at",
            "updated_at",
        ]
    )
    return payment_request


@transaction.atomic
def cancel_payment_request(
    *, tenant: User, payment_request: PaymentRequest, reason: str = ""
) -> PaymentRequest:
    """Le locataire annule sa demande tant qu'elle est en attente."""

    payment_request = PaymentRequest.objects.select_for_update().get(
        id=payment_request.id
    )
    if payment_request.requested_by_id != tenant.id:
        raise PermissionDenied(_("Tu ne peux pas annuler cette demande."))
    if payment_request.status != PaymentRequest.Status.PENDING:
        raise ValidationError(_("Cette demande a déjà été traitée."))

    payment_request.status = PaymentRequest.Status.CANCELLED
    payment_request.processing_note = reason.strip()
    payment_request.save(
        update_fields=["status", "processing_note", "updated_at"]
    )
    return payment_request
