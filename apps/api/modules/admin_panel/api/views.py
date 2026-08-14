"""Vues de l'espace admin. Toutes les routes sont protegees par le role
systeme ADMIN et la permission de ressource correspondante."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from config.pagination import LargeListPagination

from .. import services
from ..authentication import AdminSessionAuthentication
from ..models import AuditLog
from ..permissions import Perm, admin_permission
from ..selectors import (
    admin_audit_logs_queryset,
    admin_houses_queryset,
    admin_landlords_queryset,
    admin_notifications_queryset,
    admin_payments_queryset,
    admin_subscriptions_queryset,
    admin_tenants_queryset,
    admin_users_queryset,
)
from .serializers import (
    AdminAuditLogSerializer,
    AdminHouseSerializer,
    AdminNotificationSerializer,
    AdminPaymentSerializer,
    AdminSubscriptionActionSerializer,
    AdminSubscriptionSerializer,
    AdminTenantSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    UserStatusUpdateSerializer,
)


def _query_param(request, name: str, default: str = "") -> str:
    return request.query_params.get(name, default)


class AdminAuthMixin:
    """Authentifie avec un header WWW-Authenticate : les requetes
    anonymes obtiennent 401 au lieu de 403 sur l'espace admin."""

    authentication_classes = (AdminSessionAuthentication,)


class AdminDashboardView(AdminAuthMixin, APIView):
    permission_classes = (admin_permission(Perm.USERS_READ),)

    def get(self, request):
        return Response(services.dashboard_metrics())


class UsersEvolutionView(AdminAuthMixin, APIView):
    permission_classes = (admin_permission(Perm.USERS_READ),)

    def get(self, request):
        period = _query_param(request, "period", "30d")
        if period not in ("7d", "30d", "3m", "12m"):
            raise ValidationError({"period": _("Periode invalide.")})
        return Response(services.users_evolution(period=period))


class RevenueSeriesView(AdminAuthMixin, APIView):
    permission_classes = (admin_permission(Perm.PAYMENTS_READ),)

    def get(self, request):
        period = _query_param(request, "period", "monthly")
        if period not in ("weekly", "monthly", "yearly"):
            raise ValidationError({"period": _("Periode invalide.")})
        return Response(services.revenue_series(period=period))


class HousesEvolutionView(AdminAuthMixin, APIView):
    permission_classes = (admin_permission(Perm.HOUSES_READ),)

    def get(self, request):
        period = _query_param(request, "period", "30d")
        if period not in ("7d", "30d", "3m", "12m"):
            raise ValidationError({"period": _("Periode invalide.")})
        return Response(services.houses_evolution(period=period))


class AdminUserListView(AdminAuthMixin, generics.ListAPIView):
    permission_classes = (admin_permission(Perm.USERS_READ),)
    pagination_class = LargeListPagination
    serializer_class = AdminUserListSerializer

    def get_queryset(self):
        return admin_users_queryset(
            search=_query_param(self.request, "search"),
            role=_query_param(self.request, "role"),
            status=_query_param(self.request, "status"),
            profile=_query_param(self.request, "profile"),
            plan=_query_param(self.request, "plan"),
        )


class AdminUserDetailView(AdminAuthMixin, generics.RetrieveAPIView):
    permission_classes = (admin_permission(Perm.USERS_READ),)
    serializer_class = AdminUserDetailSerializer
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        return (
            admin_users_queryset()
            .filter(id=self.kwargs["user_id"])
            .select_related("subscription__plan")
        )


