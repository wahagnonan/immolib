import hashlib
import hmac
import json
import time
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from modules.billing.services import generate_monthly_charges
from modules.documents.models import RentalDocument
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house

from ..models import Payment, PaymentEvent, PaymentProviderEvent


@override_settings(
    MOBILE_MONEY_WEBHOOK_SECRET="secret-webhook-test",
    MOBILE_MONEY_WEBHOOK_TOLERANCE_SECONDS=300,
)
class MobileMoneyWebhookApiTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            phone="+2250700001700",
            password="password",
        )
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Yopougon",
                address="Niangon",
                city="Abidjan",
                commune="Yopougon",
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Adjoua Yao",
                phone="+2250500001700",
            ),
        )
        lease = create_lease(
            actor=self.owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("95000"),
                monthly_charges=Decimal("5000"),
                due_day=5,
            ),
        )
        activate_lease(actor=self.owner, lease=lease)
        self.charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]

    def _payload(self, *, event_id="evt-001", event_status="SUCCEEDED"):
        return {
            "provider": "sandbox-psp",
            "event_id": event_id,
            "event_type": "PAYMENT_STATUS_CHANGED",
            "status": event_status,
            "transaction_id": f"txn-{event_id}",
            "rent_charge_id": str(self.charge.id),
            "amount": "100000.00",
            "currency": "XOF",
            "paid_at": "2026-08-04T10:00:00Z",
        }

    def _post(self, payload, *, valid_signature=True):
        raw_body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = hmac.new(
            b"secret-webhook-test",
            timestamp.encode("ascii") + b"." + raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not valid_signature:
            signature = "0" * 64
        return self.client.generic(
            "POST",
            "/api/v1/webhooks/mobile-money/",
            data=raw_body,
            content_type="application/json",
            HTTP_X_IMMOLIB_TIMESTAMP=timestamp,
            HTTP_X_IMMOLIB_SIGNATURE=f"sha256={signature}",
        )

    def test_signed_success_confirms_payment_and_issues_documents(self):
        response = self._post(self._payload())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["created"])
        self.assertEqual(
            response.data["payment_status"],
            Payment.Status.CONFIRMED_BY_PROVIDER,
        )
        payment = Payment.objects.get()
        self.assertEqual(payment.method, Payment.Method.MOBILE_MONEY)
        self.assertEqual(payment.recorded_by, self.owner)
        self.assertTrue(
            payment.events.filter(
                event_type=PaymentEvent.Type.PROVIDER_CONFIRMED
            ).exists()
        )
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.amount_paid, Decimal("100000"))
        self.assertEqual(self.charge.status, "PAID")
        self.assertEqual(
            RentalDocument.objects.filter(payment=payment).count(),
            2,
        )
        self.assertEqual(
            PaymentProviderEvent.objects.get().status,
            PaymentProviderEvent.Status.PROCESSED,
        )

    def test_retry_is_idempotent(self):
        first = self._post(self._payload())
        second = self._post(self._payload())

        self.assertTrue(first.data["created"])
        self.assertFalse(second.data["created"])
        self.assertEqual(first.data["payment_id"], second.data["payment_id"])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentProviderEvent.objects.count(), 1)

    def test_invalid_signature_is_rejected(self):
        response = self._post(self._payload(), valid_signature=False)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(PaymentProviderEvent.objects.count(), 0)

    def test_non_success_event_is_recorded_but_ignored(self):
        response = self._post(
            self._payload(event_id="evt-failed", event_status="FAILED")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["payment_id"])
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(
            PaymentProviderEvent.objects.get().status,
            PaymentProviderEvent.Status.IGNORED,
        )

    def test_owner_cannot_cancel_provider_confirmed_payment(self):
        created = self._post(self._payload())
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            f"/api/v1/payments/{created.data['payment_id']}/cancel/",
            {"reason": "Tentative manuelle"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Payment.objects.get().status,
            Payment.Status.CONFIRMED_BY_PROVIDER,
        )
