from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from modules.leases.models import Lease
from modules.leases.selectors import manageable_properties_for

from ..models import MaintenanceIncident
from ..selectors import (
    owner_visible_incidents_for,
    tenant_visible_incidents_for,
)
from ..services import (
    CreateIncidentData,
    add_incident_comment,
    change_incident_status_by_owner,
    create_incident,
    respond_to_resolution_by_tenant,
)
from .serializers import (
    ChangeMaintenanceStatusSerializer,
    CreateMaintenanceIncidentSerializer,
    MaintenanceCommentSerializer,
    MaintenanceIncidentSerializer,
    TenantMaintenanceResponseSerializer,
)


def _raise_api_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


def _incident_queryset(queryset):
    return queryset.select_related(
        "property",
        "lease",
        "tenant",
        "reported_by",
    ).prefetch_related("events__actor")


class MaintenanceIncidentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = _incident_queryset(
            owner_visible_incidents_for(self.request.user)
        )
        house_id = self.request.query_params.get("house_id")
        status_filter = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        if house_id:
            queryset = queryset.filter(property_id=house_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if priority:
            queryset = queryset.filter(priority=priority)
        return queryset

    def get_serializer_class(self):
        return {
            "create": CreateMaintenanceIncidentSerializer,
            "set_status": ChangeMaintenanceStatusSerializer,
            "comment": MaintenanceCommentSerializer,
        }.get(self.action, MaintenanceIncidentSerializer)

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        lease = get_object_or_404(
            Lease.objects.select_related("property", "tenant"),
            id=values["lease_id"],
            property__in=manageable_properties_for(request.user),
        )
        try:
            incident = create_incident(
                actor=request.user,
                lease=lease,
                data=CreateIncidentData(
                    title=values["title"],
                    description=values["description"],
                    category=values["category"],
                    priority=values.get(
                        "priority",
                        MaintenanceIncident.Priority.NORMAL,
                    ),
                    occurred_at=values.get("occurred_at"),
                ),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        incident = self.get_queryset().get(id=incident.id)
        return Response(
            MaintenanceIncidentSerializer(incident).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request: Request, pk=None) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            incident = change_incident_status_by_owner(
                actor=request.user,
                incident=self.get_object(),
                target_status=serializer.validated_data["status"],
                message=serializer.validated_data.get("message", ""),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        incident = self.get_queryset().get(id=incident.id)
        return Response(MaintenanceIncidentSerializer(incident).data)

    @action(detail=True, methods=["post"])
    def comment(self, request: Request, pk=None) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            add_incident_comment(
                actor=request.user,
                incident=self.get_object(),
                message=serializer.validated_data["message"],
                as_tenant=False,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        incident = self.get_queryset().get(id=pk)
        return Response(MaintenanceIncidentSerializer(incident).data)


class TenantMaintenanceIncidentListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return _incident_queryset(
            tenant_visible_incidents_for(self.request.user)
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateMaintenanceIncidentSerializer
        return MaintenanceIncidentSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        lease = get_object_or_404(
            Lease.objects.select_related("property", "tenant"),
            id=values["lease_id"],
            status=Lease.Status.ACTIVE,
            tenant__linked_user=request.user,
        )
        try:
            incident = create_incident(
                actor=request.user,
                lease=lease,
                data=CreateIncidentData(
                    title=values["title"],
                    description=values["description"],
                    category=values["category"],
                    priority=values.get(
                        "priority",
                        MaintenanceIncident.Priority.NORMAL,
                    ),
                    occurred_at=values.get("occurred_at"),
                ),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        incident = self.get_queryset().get(id=incident.id)
        return Response(
            MaintenanceIncidentSerializer(incident).data,
            status=status.HTTP_201_CREATED,
        )


class TenantMaintenanceCommentView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = MaintenanceCommentSerializer

    def post(self, request: Request, incident_id) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = get_object_or_404(
            tenant_visible_incidents_for(request.user),
            id=incident_id,
        )
        try:
            add_incident_comment(
                actor=request.user,
                incident=incident,
                message=serializer.validated_data["message"],
                as_tenant=True,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        incident = _incident_queryset(
            tenant_visible_incidents_for(request.user)
        ).get(id=incident_id)
        return Response(MaintenanceIncidentSerializer(incident).data)


class TenantMaintenanceResponseView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TenantMaintenanceResponseSerializer

    def post(self, request: Request, incident_id) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = get_object_or_404(
            tenant_visible_incidents_for(request.user),
            id=incident_id,
        )
        try:
            incident = respond_to_resolution_by_tenant(
                actor=request.user,
                incident=incident,
                action=serializer.validated_data["action"],
                message=serializer.validated_data.get("message", ""),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        incident = _incident_queryset(
            tenant_visible_incidents_for(request.user)
        ).get(id=incident.id)
        return Response(MaintenanceIncidentSerializer(incident).data)