class AdminUserStatusView(AdminAuthMixin, generics.UpdateAPIView):
    permission_classes = (admin_permission(Perm.USERS_SUSPEND),)
    serializer_class = UserStatusUpdateSerializer
    http_method_names = ("patch", "options", "head")
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        return admin_users_queryset().filter(id=self.kwargs["user_id"])

    def perform_update(self, serializer):
        user = self.get_object()
        is_active = serializer.validated_data["is_active"]
        try:
            services.set_user_active_status(
                user=user,
                is_active=is_active,
                admin=self.request.user,
                request=self.request,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        serializer.instance = user
        serializer.instance.is_active = is_active


class AdminLandlordListView(AdminAuthMixin, generics.ListAPIView):
    permission_classes = (admin_permission(Perm.LANDLORDS_READ),)
    pagination_class = LargeListPagination
    serializer_class = AdminUserListSerializer

    def get_queryset(self):
        return admin_landlords_queryset(
            search=_query_param(self.request, "search"),
            status=_query_param(self.request, "status"),
            plan=_query_param(self.request, "plan"),
        )


class AdminTenantListView(AdminAuthMixin, generics.ListAPIView):
    permission_classes = (admin_permission(Perm.TENANTS_READ),)
    pagination_class = LargeListPagination
    serializer_class = AdminTenantSerializer

    def get_queryset(self):
        return admin_tenants_queryset(
            search=_query_param(self.request, "search"),
            status=_query_param(self.request, "status"),
        )


class AdminHouseListView(AdminAuthMixin, generics.ListAPIView):
    permission_classes = (admin_permission(Perm.HOUSES_READ),)
    pagination_class = LargeListPagination
    serializer_class = AdminHouseSerializer

    def get_queryset(self):
        return admin_houses_queryset(
            search=_query_param(self.request, "search"),
            status=_query_param(self.request, "status"),
            occupancy=_query_param(self.request, "occupancy"),
        )


class AdminSubscriptionListView(AdminAuthMixin, generics.ListAPIView):
    permission_classes = (admin_permission(Perm.SUBSCRIPTIONS_READ),)
    pagination_class = LargeListPagination
    serializer_class = AdminSubscriptionSerializer

    def get_queryset(self):
        return admin_subscriptions_queryset(
            search=_query_param(self.request, "search"),
            plan=_query_param(self.request, "plan"),
            status=_query_param(self.request, "status"),
        )


class AdminSubscriptionActionView(AdminAuthMixin, generics.GenericAPIView):
    permission_classes = (admin_permission(Perm.SUBSCRIPTIONS_UPDATE),)
    serializer_class = AdminSubscriptionActionSerializer
    lookup_url_kwarg = "subscription_id"
    http_method_names = ("patch", "options", "head")

    def get_queryset(self):
        from modules.subscriptions.models import Subscription

        return Subscription.objects.select_related("user", "plan").filter(
            id=self.kwargs["subscription_id"]
        )

    def patch(self, request, *args, **kwargs):
        subscription = self.get_object()
        input_serializer = self.serializer_class(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        try:
            if data["action"] == "change_plan":
                subscription = services.change_plan(
                    subscription=subscription,
                    plan_slug=data["plan_slug"],
                    admin=request.user,
                    request=request,
                )
            elif data["action"] == "extend":
                subscription = services.extend_subscription(
                    subscription=subscription,
                    days=data["days"],
                    admin=request.user,
                    request=request,
                )
            elif data["action"] == "activate":
                subscription = services.activate_subscription(
                    subscription=subscription,
                    plan_slug=data.get("plan_slug") or None,
                    days=data.get("days"),
                    admin=request.user,
                    request=request,
                )
            else:
                subscription = services.cancel_subscription(
                    subscription=subscription,
                    admin=request.user,
                    request=request,
                )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(AdminSubscriptionSerializer(subscription).data)


class AdminPaymentListView(AdminAuthMixin, generics.ListAPIView):
    permission_classes = (admin_permission(Perm.PAYMENTS_READ),)
    pagination_class = LargeListPagination
    serializer_class = AdminPaymentSerializer

    def get_queryset(self):
        return admin_payments_queryset(
            search=_query_param(self.request, "search"),
            status=_query_param(self.request, "status"),
            plan=_query_param(self.request, "plan"),
        )


class AdminNotificationListView(AdminAuthMixin, generics.ListAPIView):
    permission_classes = (admin_permission(Perm.NOTIFICATIONS_READ),)
    pagination_class = LargeListPagination
    serializer_class = AdminNotificationSerializer

    def get_queryset(self):
        return admin_notifications_queryset(
            search=_query_param(self.request, "search"),
            channel=_query_param(self.request, "channel"),
            status=_query_param(self.request, "status"),
        )


class AdminAuditLogListView(AdminAuthMixin, generics.ListAPIView):
    permission_classes = (admin_permission(Perm.AUDIT_LOGS_READ),)
    pagination_class = LargeListPagination
    serializer_class = AdminAuditLogSerializer

    def get_queryset(self):
        return admin_audit_logs_queryset(
            search=_query_param(self.request, "search"),
            action=_query_param(self.request, "action"),
            from_date=_query_param(self.request, "from"),
            to_date=_query_param(self.request, "to"),
        )
