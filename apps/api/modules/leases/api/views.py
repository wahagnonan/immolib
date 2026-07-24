from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from ..models import Lease, Tenant, TenantInvitation
from ..selectors import (
    manageable_properties_for,
    visible_leases_for,
    visible_tenants_for,
)
from ..services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    close_lease,
    create_lease,
    create_tenant,
    claim_tenant_invitation,
    create_tenant_invitation,
    resolve_tenant_invitation,
    revoke_tenant_invitation,
    share_tenant_invitation,
)
from .serializers import (
    CreateLeaseSerializer,
    CreateTenantInvitationSerializer,
    CreateTenantSerializer,
    InvitationTokenSerializer,
    LeaseSerializer,
    PublicTenantInvitationSerializer,
    ShareTenantInvitationSerializer,
    TenantInvitationSerializer,
    TenantSerializer,
)


def _raise_api_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


class TenantViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = visible_tenants_for(self.request.user).select_related("property")
        house_id = self.request.query_params.get("house_id")
        if house_id:
            queryset = queryset.filter(property_id=house_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateTenantSerializer
        return TenantSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        values = input_serializer.validated_data
        house = get_object_or_404(
            manageable_properties_for(request.user), id=values["house_id"]
        )

        try:
            tenant = create_tenant(
                actor=request.user,
                property=house,
                data=CreateTenantData(
                    full_name=values["full_name"],
                    phone=values["phone"],
                    email=values.get("email", ""),
                ),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        return Response(TenantSerializer(tenant).data, status=status.HTTP_201_CREATED)


class TenantInvitationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = TenantInvitation.objects.filter(
            tenant__property__in=manageable_properties_for(self.request.user)
        ).select_related(
            "tenant__property",
            "invited_by",
            "claimed_by",
            "accepted_by",
        )
        tenant_id = self.request.query_params.get("tenant_id")
        house_id = self.request.query_params.get("house_id")
        status_filter = self.request.query_params.get("status")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if house_id:
            queryset = queryset.filter(tenant__property_id=house_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_serializer_class(self):
        return {
            "create": CreateTenantInvitationSerializer,
            "share": ShareTenantInvitationSerializer,
        }.get(self.action, TenantInvitationSerializer)

    def create(self, request: Request, *args, **kwargs) -> Response:
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        tenant = get_object_or_404(
            Tenant.objects.filter(
                property__in=manageable_properties_for(request.user)
            ),
            id=input_serializer.validated_data["tenant_id"],
        )
        try:
            invitation = create_tenant_invitation(
                actor=request.user,
                tenant=tenant,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(
            TenantInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def share(self, request: Request, pk=None) -> Response:
        invitation = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            result = share_tenant_invitation(
                actor=request.user,
                invitation=invitation,
                channel=input_serializer.validated_data["channel"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(
            {
                "invitation": TenantInvitationSerializer(result.invitation).data,
                "secure_url": result.secure_url,
                "subject": result.subject,
                "message": result.message,
                "action_url": result.action_url,
                "channel": input_serializer.validated_data["channel"],
                "delivery": (
                    {
                        "id": str(result.delivery.id),
                        "channel": result.delivery.channel,
                        "status": result.delivery.status,
                    }
                    if result.delivery
                    else None
                ),
                "share_event_id": (
                    str(result.share_event.id) if result.share_event else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk=None) -> Response:
        try:
            invitation = revoke_tenant_invitation(
                actor=request.user,
                invitation=self.get_object(),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(TenantInvitationSerializer(invitation).data)


class PublicTenantInvitationViewSet(viewsets.GenericViewSet):
    def get_permissions(self):
        if self.action == "claim":
            return (IsAuthenticated(),)
        return (AllowAny(),)

    def get_serializer_class(self):
        return InvitationTokenSerializer

    @action(detail=False, methods=["post"])
    def preview(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = resolve_tenant_invitation(
                serializer.validated_data["token"]
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(PublicTenantInvitationSerializer(invitation).data)

    @action(detail=False, methods=["post"])
    def claim(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = claim_tenant_invitation(
                token=serializer.validated_data["token"],
                user=request.user,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(PublicTenantInvitationSerializer(invitation).data)


class LeaseViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = visible_leases_for(self.request.user).select_related(
            "property", "tenant"
        )
        house_id = self.request.query_params.get("house_id")
        if house_id:
            queryset = queryset.filter(property_id=house_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateLeaseSerializer
        return LeaseSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        values = input_serializer.validated_data
        house = get_object_or_404(
            manageable_properties_for(request.user), id=values["house_id"]
        )
        tenant = get_object_or_404(
            Tenant.objects.filter(property=house), id=values["tenant_id"]
        )

        try:
            lease = create_lease(
                actor=request.user,
                property=house,
                tenant=tenant,
                data=CreateLeaseData(
                    start_date=values["start_date"],
                    end_date=values.get("end_date"),
                    monthly_rent=values["monthly_rent"],
                    monthly_charges=values.get("monthly_charges", 0),
                    due_day=values["due_day"],
                    security_deposit=values.get("security_deposit", 0),
                    rent_advance=values.get("rent_advance", 0),
                    accepts_mobile_money=values.get("accepts_mobile_money", True),
                    accepts_cash=values.get("accepts_cash", True),
                ),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        return Response(LeaseSerializer(lease).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def activate(self, request: Request, pk=None) -> Response:
        lease = self.get_object()
        try:
            lease = activate_lease(actor=request.user, lease=lease)
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        return Response(LeaseSerializer(lease).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk=None) -> Response:
        lease = self.get_object()
        try:
            lease = close_lease(actor=request.user, lease=lease)
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        return Response(LeaseSerializer(lease).data, status=status.HTTP_200_OK)
