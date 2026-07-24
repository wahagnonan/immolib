from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.billing.models import RentCharge
from modules.billing.services import generate_monthly_charges
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.models import Ownership
from modules.properties.services import CreateHouseData, create_house

from ..models import Payment, PaymentEvent
from ..services import (
    RecordOfflinePaymentData,
    cancel_payment,
    confirm_payment_by_tenant,
    dispute_payment_by_tenant,
    record_offline_payment,
)


class OfflinePaymentServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000500", password="password"
        )
        self.observer = user_model.objects.create_user(
            phone="+2250700000501", password="password"
        )
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Port-Bouet",
                address="Vridi",
                city="Abidjan",
                commune="Port-Bouet",
            ),
        )
        Ownership.objects.create(
            property=self.house,
            user=self.observer,
            role=Ownership.Role.CO_OWNER,
            access_level=Ownership.AccessLevel.OBSERVER,
        )
        self.tenant = create_tenant(
            actor=self.owner,
            property=self.house,
            data=CreateTenantData(
                full_name="Mariam Coulibaly", phone="+2250500000500"
            ),
        )
        lease = create_lease(
            actor=self.owner,
            property=self.house,
            tenant=self.tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("100000"),
                monthly_charges=Decimal("10000"),
                due_day=5,
            ),
        )
        activate_lease(actor=self.owner, lease=lease)
        self.charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]
        self.received_at = timezone.make_aware(datetime(2026, 8, 4, 10, 30))

    def _record(self, amount, *, key=None, actor=None, method=Payment.Method.CASH):
        return record_offline_payment(
            actor=actor or self.owner,
            charge=self.charge,
            data=RecordOfflinePaymentData(
                amount=Decimal(amount),
                method=method,
                idempotency_key=key or uuid4(),
                received_at=self.received_at,
            ),
        )

    def test_partial_payment_updates_charge_and_creates_event(self):
        result = self._record("40000")

        self.charge.refresh_from_db()
        self.assertTrue(result.created)
        self.assertEqual(self.charge.amount_paid, Decimal("40000"))
        self.assertEqual(self.charge.balance_due, Decimal("70000"))
        self.assertEqual(self.charge.status, RentCharge.Status.PARTIALLY_PAID)
        self.assertEqual(
            result.payment.events.get().event_type, PaymentEvent.Type.RECORDED
        )

    def test_multiple_payments_can_fully_pay_charge(self):
        self._record("40000")
        self._record("70000")

        self.charge.refresh_from_db()
        self.assertEqual(self.charge.amount_paid, Decimal("110000"))
        self.assertEqual(self.charge.balance_due, Decimal("0"))
        self.assertEqual(self.charge.status, RentCharge.Status.PAID)

    def test_payment_cannot_exceed_outstanding_balance(self):
        with self.assertRaisesMessage(ValidationError, "depasse le solde"):
            self._record("110001")

    def test_same_idempotency_key_returns_same_payment(self):
        key = uuid4()
        first = self._record("40000", key=key)
        second = self._record("40000", key=key)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.payment.id, second.payment.id)
        self.assertEqual(Payment.objects.count(), 1)

    def test_idempotency_key_cannot_be_reused_with_different_amount(self):
        key = uuid4()
        self._record("40000", key=key)

        with self.assertRaisesMessage(ValidationError, "donnees differentes"):
            self._record("30000", key=key)

    def test_observer_cannot_record_payment(self):
        with self.assertRaises(PermissionDenied):
            self._record("40000", actor=self.observer)

    def test_tenant_dispute_does_not_cancel_owner_validated_amount(self):
        payment = self._record("110000").payment

        disputed = dispute_payment_by_tenant(
            tenant=self.tenant,
            payment=payment,
            reason="Je ne reconnais pas ce paiement.",
        )

        self.charge.refresh_from_db()
        self.assertEqual(disputed.status, Payment.Status.DISPUTED_BY_TENANT)
        self.assertEqual(self.charge.amount_paid, Decimal("110000"))
        self.assertEqual(self.charge.status, RentCharge.Status.PAID)
        self.assertTrue(
            disputed.events.filter(event_type=PaymentEvent.Type.TENANT_DISPUTED).exists()
        )

    def test_tenant_can_confirm_payment(self):
        payment = self._record("40000").payment

        confirmed = confirm_payment_by_tenant(tenant=self.tenant, payment=payment)

        self.assertEqual(confirmed.status, Payment.Status.CONFIRMED_BY_TENANT)
        self.assertTrue(
            confirmed.events.filter(event_type=PaymentEvent.Type.TENANT_CONFIRMED).exists()
        )

    def test_cancellation_preserves_payment_and_recalculates_charge(self):
        payment = self._record("40000").payment

        cancelled = cancel_payment(
            actor=self.owner,
            payment=payment,
            reason="Erreur de saisie du bailleur.",
        )

        self.charge.refresh_from_db()
        self.assertEqual(cancelled.status, Payment.Status.CANCELLED)
        self.assertEqual(self.charge.amount_paid, Decimal("0"))
        self.assertNotEqual(self.charge.status, RentCharge.Status.PARTIALLY_PAID)
        self.assertTrue(Payment.objects.filter(id=payment.id).exists())
