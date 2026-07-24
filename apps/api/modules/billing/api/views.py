from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from modules.leases.models import Lease
from modules.leases.selectors import manageable_properties_for
from config.pagination import LargeListPagination

from ..selectors import visible_obligations_for, visible_rent_charges_for
from ..services import generate_monthly_charges, prepare_payment_obligations
from .serializers import (
    GenerateRentChargesSerializer,
    PreparePaymentObligationsSerializer,
    RentChargeSerializer,
)


def _raise_api_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


def _month_start(value: str, field: str) -> date:
    try:
        return date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise ValidationError(
            {field: "Utilisez le format AAAA-MM."}
        ) from exc


class RentChargeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    serializer_class = RentChargeSerializer
    pagination_class = LargeListPagination

    def get_queryset(self):
        queryset = visible_rent_charges_for(self.request.user).select_related(
            "lease__property", "lease__tenant"
        )
        house_id = self.request.query_params.get("house_id")
        lease_id = self.request.query_params.get("lease_id")
        period = self.request.query_params.get("period")
        period_from = self.request.query_params.get("period_from")
        period_to = self.request.query_params.get("period_to")
        if house_id:
            queryset = queryset.filter(lease__property_id=house_id)
        if lease_id:
            queryset = queryset.filter(lease_id=lease_id)
        if period:
            try:
                year, month = (int(part) for part in period.split("-"))
            except (TypeError, ValueError):
                return queryset.none()
            queryset = queryset.filter(period_start__year=year, period_start__month=month)
        if period_from:
            queryset = queryset.filter(
                period_start__gte=_month_start(period_from, "period_from")
            )
        if period_to:
            queryset = queryset.filter(
                period_start__lte=_month_start(period_to, "period_to")
            )
        return queryset

    @action(detail=False, methods=["post"])
    def generate(self, request: Request) -> Response:
        input_serializer = GenerateRentChargesSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        summary = generate_monthly_charges(
            actor=request.user,
            period_start=input_serializer.validated_data["period"],
            today=timezone.localdate(),
        )
        return Response(
            {
                "created": summary.created,
                "existing": summary.existing,
                "charges": RentChargeSerializer(summary.charges, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class LeaseObligationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Vue unifiée des loyers et cautions utilisée pour les encaissements."""

    permission_classes = (IsAuthenticated,)
    serializer_class = RentChargeSerializer
    pagination_class = LargeListPagination

    def get_queryset(self):
        queryset = visible_obligations_for(self.request.user).select_related(
            "lease__property", "lease__tenant"
        )
        lease_id = self.request.query_params.get("lease_id")
        unpaid_only = self.request.query_params.get("unpaid_only")
        if lease_id:
            queryset = queryset.filter(lease_id=lease_id)
        if unpaid_only in {"1", "true", "yes"}:
            queryset = queryset.exclude(status__in=("PAID", "CANCELLED"))
        return queryset.order_by("lease_id", "period_start", "charge_type")

    @action(detail=False, methods=["post"], url_path="prepare-payment")
    def prepare_payment(self, request: Request) -> Response:
        serializer = PreparePaymentObligationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        manageable_property_ids = manageable_properties_for(request.user).values_list(
            "id", flat=True
        )
        lease = get_object_or_404(
            Lease.objects.select_related("property", "tenant"),
            id=values["lease_id"],
            property_id__in=manageable_property_ids,
        )
        try:
            result = prepare_payment_obligations(
                actor=request.user,
                lease=lease,
                period_start=values["period_start"],
                period_end=values["period_end"],
                include_security_deposit=values["include_security_deposit"],
                today=timezone.localdate(),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(
            {
                "created": result.created,
                "existing": result.existing,
                "obligations": RentChargeSerializer(
                    result.obligations, many=True
                ).data,
            },
            status=status.HTTP_200_OK,
        )
