"""Matrice IDOR cross-tenant : espace locataire (portail)."""

from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.tests.idor_fixtures import make_estate, make_landlord


class TenantPortalIdorBase(APITestCase):
    def setUp(self):
        self.landlord_a = make_landlord("+2250700001701")
        self.landlord_b = make_landlord("+2250700001702")
        self.estate_a = make_estate(
            owner=self.landlord_a,
            name="Villa A",
            tenant_phone="+2250500001701",
            coowner_phone="+2250100001701",
        )
        self.estate_b = make_estate(
            owner=self.landlord_b,
            name="Villa B",
            tenant_phone="+2250500001702",
            coowner_phone="+2250100001702",
        )
        self.client.force_authenticate(self.estate_a.tenant_user)


class TenantPortalOverviewIdorTests(TenantPortalIdorBase):
    def test_overview_excludes_data_of_other_tenant(self):
        response = self.client.get("/api/v1/tenant-portal/overview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile_ids = [p["id"] for p in response.data["profiles"]]
        self.assertIn(str(self.estate_a.tenant.id), profile_ids)
        self.assertNotIn(str(self.estate_b.tenant.id), profile_ids)


class TenantPortalLeaseIdorTests(TenantPortalIdorBase):
    def test_leases_list_only_contains_own_leases(self):
        response = self.client.get("/api/v1/tenant-portal/leases/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [str(l["id"]) for l in response.data["results"]]
        self.assertIn(str(self.estate_a.lease.id), ids)
        self.assertNotIn(str(self.estate_b.lease.id), ids)


class TenantPortalChargeIdorTests(TenantPortalIdorBase):
    def test_charges_list_only_contains_own_charges(self):
        response = self.client.get("/api/v1/tenant-portal/charges/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [str(c["id"]) for c in response.data["results"]]
        self.assertIn(str(self.estate_a.charge.id), ids)
        self.assertNotIn(str(self.estate_b.charge.id), ids)

    def test_charges_filtered_by_foreign_lease_are_empty(self):
        response = self.client.get(
            f"/api/v1/tenant-portal/charges/?lease_id={self.estate_b.lease.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])


class TenantPortalPaymentIdorTests(TenantPortalIdorBase):
    def test_payments_list_only_contains_own_payments(self):
        response = self.client.get("/api/v1/tenant-portal/payments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [str(p["id"]) for p in response.data["results"]]
        self.assertIn(str(self.estate_a.payment.id), ids)
        self.assertNotIn(str(self.estate_b.payment.id), ids)

    def test_cannot_confirm_payment_of_other_tenant(self):
        response = self.client.post(
            f"/api/v1/tenant-portal/payments/{self.estate_b.payment.id}/confirm/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_dispute_payment_of_other_tenant(self):
        response = self.client.post(
            f"/api/v1/tenant-portal/payments/{self.estate_b.payment.id}/dispute/",
            {"reason": "Je ne reconnais pas ce paiement"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TenantPortalDocumentIdorTests(TenantPortalIdorBase):
    def test_documents_list_only_contains_own_documents(self):
        response = self.client.get("/api/v1/tenant-portal/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [str(d["id"]) for d in response.data["results"]]
        self.assertIn(str(self.estate_a.receipt.id), ids)
        self.assertNotIn(str(self.estate_b.receipt.id), ids)

    def test_cannot_download_pdf_of_other_tenant(self):
        response = self.client.get(
            f"/api/v1/tenant-portal/documents/{self.estate_b.receipt.id}/pdf/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
