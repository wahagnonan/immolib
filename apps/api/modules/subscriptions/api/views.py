import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.accounts.models import User

from .. import paydunya
from ..models import Subscription, SubscriptionPlan, SubscriptionTransaction
from ..services import (
    FeatureDenied,
    HouseLimitReached,
    cancel_subscription,
    check_subscription_expirations,
    confirm_transaction,
    ensure_subscription,
    get_effective_plan,
    get_usage,
    handle_paydunya_ipn,
    refresh_transaction,
    upgrade,
)
from .serializers import (
    SubscriptionDetailSerializer,
    SubscriptionPlanSerializer,
    SubscriptionTransactionSerializer,
    UpgradeSubscriptionSerializer,
)


class SubscriptionView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        user = request.user
        subscription = ensure_subscription(user)
        plan = get_effective_plan(user)
        usage = get_usage(user)
        pending = (
            SubscriptionTransaction.objects.filter(
                user=user, status=SubscriptionTransaction.Status.PENDING
            )
            .select_related("plan")
            .first()
        )
        payload = SubscriptionDetailSerializer(
            {
                "plan": plan,
                "status": subscription.status,
                "status_label": subscription.get_status_display(),
                "started_at": subscription.started_at,
                "expires_at": subscription.expires_at,
                "house_count": usage.house_count,
                "max_houses": usage.max_houses,
                "remaining_houses": usage.remaining,
                "features": plan.features,
                "pending_transaction": pending,
            }
        ).data
        return Response(payload)


class SubscriptionPlansView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by(
            "price_monthly"
        )
        return Response(SubscriptionPlanSerializer(plans, many=True).data)


class UpgradeSubscriptionView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        serializer = UpgradeSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = upgrade(request.user, serializer.validated_data["plan_slug"])
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except paydunya.PayDunyaError as exc:
            logger.warning(
                "Echec PayDunya (checkout) pour l\u2019utilisateur %s : %s",
                request.user.id,
                exc,
            )
            return Response(
                {
                    "detail": _(
                        "Le paiement en ligne est momentanément indisponible."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                "transaction": SubscriptionTransactionSerializer(
                    result.transaction
                ).data,
                "redirect_url": result.redirect_url,
                "activated": result.activated,
            },
            status=status.HTTP_201_CREATED,
        )


class CancelSubscriptionView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        try:
            subscription = cancel_subscription(request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(
            {
                "status": subscription.status,
                "status_label": subscription.get_status_display(),
            }
        )


class SubscriptionTransactionRefreshView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, transaction_id) -> Response:
        transaction_record = get_object_or_404(
            SubscriptionTransaction,
            id=transaction_id,
            user=request.user,
        )
        transaction_record = refresh_transaction(transaction_record)
        return Response(
            SubscriptionTransactionSerializer(transaction_record).data
        )


class PayDunyaWebhookView(APIView):
    """IPN PayDunya : la confiance repose sur la confirmation authentifiée
    du token auprès de PayDunya, jamais sur le corps seul."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> Response:
        if not paydunya.is_configured():
            return Response(
                {"detail": "PayDunya n'est pas configuré."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        invoice = request.data.get("invoice") or {}
        token = invoice.get("token") or request.data.get("invoice_token", "")
        if not token:
            return Response({"detail": "Token manquant."}, status=400)
        transaction_record = handle_paydunya_ipn(token=token)
        return Response(
            {
                "ok": True,
                "transaction_status": (
                    transaction_record.status
                    if transaction_record is not None
                    else "UNKNOWN"
                ),
            }
        )


class SubscriptionExpiryCheckView(APIView):
    """Point d'accès admin manuel (réutilisé par la commande Django)."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        if request.user.role != User.Role.ADMIN:
            raise PermissionDenied(_("Réservé aux administrateurs ImmoLib."))
        count = check_subscription_expirations()
        return Response({"expired": count})
