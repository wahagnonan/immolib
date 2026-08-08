from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from modules.billing.services import generate_monthly_charges
from modules.documents.models import NotificationDelivery, RentalDocument
from modules.leases.models import Tenant
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house

from ..models import Payment, PaymentRequest


class PaymentRequestApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        from django.utils import timezone

        self.owner = user_model.objects.create_user(
            phone="+2250700000700", password="password"
        )
        self.outsider = user_model.objects.create_user(
            phone="+2250700000701", password="password"
        )
        self.tenant_user = user_model.objects.create_user(
            phone="+2250700000702", password="password"
        )
        for account in (self.owner, self.outsider, self.tenant_user):
            account.email = f"{account.phone}@example.com"
            account.email_verified_at = timezone.now()
            account.save(update_fields=["email", "email_verified_at", "updated_at"])
        house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Yopougon", address="Camp Militaire", city="Abidjan"
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=house,
            data=CreateTenantData(
                full_name="Awa Koné", phone="+2250500000700"
            ),
        )
        tenant.linked_user = self.tenant_user
        tenant.save(update_fields=["linked_user", "updated_at"])
        self.lease = create_lease(
            actor=self.owner,
            property=house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("80000"),
                due_day=5,
                security_deposit=Decimal("200000"),
            ),
        )
        activate_lease(actor=self.owner, lease=self.lease)
        self.charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]

    def _initiate(self, amount="30000.00", operator="MTN_MOMO"):
        return self.client.post(
            "/api/v1/payment-requests/",
            {
                "rent_charge_id": str(self.charge.id),
                "amount": amount,
                "operator": operator,
            },
            format="json",
        )

    def test_tenant_initiates_payment_request(self):
        self.client.force_authenticate(self.tenant_user)

        response = self._initiate()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], PaymentRequest.Status.PENDING)
        self.assertTrue(response.data["reference"].startswith("PR-"))
        self.assertEqual(response.data["amount"], "30000.00")
        self.assertEqual(response.data["house_name"], "Maison Yopougon")
        self.assertEqual(response.data["tenant_name"], "Awa Koné")
        self.assertEqual(response.data["payee_phone"], self.owner.phone)
        self.assertEqual(
            NotificationDelivery.objects.filter(
                kind=NotificationDelivery.Kind.PAYMENT_REQUEST
            ).count(),
            1,
        )

    def test_tenant_cannot_initiate_beyond_balance(self):
        self.client.force_authenticate(self.tenant_user)

        response = self._initiate(amount="90000.00")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PaymentRequest.objects.count(), 0)

    def test_outsider_cannot_initiate_for_someone_else(self):
        self.client.force_authenticate(self.outsider)

        response = self._initiate()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PaymentRequest.objects.count(), 0)

    def test_only_one_pending_request_per_charge(self):
        self.client.force_authenticate(self.tenant_user)
        self._initiate()

        response = self._initiate(amount="10000.00")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            PaymentRequest.objects.filter(
                rent_charge=self.charge,
                status=PaymentRequest.Status.PENDING,
            ).count(),
            1,
        )

    def test_owner_lists_requests_and_tenant_lists_mine(self):
        self.client.force_authenticate(self.tenant_user)
        self._initiate()

        self.client.force_authenticate(self.owner)
        owner_list = self.client.get("/api/v1/payment-requests/")
        self.assertEqual(owner_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(owner_list.data["results"]), 1)

        self.client.force_authenticate(self.tenant_user)
        my_list = self.client.get("/api/v1/payment-requests/my/")
        self.assertEqual(my_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(my_list.data), 1)

        self.client.force_authenticate(self.outsider)
        outsider_list = self.client.get("/api/v1/payment-requests/")
        self.assertEqual(len(outsider_list.data["results"]), 0)

    def test_owner_confirms_request_and_receipt_is_generated(self):
        self.client.force_authenticate(self.tenant_user)
        created = self._initiate()
        request_id = created.data["id"]

        self.client.force_authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/payment-requests/{request_id}/confirm/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], PaymentRequest.Status.CONFIRMED)
        self.assertEqual(response.data["amount_received"], "30000.00")
        payment = Payment.objects.get(payment_request__id=request_id)
        self.assertEqual(payment.amount, Decimal("30000.00"))
        self.assertEqual(payment.method, Payment.Method.EXTERNAL_MOBILE_MONEY)
        self.assertEqual(payment.status, Payment.Status.RECORDED_BY_OWNER)
        self.assertEqual(self.charge.amount_paid, Decimal("30000.00"))
        self.assertTrue(
            RentalDocument.objects.filter(
                payment=payment,
                status=RentalDocument.Status.ACTIVE,
            ).exists()
        )
        self.assertEqual(
            NotificationDelivery.objects.filter(
                kind=NotificationDelivery.Kind.PAYMENT_CONFIRMED
            ).count(),
            1,
        )

    def test_owner_confirms_with_received_amount(self):
        self.client.force_authenticate(self.tenant_user)
        created = self._initiate()
        request_id = created.data["id"]

        self.client.force_authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/payment-requests/{request_id}/confirm/",
            {"received_amount": "50000.00", "note": "Solde partiel"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["amount_received"], "50000.00")
        self.assertEqual(self.charge.amount_paid, Decimal("50000.00"))

    def test_owner_cannot_confirm_request_of_another_property(self):
        self.client.force_authenticate(self.tenant_user)
        created = self._initiate()
        request_id = created.data["id"]

        self.client.force_authenticate(self.outsider)
        response = self.client.post(
            f"/api/v1/payment-requests/{request_id}/confirm/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_refuses_request(self):
        self.client.force_authenticate(self.tenant_user)
        created = self._initiate()
        request_id = created.data["id"]

        self.client.force_authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/payment-requests/{request_id}/refuse/",
            {"reason": "Je n'ai rien reçu sur mon compte."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], PaymentRequest.Status.NOT_RECEIVED)
        self.assertEqual(Payment.objects.count(), 0)

    def test_refuse_requires_reason(self):
        self.client.force_authenticate(self.tenant_user)
        created = self._initiate()
        request_id = created.data["id"]

        self.client.force_authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/payment-requests/{request_id}/refuse/",
            {"reason": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tenant_cancels_pending_request(self):
        self.client.force_authenticate(self.tenant_user)
        created = self._initiate()
        request_id = created.data["id"]

        response = self.client.post(
            f"/api/v1/payment-requests/{request_id}/cancel/",
            {"reason": "J'ai finalement payé en espèces."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], PaymentRequest.Status.CANCELLED)

    def test_outsider_cannot_cancel_request(self):
        self.client.force_authenticate(self.tenant_user)
        created = self._initiate()
        request_id = created.data["id"]

        self.client.force_authenticate(self.outsider)
        response = self.client.post(
            f"/api/v1/payment-requests/{request_id}/cancel/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PaymentMethodAccountApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000800", password="password"
        )

    def test_owner_creates_default_method(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            "/api/v1/payment-methods/",
            {
                "operator": "MTN_MOMO",
                "account_identifier": "+2250700000800",
                "account_holder": "Koffi Yao",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_default"])
        self.assertEqual(response.data["operator_label"], "MTN Mobile Money")

    def test_duplicate_method_is_rejected(self):
        self.client.force_authenticate(self.owner)
        payload = {
            "operator": "ORANGE_MONEY",
            "account_identifier": "+2250700000801",
        }
        self.client.post("/api/v1/payment-methods/", payload, format="json")

        response = self.client.post(
            "/api/v1/payment-methods/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_make_default_switches_default(self):
        self.client.force_authenticate(self.owner)
        first = self.client.post(
            "/api/v1/payment-methods/",
            {"operator": "MTN_MOMO", "account_identifier": "+2250700000802"},
            format="json",
        ).data
        second = self.client.post(
            "/api/v1/payment-methods/",
            {"operator": "WAVE", "account_identifier": "+2250700000803"},
            format="json",
        ).data

        response = self.client.post(
            f"/api/v1/payment-methods/{first['id']}/make-default/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        listing = self.client.get("/api/v1/payment-methods/").data
        defaults = [item for item in listing if item["is_default"]]
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0]["id"], first["id"])
        self.assertEqual(second["is_default"], False)

    def test_delete_method_falls_back_to_another(self):
        self.client.force_authenticate(self.owner)
        first = self.client.post(
            "/api/v1/payment-methods/",
            {"operator": "MTN_MOMO", "account_identifier": "+2250700000804"},
            format="json",
        ).data
        self.client.post(
            "/api/v1/payment-methods/",
            {"operator": "WAVE", "account_identifier": "+2250700000805"},
            format="json",
        )

        response = self.client.delete(f"/api/v1/payment-methods/{first['id']}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        listing = self.client.get("/api/v1/payment-methods/").data
        self.assertEqual(len(listing), 1)
        self.assertTrue(listing[0]["is_default"])
