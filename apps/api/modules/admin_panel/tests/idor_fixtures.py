"""Fixtures partagees de la matrice IDOR cross-tenant.

Deux bailleurs A et B, chacun avec un patrimoine disjoint complet :
maison, locataire (compte lie), bail actif, echeance payee, echeance
impayee, paiement, quittances, partage de document, incident de
maintenance, invitation de coproprietaire et demande de paiement.

Les tests IDOR de chaque module reutilisent ces fixtures pour prouver
qu'un utilisateur A ne peut ni lire ni modifier les objets de B
(reponse 404 attendue, jamais 403).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone

from modules.billing.services import ensure_security_deposit_obligation, generate_monthly_charges
from modules.documents.models import RentalDocument
from modules.documents.services import share_document
from modules.leases.models import Tenant
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.maintenance.models import MaintenanceIncident
from modules.maintenance.services import CreateIncidentData, create_incident
from modules.payments.models import Payment, PaymentRequest
from modules.payments.services import (
    InitiatePaymentRequestData,
    PaymentAllocationData,
    RecordOfflinePaymentData,
    initiate_payment_request,
    record_allocated_offline_payment,
)
from modules.properties.models import Ownership
from modules.properties.services import (
    CreateHouseData,
    InviteCoOwnerData,
    create_house,
    invite_coowner,
)
from modules.subscriptions.services import upgrade

User = get_user_model()


def make_landlord(phone: str):
    """Bailleur avec plan Essentiel (co_owners, plusieurs maisons)."""
    user = User.objects.create_user(phone=phone, password="password")
    upgrade(user, "essential")
    return user


def make_tenant_user(phone: str):
    """Compte locataire verifie, prêt à être lié à une fiche locataire."""
    return User.objects.create_user(
        phone=phone,
        password="password",
        phone_verified_at=timezone.now(),
        email=f"locataire-{phone.replace('+', '')}@example.com",
    )


@dataclass
class Estate:
    owner: object
    house: object
    tenant: object
    tenant_user: object
    lease: object
    charge: object
    unpaid_charge: object
    deposit_obligation: object
    payment: object
    receipt: object
    rent_receipt: object
    incident: object
    coowner_invitation: object
    payment_request: object
    delivery: object


def make_estate(*, owner, name, tenant_phone, coowner_phone) -> Estate:
    """Patrimoine complet et disjoint pour un bailleur."""
    tenant_user = make_tenant_user(tenant_phone)
    house = create_house(
        owner=owner,
        data=CreateHouseData(
            name=name,
            address="Cocody",
            commune="Cocody",
            city="Abidjan",
        ),
    )
    tenant = create_tenant(
        actor=owner,
        property=house,
        data=CreateTenantData(
            full_name=f"Locataire {name}",
            phone=tenant_phone,
            email=tenant_user.email,
        ),
    )
    lease = create_lease(
        actor=owner,
        property=house,
        tenant=tenant,
        data=CreateLeaseData(
            start_date=date(2026, 7, 1),
            monthly_rent=Decimal("100000"),
            monthly_charges=Decimal("0"),
            due_day=5,
            security_deposit=Decimal("100000"),
        ),
    )
    activate_lease(actor=owner, lease=lease)
    charge = generate_monthly_charges(
        actor=owner,
        period_start=date(2026, 8, 1),
        today=date(2026, 7, 25),
    ).charges[0]
    unpaid_charge = generate_monthly_charges(
        actor=owner,
        period_start=date(2026, 9, 1),
        today=date(2026, 8, 25),
    ).charges[0]
    deposit_obligation, _ = ensure_security_deposit_obligation(
        actor=owner, lease=lease, today=date(2026, 7, 25)
    )

    result = record_allocated_offline_payment(
        actor=owner,
        allocations=(PaymentAllocationData(charge=charge, amount=Decimal("100000")),),
        data=RecordOfflinePaymentData(
            amount=Decimal("100000"),
            method=Payment.Method.CASH,
            idempotency_key=uuid4(),
            received_at=timezone.now(),
        ),
    )
    payment = result.payment
    receipt = RentalDocument.objects.get(
        payment=payment, document_type=RentalDocument.Type.PAYMENT_RECEIPT
    )
    rent_receipt = RentalDocument.objects.get(
        rent_charge=charge, document_type=RentalDocument.Type.RENT_RECEIPT
    )
    share = share_document(actor=owner, document=receipt, channels=["SMS"])
    incident = create_incident(
        actor=owner,
        lease=lease,
        data=CreateIncidentData(
            title=f"Incident {name}",
            description="Fuite d'eau dans la cuisine",
            category=MaintenanceIncident.Category.PLUMBING,
            priority=MaintenanceIncident.Priority.NORMAL,
        ),
    )
    coowner_invitation = invite_coowner(
        actor=owner,
        property=house,
        data=InviteCoOwnerData(
            phone=coowner_phone,
            access_level=Ownership.AccessLevel.OBSERVER,
        ),
    )
    payment_request = initiate_payment_request(
        tenant=tenant_user,
        data=InitiatePaymentRequestData(
            rent_charge_id=unpaid_charge.id,
            amount=Decimal("50000"),
            operator=PaymentRequest.Operator.ORANGE_MONEY,
        ),
    )
    return Estate(
        owner=owner,
        house=house,
        tenant=tenant,
        tenant_user=tenant_user,
        lease=lease,
        charge=charge,
        unpaid_charge=unpaid_charge,
        deposit_obligation=deposit_obligation,
        payment=payment,
        receipt=receipt,
        rent_receipt=rent_receipt,
        incident=incident,
        coowner_invitation=coowner_invitation,
        payment_request=payment_request,
        delivery=share.deliveries[0],
    )
