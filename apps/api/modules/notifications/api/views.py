from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services import (
    deactivate_push_subscription,
    preference_for,
    register_push_subscription,
)
from .serializers import (
    NotificationPreferenceSerializer,
    PushSubscriptionInputSerializer,
    PushSubscriptionSerializer,
)


class NotificationPreferenceView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        preference = preference_for(request.user)
        return Response(NotificationPreferenceSerializer(preference).data)

    def patch(self, request: Request) -> Response:
        preference = preference_for(request.user)
        serializer = NotificationPreferenceSerializer(
            preference, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PushSubscriptionView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        subscriptions = request.user.push_subscriptions.filter(is_active=True)
        return Response(PushSubscriptionSerializer(subscriptions, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = PushSubscriptionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = register_push_subscription(
            user=request.user, **serializer.validated_data
        )
        return Response(
            PushSubscriptionSerializer(subscription).data,
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request: Request) -> Response:
        serializer = PushSubscriptionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deactivate_push_subscription(
            user=request.user, token=serializer.validated_data["token"]
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
