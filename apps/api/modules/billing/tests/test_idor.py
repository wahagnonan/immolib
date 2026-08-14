"""Matrice IDOR cross-tenant : echeances (rent-charges) et obligations."""

from rest_framework import status
from rest_framework.test import APITestCase

from modules.admin_panel.tests.idor_fixtures import make_estate, make_landlord


class EstateIdorBase(APITestCase):
    def setUp(self):
        self.landlord_a = make_landlord("+2250700001401")
        self.landlord_b = make_landlord("+2250700001402")
        self.estate_b = make_estate(
            owner=self.landlord_b,
            name="Villa B",
            tenant_phone="+2250500001402",
            coowner_phone="+2250100001402",
        )
        self.client.force_authenticate(self.landlord_a)


class RentChargeIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_charge_of_b(self):
        response = self.client.get(f"/api/v1/rent-charges/{self.estate_b.charge.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_update_charge_of_b(self):
        response = self.client.patch(
            f"/api/v1/rent-charges/{self.estate_b.charge.id}/",
            {"amount_due": "1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_list_excludes_charges_of_b(self):
        response = self.client.get("/api/v1/rent-charges/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.charge.id), [str(c["id"]) for c in response.data["results"]]
        )

    def test_a_list_with_lease_filter_of_b_is_empty(self):
        response = self.client.get(
            f"/api/v1/rent-charges/?lease_id={self.estate_b.lease.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])


class LeaseObligationIdorTests(EstateIdorBase):
    def test_a_cannot_retrieve_obligation_of_b(self):
        response = self.client.get(
            f"/api/v1/lease-obligations/{self.estate_b.charge.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_cannot_prepare_payment_for_lease_of_b(self):
        response = self.client.post(
            "/api/v1/lease-obligations/prepare-payment/",
            {
                "lease_id": str(self.estate_b.lease.id),
                "period_start": "2026-10",
                "period_end": "2026-10",
                "include_security_deposit": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_list_obligations_excludes_those_of_b(self):
        response = self.client.get("/api/v1/lease-obligations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(self.estate_b.charge.id),
            [str(o["id"]) for o in response.data["results"]],
        )
