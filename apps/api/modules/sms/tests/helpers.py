"""Fixtures partagees des tests SMS : construction d'une NotificationDelivery.

La chaine complete (propriete -> bail -> charge -> paiement -> document ->
partage SMS) est creee via les services reels, comme dans les tests du module
documents, pour rester proche du flux de production.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone

from modules.billing.services import generate_monthly_charges
from modules.documents.models import NotificationDelivery, RentalDocument
from modules.documents.services import share_document
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.payments.models import Payment
from modules.payments.services import RecordOfflinePaymentData, record_offline_payment
from modules.properties.services import CreateHouseData, create_house


def build_delivery(*, phone: str = "+2250500000900") -> NotificationDelivery:
    """Cree une NotificationDelivery SMS (quittance de loyer partagee)."""
    owner = get_user_model().objects.create_user(
        phone="+2250700000987",
        password="password",
        first_name="Awa",
        last_name="Kone",
    )
    house = create_house(
        owner=owner,
        data=CreateHouseData(
            name="Maison Tests SMS",
            address="Cocody Riviera",
            city="Abidjan",
            commune="Cocody",
        ),
    )
    tenant = create_tenant(
        actor=owner,
        property=house,
        data=CreateTenantData(
            full_name="Yao Kouassi",
            phone=phone,
            email="yao@example.com",
        ),
    )
    lease = create_lease(
        actor=owner,
        property=house,
        tenant=tenant,
        data=CreateLeaseData(
            start_date=date(2026, 7, 1),
            monthly_rent=Decimal("100000"),
            due_day=5,
        ),
    )
    activate_lease(actor=owner, lease=lease)
    charge = generate_monthly_charges(
        actor=owner,
        period_start=date(2026, 8, 1),
        today=date(2026, 7, 25),
    ).charges[0]
    payment = record_offline_payment(
        actor=owner,
        charge=charge,
        data=RecordOfflinePaymentData(
            amount=Decimal("40000"),
            method=Payment.Method.CASH,
            idempotency_key=uuid4(),
            received_at=timezone.make_aware(datetime(2026, 8, 4, 12, 0)),
        ),
    ).payment
    document = payment.rental_documents.get(
        document_type=RentalDocument.Type.PAYMENT_RECEIPT
    )
    result = share_document(actor=owner, document=document, channels=["SMS"])
    return result.deliveries[0]


def dr_payload(
    *,
    resource_id: str = "resource-ABC",
    status: str = "DeliveredToTerminal",
    address: str = "tel:+2250700000001",
) -> dict:
    """Payload de Delivery Receipt Orange conforme a la documentation."""
    return {
        "deliveryInfoNotification": {
            "callbackData": resource_id,
            "deliveryInfo": {"address": address, "deliveryStatus": status},
        }
    }
