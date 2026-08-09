from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from modules.billing.services import generate_monthly_charges
from modules.documents.models import RentalDocument
from modules.leases.models import Lease, Tenant
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
from modules.subscriptions.services import upgrade


class TenantPortalApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700001500",
            password="password",
            first_name="Jean",
            last_name="Soro",
        )
        self.tenant_user = user_model.objects.create_user(
            phone="+2250500001500",
            email="mariam@example.com",
            password="password",
            first_name="Mariam",
            last_name="Koné",
        )
        self.outsider = user_model.objects.create_user(
            phone="+2250100001500",
            password="password",
        )
        upgrade(self.owner, "essential")
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Riviera",
                address="Riviera Palmeraie",
                city="Abidjan",
                commune="Cocody",
            ),
        )
        self.tenant = create_tenant(
            actor=self.owner,
            property=self.house,
            data=CreateTenantData(
                full_name="Mariam Koné",
                phone=self.tenant_user.phone,
                email=self.tenant_user.email,
            ),
        )
        self.lease = create_lease(
            actor=self.owner,
            property=self.house,
            tenant=self.tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("100000"),
                monthly_charges=Decimal("5000"),
                due_day=5,
                security_deposit=Decimal("100000"),
            ),
        )
        activate_lease(actor=self.owner, lease=self.lease)
        self.charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]
        self.payment = record_offline_payment(
            actor=self.owner,
            charge=self.charge,
            data=RecordOfflinePaymentData(
                amount=Decimal("40000"),
                method=Payment.Method.CASH,
                idempotency_key=uuid4(),
                received_at=timezone.make_aware(
                    datetime(2026, 8, 4, 9, 0)
                ),
                note="Remis en main propre",
            ),
        ).payment

    def test_overview_contains_only_linked_tenant_data(self):
        other_house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison privée",
                address="Marcory",
                city="Abidjan",
            ),
        )
        other_tenant = create_tenant(
            actor=self.owner,
            property=other_house,
            data=CreateTenantData(
                full_name="Autre locataire",
                phone="+2250500001599",
            ),
        )
        create_lease(
            actor=self.owner,
            property=other_house,
            tenant=other_tenant,
            data=CreateLeaseData(
                start_date=date(2026, 8, 1),
                monthly_rent=Decimal("80000"),
                due_day=5,
            ),
        )
        self.client.force_authenticate(self.tenant_user)

        response = self.client.get("/api/v1/tenant-portal/overview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_profile"])
        self.assertEqual(len(response.data["profiles"]), 1)
        self.assertEqual(
            response.data["profiles"][0]["house"]["name"],
            "Maison Riviera",
        )
        self.assertEqual(
            response.data["profiles"][0]["owner"]["full_name"],
            "Jean Soro",
        )
        self.assertEqual(response.data["balances"][0]["amount"], "65000.00")
        self.assertEqual(response.data["payment_to_review_count"], 1)
        self.assertEqual(response.data["document_count"], 1)

    def test_draft_lease_is_hidden_from_tenant(self):
        draft_house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Future maison",
                address="Bingerville",
                city="Abidjan",
            ),
        )
        draft_tenant = create_tenant(
            actor=self.owner,
            property=draft_house,
            data=CreateTenantData(
                full_name=self.tenant.full_name,
                phone=self.tenant_user.phone,
                email=self.tenant_user.email,
            ),
        )
        draft = create_lease(
            actor=self.owner,
            property=draft_house,
            tenant=draft_tenant,
            data=CreateLeaseData(
                start_date=date(2026, 9, 1),
                monthly_rent=Decimal("120000"),
                due_day=5,
            ),
        )
        self.client.force_authenticate(self.tenant_user)

        response = self.client.get("/api/v1/tenant-portal/leases/")
        overview = self.client.get("/api/v1/tenant-portal/overview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertNotEqual(response.data[0]["id"], str(draft.id))
        self.assertEqual(response.data[0]["status"], Lease.Status.ACTIVE)
        self.assertEqual(len(overview.data["profiles"]), 1)
        self.assertEqual(
            overview.data["profiles"][0]["house"]["name"],
            "Maison Riviera",
        )

    def test_account_profile_exposes_available_spaces(self):
        self.client.force_authenticate(self.tenant_user)
        tenant_response = self.client.get("/api/v1/auth/me/")
        self.client.force_authenticate(self.owner)
        owner_response = self.client.get("/api/v1/auth/me/")

        self.assertTrue(tenant_response.data["user"]["has_tenant_access"])
        self.assertFalse(tenant_response.data["user"]["has_owner_access"])
        self.assertTrue(owner_response.data["user"]["has_owner_access"])
        self.assertFalse(owner_response.data["user"]["has_tenant_access"])

    def test_tenant_lists_charges_payments_and_documents(self):
        self.client.force_authenticate(self.tenant_user)

        charges = self.client.get("/api/v1/tenant-portal/charges/")
        payments = self.client.get("/api/v1/tenant-portal/payments/")
        documents = self.client.get("/api/v1/tenant-portal/documents/")

        self.assertEqual(len(charges.data), 1)
        self.assertEqual(charges.data[0]["balance_due"], "65000.00")
        self.assertEqual(len(payments.data), 1)
        self.assertEqual(payments.data[0]["id"], str(self.payment.id))
        self.assertEqual(len(documents.data), 1)
        self.assertEqual(
            documents.data[0]["document_type"],
            RentalDocument.Type.PAYMENT_RECEIPT,
        )

    def test_tenant_confirms_then_disputes_own_payment(self):
        self.client.force_authenticate(self.tenant_user)

        confirmed = self.client.post(
            f"/api/v1/tenant-portal/payments/{self.payment.id}/confirm/",
            {},
            format="json",
        )
        disputed = self.client.post(
            f"/api/v1/tenant-portal/payments/{self.payment.id}/dispute/",
            {"reason": "Le montant remis était différent."},
            format="json",
        )

        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        self.assertEqual(
            confirmed.data["status"],
            Payment.Status.CONFIRMED_BY_TENANT,
        )
        self.assertEqual(
            disputed.data["status"],
            Payment.Status.DISPUTED_BY_TENANT,
        )
        self.assertEqual(
            disputed.data["events"][-1]["reason"],
            "Le montant remis était différent.",
        )

    def test_dispute_requires_reason(self):
        self.client.force_authenticate(self.tenant_user)

        response = self.client.post(
            f"/api/v1/tenant-portal/payments/{self.payment.id}/dispute/",
            {"reason": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)

    def test_outsider_cannot_access_or_answer_payment(self):
        self.client.force_authenticate(self.outsider)

        overview = self.client.get("/api/v1/tenant-portal/overview/")
        payments = self.client.get("/api/v1/tenant-portal/payments/")
        confirm = self.client.post(
            f"/api/v1/tenant-portal/payments/{self.payment.id}/confirm/",
            {},
            format="json",
        )

        self.assertFalse(overview.data["has_profile"])
        self.assertEqual(payments.data, [])
        self.assertEqual(confirm.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_downloads_own_pdf_but_outsider_cannot(self):
        document = self.payment.rental_documents.get()
        self.client.force_authenticate(self.tenant_user)
        allowed = self.client.get(
            f"/api/v1/tenant-portal/documents/{document.id}/pdf/"
        )
        self.client.force_authenticate(self.outsider)
        denied = self.client.get(
            f"/api/v1/tenant-portal/documents/{document.id}/pdf/"
        )

        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed["Content-Type"], "application/pdf")
        self.assertTrue(allowed.content.startswith(b"%PDF-"))
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_blocked_tenant_loses_portal_access(self):
        self.tenant.status = Tenant.Status.BLOCKED
        self.tenant.save(update_fields=["status"])
        self.client.force_authenticate(self.tenant_user)

        overview = self.client.get("/api/v1/tenant-portal/overview/")
        payments = self.client.get("/api/v1/tenant-portal/payments/")

        self.assertFalse(overview.data["has_profile"])
        self.assertEqual(payments.data, [])
