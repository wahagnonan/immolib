import hashlib
import hmac
import json
import time
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, override_settings

from modules.billing.services import generate_monthly_charges
from modules.documents.models import RentalDocument
from modules.leases.models import Tenant
from modules.leases.services import CreateLeaseData, CreateTenantData, activate_lease, create_lease, create_tenant
from modules.properties.services import CreateHouseData, create_house

from ..models import Payment, PaymentProviderEvent, PaymentRequest


def _pi_spi_headers(raw_body: bytes, secret: str | None = None):
    s = secret or getattr(settings, "PI_SPI_WEBHOOK_SECRET", "test-secret")
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(s.encode(), ts.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
    return {"X-PI-SPI-Timestamp": ts, "X-PI-SPI-Signature": sig}


class PiSpiFlowTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(phone="+2250700000900", password="password")
        self.tenant_user = User.objects.create_user(phone="+2250700000901", password="password")
        for u in (self.owner, self.tenant_user):
            u.email = f"{u.phone}@example.com"
            from django.utils import timezone
            u.email_verified_at = timezone.now()
            u.save(update_fields=["email", "email_verified_at", "updated_at"])
        house = create_house(owner=self.owner, data=CreateHouseData(name="Maison PI-SPI", address="Rue 1", city="Abidjan"))
        # Crée un compte PI_SPI pour le bailleur (bénéficiaire)
        from ..models import PaymentMethodAccount
        PaymentMethodAccount.objects.create(owner=self.owner, operator="PI_SPI", account_identifier="CI93_UEMOA_123", account_holder="Bailleur")
        tenant = create_tenant(actor=self.owner, property=house, data=CreateTenantData(full_name="Loc PI", phone="+2250500000900"))
        tenant.linked_user = self.tenant_user
        tenant.save(update_fields=["linked_user"])
        self.lease = create_lease(actor=self.owner, property=house, tenant=tenant, data=CreateLeaseData(start_date=date(2026, 7, 1), monthly_rent=Decimal("100000"), due_day=5))
        activate_lease(actor=self.owner, lease=self.lease)
        self.charge = generate_monthly_charges(actor=self.owner, period_start=date(2026, 8, 1), today=date(2026, 7, 25)).charges[0]

    def _create_pi_spi_request(self, amount="100000.00"):
        self.client.force_authenticate(self.tenant_user)
        resp = self.client.post("/api/v1/payment-requests/", {"rent_charge_id": str(self.charge.id), "amount": amount, "operator": "PI_SPI"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        return resp.data

    @override_settings(PI_SPI_ENABLED=True, PI_SPI_MOCK_ENABLED=True, PI_SPI_MOCK_AUTO_SUCCESS=False, PI_SPI_WEBHOOK_SECRET="test-secret")
    def test_initiate_pi_spi_mock_pending(self):
        data = self._create_pi_spi_request()
        rid = data["id"]
        # Initiate via PI-SPI
        resp = self.client.post(f"/api/v1/payment-requests/{rid}/initiate-pi-spi/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["payment_request"]["status"], "PROCESSING")
        self.assertTrue(resp.data["external_transaction_id"].startswith("mock-"))
        # Idempotence : second call returns same transaction, created false
        resp2 = self.client.post(f"/api/v1/payment-requests/{rid}/initiate-pi-spi/", {}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data["external_transaction_id"], resp.data["external_transaction_id"])
        self.assertFalse(resp2.data["created"])

    @override_settings(PI_SPI_ENABLED=True, PI_SPI_MOCK_ENABLED=True, PI_SPI_WEBHOOK_SECRET="test-secret")
    def test_webhook_success_creates_payment_and_receipt(self):
        data = self._create_pi_spi_request()
        rid = data["id"]
        init = self.client.post(f"/api/v1/payment-requests/{rid}/initiate-pi-spi/", {}, format="json")
        ext_txn = init.data["external_transaction_id"]
        # Simulate PSP webhook success
        payload = {
            "provider": "PI_SPI",
            "event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "event_type": "payment.succeeded",
            "status": "SUCCEEDED",
            "transaction_id": ext_txn,
            "payment_request_id": rid,
            "rent_charge_id": str(self.charge.id),
            "amount": "100000.00",
            "currency": "XOF",
            "paid_at": "2026-08-05T12:00:00Z",
        }
        raw = json.dumps(payload).encode()
        headers = _pi_spi_headers(raw, "test-secret")
        resp = self.client.post(
            "/api/v1/webhooks/pi-spi/",
            data=raw,
            content_type="application/json",
            **{f"HTTP_{k.upper().replace('-','_')}": v for k, v in headers.items()},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp.data["payment_id"])
        # Payment created
        payment = Payment.objects.get(id=resp.data["payment_id"])
        self.assertEqual(payment.method, "PI_SPI")
        self.assertEqual(payment.status, "CONFIRMED_BY_PROVIDER")
        self.assertEqual(payment.amount, Decimal("100000.00"))
        # RentCharge updated
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.amount_paid, Decimal("100000.00"))
        self.assertEqual(self.charge.status, "PAID")
        # Receipt generated
        self.assertTrue(RentalDocument.objects.filter(payment=payment).exists())
        # Request confirmed
        pr = PaymentRequest.objects.get(id=rid)
        self.assertEqual(pr.status, "CONFIRMED")

    @override_settings(PI_SPI_ENABLED=True, PI_SPI_MOCK_ENABLED=True, PI_SPI_WEBHOOK_SECRET="test-secret")
    def test_webhook_idempotent_replay(self):
        data = self._create_pi_spi_request()
        rid = data["id"]
        init = self.client.post(f"/api/v1/payment-requests/{rid}/initiate-pi-spi/", {}, format="json")
        ext_txn = init.data["external_transaction_id"]
        payload = {
            "provider": "PI_SPI",
            "event_id": "evt-replay-123",
            "status": "SUCCEEDED",
            "transaction_id": ext_txn,
            "payment_request_id": rid,
            "rent_charge_id": str(self.charge.id),
            "amount": "100000.00",
            "currency": "XOF",
            "paid_at": "2026-08-05T12:00:00Z",
        }
        raw = json.dumps(payload).encode()
        headers = _pi_spi_headers(raw, "test-secret")
        h = {f"HTTP_{k.upper().replace('-','_')}": v for k, v in headers.items()}
        r1 = self.client.post("/api/v1/webhooks/pi-spi/", data=raw, content_type="application/json", **h)
        r2 = self.client.post("/api/v1/webhooks/pi-spi/", data=raw, content_type="application/json", **h)
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["payment_id"], r2.data["payment_id"])
        self.assertEqual(Payment.objects.filter(payment_request__id=rid).count(), 1)
        self.assertEqual(PaymentProviderEvent.objects.filter(external_event_id="evt-replay-123").count(), 1)

    @override_settings(PI_SPI_ENABLED=True, PI_SPI_MOCK_ENABLED=True, PI_SPI_WEBHOOK_SECRET="test-secret")
    def test_webhook_rejects_amount_mismatch(self):
        data = self._create_pi_spi_request()
        rid = data["id"]
        self.client.post(f"/api/v1/payment-requests/{rid}/initiate-pi-spi/", {}, format="json")
        payload = {
            "provider": "PI_SPI",
            "event_id": "evt-bad-amount",
            "status": "SUCCEEDED",
            "transaction_id": "bad-txn",
            "payment_request_id": rid,
            "rent_charge_id": str(self.charge.id),
            "amount": "9999.00",  # mismatch
            "currency": "XOF",
        }
        raw = json.dumps(payload).encode()
        headers = _pi_spi_headers(raw, "test-secret")
        h = {f"HTTP_{k.upper().replace('-','_')}": v for k, v in headers.items()}
        resp = self.client.post("/api/v1/webhooks/pi-spi/", data=raw, content_type="application/json", **h)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.filter(payment_request__id=rid).count(), 0)

    @override_settings(PI_SPI_ENABLED=True, PI_SPI_MOCK_ENABLED=True, PI_SPI_WEBHOOK_SECRET="test-secret")
    def test_webhook_rejects_invalid_signature(self):
        data = self._create_pi_spi_request()
        rid = data["id"]
        self.client.post(f"/api/v1/payment-requests/{rid}/initiate-pi-spi/", {}, format="json")
        payload = {"provider": "PI_SPI", "event_id": "evt-bad-sig", "status": "SUCCEEDED", "transaction_id": "x", "payment_request_id": rid, "rent_charge_id": str(self.charge.id), "amount": "100000.00", "currency": "XOF"}
        raw = json.dumps(payload).encode()
        headers = {"X-PI-SPI-Timestamp": str(int(time.time())), "X-PI-SPI-Signature": "sha256=bad"}
        h = {f"HTTP_{k.upper().replace('-','_')}": v for k, v in headers.items()}
        resp = self.client.post("/api/v1/webhooks/pi-spi/", data=raw, content_type="application/json", **h)
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

    @override_settings(PI_SPI_ENABLED=True, PI_SPI_MOCK_ENABLED=True, PI_SPI_WEBHOOK_SECRET="test-secret")
    def test_outsider_cannot_initiate_pi_spi(self):
        data = self._create_pi_spi_request()
        rid = data["id"]
        User = get_user_model()
        outsider = User.objects.create_user(phone="+2250700000999", password="password")
        self.client.force_authenticate(outsider)
        resp = self.client.post(f"/api/v1/payment-requests/{rid}/initiate-pi-spi/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(PI_SPI_ENABLED=True, PI_SPI_MOCK_ENABLED=True, PI_SPI_WEBHOOK_SECRET="test-secret")
    def test_status_polling(self):
        data = self._create_pi_spi_request()
        rid = data["id"]
        self.client.post(f"/api/v1/payment-requests/{rid}/initiate-pi-spi/", {}, format="json")
        self.client.force_authenticate(self.tenant_user)
        resp = self.client.get(f"/api/v1/payment-requests/{rid}/pi-spi-status/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "PROCESSING")
