"""Matrice IDOR cross-tenant : quittances/documents et notifications (deliveries)."""

from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.tests.idor_fixtures import make_estate, make_landlord


class EstateIdorBase(APITestCase):
    def setUp(self):
        self.landlord_a = make_landlord("+2250700001601")
        self.landlord_b = make_landlord("+2250700001602")
        self.estate_b = make_estate(
            owner=self.landlord_b,
            name="Villa B",
            tenant_phone="+2250500001602",
            coowner_phone="+2250100001602",
        )
        self.client.force_authenticate(self.landlord_a)


class RentalDocumentIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_document_of_b(self):
        response = self.client.get(f"/api/v1/documents/{self.estate_b.receipt.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_download_pdf_of_b(self):
        response = self.client.get(f"/api/v1/documents/{self.estate_b.receipt.id}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_share_document_of_b(self):
        response = self.client.post(
            f"/api/v1/documents/{self.estate_b.receipt.id}/share/",
            {"channels": ["SMS"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_manual_share_document_of_b(self):
        response = self.client.post(
            f"/api/v1/documents/{self.estate_b.receipt.id}/manual-share/",
            {"channel": "SMS"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_update_document_of_b(self):
        response = self.client.patch(
            f"/api/v1/documents/{self.estate_b.receipt.id}/",
            {"status": "VOIDED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_list_excludes_documents_of_b(self):
        response = self.client.get("/api/v1/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [str(d["id"]) for d in response.data["results"]]
        self.assertNotIn(str(self.estate_b.receipt.id), ids)
        self.assertNotIn(str(self.estate_b.rent_receipt.id), ids)


class NotificationDeliveryIdorTests(EstateIdorBase):
    def test_a_list_excludes_deliveries_of_b(self):
        response = self.client.get("/api/v1/notification-deliveries/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.delivery.id),
            [str(d["id"]) for d in response.data["results"]],
        )

    def test_a_filter_by_document_of_b_is_empty(self):
        response = self.client.get(
            f"/api/v1/notification-deliveries/?document_id={self.estate_b.receipt.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_a_filter_by_charge_of_b_is_empty(self):
        response = self.client.get(
            f"/api/v1/notification-deliveries/?rent_charge_id={self.estate_b.charge.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_deliveries_do_not_expose_message_body_or_otp(self):
        response = self.client.get("/api/v1/notification-deliveries/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for delivery in response.data["results"]:
            self.assertNotIn("body", delivery)
            self.assertNotIn("subject", delivery)
            self.assertNotIn("code", delivery)
