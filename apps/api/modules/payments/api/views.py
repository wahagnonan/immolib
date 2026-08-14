from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from modules.billing.models import RentCharge
from modules.leases.selectors import manageable_properties_for
from config.pagination import LargeListPagination

from ..models import PaymentMethodAccount
from ..selectors import (
    payment_method_accounts_for,
    payment_requests_for_owner,
    payment_requests_for_tenant,
    visible_payments_for,
)
from ..services import (
    InitiatePaymentRequestData,
    PaymentAllocationData,
    RecordOfflinePaymentData,
    SettleSecurityDepositData,
    cancel_payment,
    cancel_payment_request,
    confirm_payment_request,
    initiate_payment_request,
    record_allocated_offline_payment,
    refuse_payment_request,
    settle_security_deposit,
)
from .serializers import (
    CancelPaymentSerializer,
    PaymentMethodAccountCreateSerializer,
    PaymentMethodAccountSerializer,
    PaymentRequestCancelSerializer,
    PaymentRequestConfirmSerializer,
    PaymentRequestCreateSerializer,
    PaymentRequestRefuseSerializer,
    PaymentRequestSerializer,
    PaymentSerializer,
    RecordOfflinePaymentSerializer,
    SecurityDepositSerializer,
    SettleSecurityDepositSerializer,
)


def _raise_api_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


def _date_filter(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field: _("Utilisez le format AAAA-MM-JJ.")}) from exc


class PaymentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    pagination_class = LargeListPagination

    def get_queryset(self):
        queryset = visible_payments_for(self.request.user).prefetch_related(
            "allocations__rent_charge", "events"
        )
        rent_charge_id = self.request.query_params.get("rent_charge_id")
        received_from = self.request.query_params.get("received_from")
        received_to = self.request.query_params.get("received_to")
        if rent_charge_id:
            queryset = queryset.filter(allocations__rent_charge_id=rent_charge_id)
        if received_from:
            queryset = queryset.filter(
                received_at__date__gte=_date_filter(
                    received_from,
                    "received_from",
                )
            )
        if received_to:
            queryset = queryset.filter(
                received_at__date__lte=_date_filter(received_to, "received_to")
            )
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return RecordOfflinePaymentSerializer
        if self.action == "cancel":
            return CancelPaymentSerializer
        return PaymentSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        values = input_serializer.validated_data
        manageable_property_ids = manageable_properties_for(request.user).values_list(
            "id", flat=True
        )
        requested_allocations = values.get("allocations")
        if requested_allocations:
            obligation_ids = [item["obligation_id"] for item in requested_allocations]
            obligations = {
                item.id: item
                for item in RentCharge.objects.select_related(
                    "lease__property", "lease__tenant"
                ).filter(
                    id__in=obligation_ids,
                    lease__property_id__in=manageable_property_ids,
                )
            }
            if len(obligations) != len(obligation_ids):
                raise ValidationError(
                    {"allocations": _("Une obligation est introuvable ou inaccessible.")}
                )
            allocations = tuple(
                PaymentAllocationData(
                    charge=obligations[item["obligation_id"]],
                    amount=item["amount"],
                )
                for item in requested_allocations
            )
        else:
            charge = get_object_or_404(
                RentCharge.objects.select_related("lease__property", "lease__tenant"),
                id=values["rent_charge_id"],
                lease__property_id__in=manageable_property_ids,
            )
            allocations = (
                PaymentAllocationData(charge=charge, amount=values["amount"]),
            )

        try:
            result = record_allocated_offline_payment(
                actor=request.user,
                allocations=allocations,
                data=RecordOfflinePaymentData(
                    amount=values["amount"],
                    method=values["method"],
                    received_at=values.get("received_at", timezone.now()),
                    external_reference=values.get("external_reference", ""),
                    note=values.get("note", ""),
                    idempotency_key=values["idempotency_key"],
                ),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_status = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        payment = self.get_queryset().get(id=result.payment.id)
        return Response(PaymentSerializer(payment).data, status=response_status)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk=None) -> Response:
        payment = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            payment = cancel_payment(
                actor=request.user,
                payment=payment,
                reason=input_serializer.validated_data["reason"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        payment = self.get_queryset().get(id=payment.id)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class SecurityDepositViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    serializer_class = SecurityDepositSerializer
    pagination_class = LargeListPagination

    def get_queryset(self):
        manageable_property_ids = manageable_properties_for(
            self.request.user
        ).values_list("id", flat=True)
        queryset = (
            RentCharge.objects.filter(
                charge_type=RentCharge.Type.SECURITY_DEPOSIT,
                lease__property_id__in=manageable_property_ids,
            )
            .select_related("lease__property", "lease__tenant")
            .prefetch_related(
                "security_deposit_movements__target_rent_charge",
                "security_deposit_movements__rental_documents",
            )
        )
        if self.request.query_params.get("held_only") in {"1", "true", "yes"}:
            queryset = queryset.filter(amount_paid__gt=0).exclude(
                amount_released__gte=F("amount_paid")
            )
        return queryset

    def get_serializer_class(self):
        if self.action == "settle":
            return SettleSecurityDepositSerializer
        return SecurityDepositSerializer

    @action(detail=True, methods=["post"])
    def settle(self, request: Request, pk=None) -> Response:
        deposit = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        values = input_serializer.validated_data
        target = None
        if values.get("target_rent_charge_id"):
            target = get_object_or_404(
                RentCharge,
                id=values["target_rent_charge_id"],
                lease__property_id__in=manageable_properties_for(
                    request.user
                ).values_list("id", flat=True),
            )
        try:
            result = settle_security_deposit(
                actor=request.user,
                deposit=deposit,
                data=SettleSecurityDepositData(
                    movement_type=values["movement_type"],
                    amount=values["amount"],
                    reason=values.get("reason", ""),
                    agreement_confirmed=values.get("agreement_confirmed", False),
                    agreement_reference=values.get("agreement_reference", ""),
                    target_rent_charge=target,
                    idempotency_key=values["idempotency_key"],
                    occurred_at=values.get("occurred_at", timezone.now()),
                ),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        deposit = self.get_queryset().get(id=deposit.id)
        response_status = (
            status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        )
        return Response(
            SecurityDepositSerializer(deposit).data,
            status=response_status,
        )


class PaymentMethodAccountViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return payment_method_accounts_for(self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentMethodAccountCreateSerializer
        return PaymentMethodAccountSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        values = input_serializer.validated_data
        if values.get("is_default"):
            self.get_queryset().update(is_default=False)
        account = PaymentMethodAccount(
            owner=request.user,
            operator=values["operator"],
            account_identifier=values["account_identifier"].strip(),
            account_holder=values.get("account_holder", "").strip(),
            is_default=values.get("is_default", False),
        )
        try:
            account.full_clean()
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        account.save()
        if not self.get_queryset().filter(is_default=True).exists():
            account.is_default = True
            account.save(update_fields=["is_default", "updated_at"])
        return Response(
            PaymentMethodAccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request: Request, pk=None) -> Response:
        account = self.get_object()
        account.delete()
        if not self.get_queryset().filter(is_default=True).exists():
            first = self.get_queryset().first()
            if first:
                first.is_default = True
                first.save(update_fields=["is_default", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="make-default")
    def make_default(self, request: Request, pk=None) -> Response:
        account = self.get_object()
        self.get_queryset().update(is_default=False)
        account.is_default = True
        account.save(update_fields=["is_default", "updated_at"])
        return Response(
            PaymentMethodAccountSerializer(account).data,
            status=status.HTTP_200_OK,
        )


class PaymentRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    pagination_class = LargeListPagination

    def get_queryset(self):
        queryset = payment_requests_for_tenant(self.request.user)
        if self.action in ("list", "confirm", "refuse"):
            queryset = payment_requests_for_owner(self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.select_related(
            "rent_charge__lease__tenant",
            "rent_charge__lease__property",
            "method_account",
            "payee",
            "requested_by",
        )

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentRequestCreateSerializer
        if self.action == "confirm":
            return PaymentRequestConfirmSerializer
        if self.action == "refuse":
            return PaymentRequestRefuseSerializer
        if self.action == "cancel":
            return PaymentRequestCancelSerializer
        return PaymentRequestSerializer

    @action(detail=False, methods=["get"])
    def my(self, request: Request) -> Response:
        queryset = payment_requests_for_tenant(request.user).select_related(
            "rent_charge__lease__tenant",
            "rent_charge__lease__property",
            "method_account",
            "payee",
            "requested_by",
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return Response(
            PaymentRequestSerializer(queryset, many=True).data,
            status=status.HTTP_200_OK,
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        values = input_serializer.validated_data
        try:
            payment_request = initiate_payment_request(
                tenant=request.user,
                data=InitiatePaymentRequestData(
                    rent_charge_id=values["rent_charge_id"],
                    amount=values["amount"],
                    operator=values["operator"],
                    method_account_id=values.get("method_account_id"),
                    note=values.get("note", ""),
                ),
            )
        except PermissionDenied as exc:
            # Ne pas distinguer une echeance etrangere d'une echeance
            # inexistante : eviter l'oracle d'existence cross-tenant.
            raise NotFound("Cette échéance est introuvable.") from exc
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        payment_request = self.get_queryset().get(id=payment_request.id)
        return Response(
            PaymentRequestSerializer(payment_request).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request: Request, pk=None) -> Response:
        payment_request = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        values = input_serializer.validated_data
        try:
            payment_request = confirm_payment_request(
                owner=request.user,
                payment_request=payment_request,
                received_amount=values.get("received_amount"),
                note=values.get("note", ""),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        payment_request = self.get_queryset().get(id=payment_request.id)
        return Response(
            PaymentRequestSerializer(payment_request).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def refuse(self, request: Request, pk=None) -> Response:
        payment_request = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            payment_request = refuse_payment_request(
                owner=request.user,
                payment_request=payment_request,
                reason=input_serializer.validated_data["reason"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        payment_request = self.get_queryset().get(id=payment_request.id)
        return Response(
            PaymentRequestSerializer(payment_request).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk=None) -> Response:
        payment_request = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            payment_request = cancel_payment_request(
                tenant=request.user,
                payment_request=payment_request,
                reason=input_serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        payment_request = self.get_queryset().get(id=payment_request.id)
        return Response(
            PaymentRequestSerializer(payment_request).data,
            status=status.HTTP_200_OK,
        )
