from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from ..models import Ownership, Property
from ..selectors import (
    co_owner_invitations_for,
    manageable_co_ownerships_for,
    primary_owned_properties_for,
)
from ..services import (
    CreateHouseData,
    InviteCoOwnerData,
    UpdateCoOwnerData,
    create_house,
    invite_coowner,
    remove_coowner,
    revoke_coowner_invitation,
    update_coowner,
)
from modules.subscriptions.services import FeatureDenied, HouseLimitReached
from .serializers import (
    CoOwnerInvitationSerializer,
    CoOwnerSerializer,
    CreateCoOwnerInvitationSerializer,
    CreateHouseSerializer,
    HouseSerializer,
    UpdateCoOwnerSerializer,
)


def _raise_api_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


class HouseViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Cree et consulte uniquement les maisons appartenant a l'utilisateur."""

    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return (
            Property.objects.filter(ownerships__user=self.request.user)
            .prefetch_related("ownerships__user")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "create":
            return CreateHouseSerializer
        return HouseSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        values = input_serializer.validated_data

        try:
            house = create_house(
                owner=request.user,
                data=CreateHouseData(
                    name=values["name"],
                    address=values["address"],
                    city=values["city"],
                    commune=values.get("commune", ""),
                    landmark=values.get("landmark", ""),
                ),
            )
        except HouseLimitReached as exc:
            payload = {
                "detail": str(exc),
                "code": "HOUSE_LIMIT_REACHED",
                "limit": exc.limit,
                "required_plan": exc.next_plan_slug,
            }
            return Response(payload, status=status.HTTP_403_FORBIDDEN)
        output_serializer = HouseSerializer(house, context=self.get_serializer_context())
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class CoOwnerViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Gestion des copropriétaires réservée au propriétaire principal."""

    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = manageable_co_ownerships_for(self.request.user).select_related(
            "property", "user"
        )
        house_id = self.request.query_params.get("house_id")
        if house_id:
            queryset = queryset.filter(property_id=house_id)
        return queryset

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return UpdateCoOwnerSerializer
        return CoOwnerSerializer

    def update(self, request: Request, *args, **kwargs) -> Response:
        ownership = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            ownership = update_coowner(
                actor=request.user,
                ownership=ownership,
                data=UpdateCoOwnerData(
                    ownership_percentage=values.get(
                        "ownership_percentage", ownership.ownership_percentage
                    ),
                    access_level=values.get("access_level", ownership.access_level),
                ),
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(CoOwnerSerializer(ownership).data)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        ownership = self.get_object()
        remove_coowner(actor=request.user, ownership=ownership)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CoOwnerInvitationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = co_owner_invitations_for(self.request.user).select_related(
            "property", "invited_by", "accepted_by"
        )
        house_id = self.request.query_params.get("house_id")
        status_filter = self.request.query_params.get("status")
        if house_id:
            queryset = queryset.filter(property_id=house_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateCoOwnerInvitationSerializer
        return CoOwnerInvitationSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        house = get_object_or_404(
            primary_owned_properties_for(request.user), id=values["house_id"]
        )
        try:
            invitation = invite_coowner(
                actor=request.user,
                property=house,
                data=InviteCoOwnerData(
                    phone=values["phone"],
                    email=values.get("email", ""),
                    ownership_percentage=values.get("ownership_percentage"),
                    access_level=values.get(
                        "access_level", Ownership.AccessLevel.OBSERVER
                    ),
                ),
            )
        except FeatureDenied as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": "FEATURE_NOT_AVAILABLE",
                    "feature": exc.feature,
                    "required_plan": exc.required_plan_slug,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(
            CoOwnerInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk=None) -> Response:
        invitation = self.get_object()
        try:
            invitation = revoke_coowner_invitation(
                actor=request.user, invitation=invitation
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(CoOwnerInvitationSerializer(invitation).data)
