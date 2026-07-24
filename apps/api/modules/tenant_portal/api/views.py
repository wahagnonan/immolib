from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.billing.api.serializers import RentChargeSerializer
from modules.billing.models import RentCharge
from modules.documents.api.serializers import RentalDocumentSerializer
from modules.documents.models import RentalDocument
from modules.documents.pdfs import (
    build_rental_document_pdf,
    rental_document_pdf_filename,
)
from modules.leases.models import Lease
from modules.payments.api.serializers import PaymentSerializer
from modules.payments.models import Payment
from modules.payments.services import (
    confirm_payment_by_tenant,
    dispute_payment_by_tenant,
)

from ..selectors import (
    tenant_documents_for,
    tenant_leases_for,
    tenant_payments_for,
    tenant_profiles_for,
    tenant_rent_charges_for,
)
from .serializers import (
    TenantPaymentDisputeSerializer,
    TenantPortalLeaseSerializer,
    TenantPortalProfileSerializer,
)


def _raise_api_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


def _tenant_for_payment(*, user, payment: Payment):
    tenant_ids = payment.allocations.values_list(
        "rent_charge__lease__tenant_id",
        flat=True,
    )
    return get_object_or_404(
        tenant_profiles_for(user),
        id__in=tenant_ids,
    )


def _payment_response(*, user, payment: Payment) -> Response:
    refreshed = tenant_payments_for(user).get(id=payment.id)
    return Response(PaymentSerializer(refreshed).data, status=status.HTTP_200_OK)


class TenantPortalOverviewView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        profiles = list(tenant_profiles_for(request.user))
        active_leases = list(
            tenant_leases_for(request.user).filter(status=Lease.Status.ACTIVE)
        )
        charges = tenant_rent_charges_for(request.user).exclude(
            status=RentCharge.Status.CANCELLED
        )
        outstanding = list(
            charges.filter(amount_paid__lt=F("amount_due")).order_by(
                "due_date", "period_start"
            )
        )
        balances: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for charge in outstanding:
            balances[charge.currency] += charge.balance_due

        next_charge = outstanding[0] if outstanding else None
        payments = tenant_payments_for(request.user)
        documents = tenant_documents_for(request.user)
        return Response(
            {
                "has_profile": bool(profiles),
                "profiles": TenantPortalProfileSerializer(
                    profiles,
                    many=True,
                ).data,
                "active_leases": TenantPortalLeaseSerializer(
                    active_leases,
                    many=True,
                ).data,
                "next_charge": (
                    RentChargeSerializer(next_charge).data
                    if next_charge is not None
                    else None
                ),
                "balances": [
                    {
                        "currency": currency,
                        "amount": f"{amount:.2f}",
                    }
                    for currency, amount in sorted(balances.items())
                ],
                "overdue_charge_count": charges.filter(
                    status=RentCharge.Status.OVERDUE
                ).count(),
                "payment_to_review_count": payments.filter(
                    status=Payment.Status.RECORDED_BY_OWNER
                ).count(),
                "document_count": documents.filter(
                    status=RentalDocument.Status.ACTIVE
                ).count(),
            }
        )


class TenantPortalLeaseListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TenantPortalLeaseSerializer

    def get_queryset(self):
        queryset = tenant_leases_for(self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class TenantPortalChargeListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = RentChargeSerializer

    def get_queryset(self):
        queryset = tenant_rent_charges_for(self.request.user)
        lease_id = self.request.query_params.get("lease_id")
        status_filter = self.request.query_params.get("status")
        if lease_id:
            queryset = queryset.filter(lease_id=lease_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class TenantPortalPaymentListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PaymentSerializer

    def get_queryset(self):
        queryset = tenant_payments_for(self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class TenantPortalPaymentConfirmView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request, payment_id) -> Response:
        payment = get_object_or_404(
            tenant_payments_for(request.user),
            id=payment_id,
        )
        tenant = _tenant_for_payment(user=request.user, payment=payment)
        try:
            payment = confirm_payment_by_tenant(
                tenant=tenant,
                payment=payment,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return _payment_response(user=request.user, payment=payment)


class TenantPortalPaymentDisputeView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request, payment_id) -> Response:
        serializer = TenantPaymentDisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = get_object_or_404(
            tenant_payments_for(request.user),
            id=payment_id,
        )
        tenant = _tenant_for_payment(user=request.user, payment=payment)
        try:
            payment = dispute_payment_by_tenant(
                tenant=tenant,
                payment=payment,
                reason=serializer.validated_data["reason"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return _payment_response(user=request.user, payment=payment)


class TenantPortalDocumentListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = RentalDocumentSerializer

    def get_queryset(self):
        queryset = tenant_documents_for(self.request.user)
        document_type = self.request.query_params.get("document_type")
        status_filter = self.request.query_params.get("status")
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class TenantPortalDocumentPdfView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, document_id) -> HttpResponse:
        document = get_object_or_404(
            tenant_documents_for(request.user),
            id=document_id,
        )
        content = build_rental_document_pdf(document)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{rental_document_pdf_filename(document)}"'
        )
        response["Content-Length"] = str(len(content))
        response["Cache-Control"] = "private, no-store"
        return response
