from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Plan, SubscriptionPayment
from ..services import (
    confirm_paydunya_payment,
    get_user_subscription,
    initiate_subscription_payment,
    verify_paydunya_hash,
)
from .serializers import (
    CreatePaymentSerializer,
    PlanSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionSerializer,
)


class PlanListView(APIView):
    """Liste les plans d'abonnement disponibles."""

    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        plans = Plan.objects.filter(is_active=True)
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data)


class CurrentSubscriptionView(APIView):
    """Affiche l'abonnement actuel de l'utilisateur."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        subscription = get_user_subscription(request.user)
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)


class CreatePaymentView(APIView):
    """Initie un paiement d'abonnement via PayDunya."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = initiate_subscription_payment(
                user=request.user,
                plan_id=serializer.validated_data["plan_id"],
            )
            return Response(
                {
                    "payment_id": str(payment.id),
                    "payment_url": payment.payment_url,
                    "invoice_token": payment.paydunya_invoice_token,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PaymentHistoryView(APIView):
    """Historique des paiements d'abonnement."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        payments = SubscriptionPayment.objects.filter(
            subscription__user=request.user
        )
        serializer = SubscriptionPaymentSerializer(payments, many=True)
        return Response(serializer.data)


class PayDunyaWebhookView(APIView):
    """Webhook IPN pour les notifications PayDunya."""

    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        # PayDunya envoie les données en form-urlencoded
        data = request.POST.get("data", {})

        if not data:
            return Response(
                {"detail": "Données manquantes"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Vérifier le hash
        master_key = getattr(settings, "PAYDUNYA_MASTER_KEY", "")
        received_hash = data.get("hash", "")

        if not verify_paydunya_hash(master_key, received_hash):
            return Response(
                {"detail": "Hash invalide"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Vérifier le statut
        invoice_status = data.get("status", "")
        if invoice_status != "completed":
            return Response({"detail": "Paiement non complété"})

        # Confirmer le paiement
        token = data.get("invoice", {}).get("token", "")
        try:
            confirm_paydunya_payment(token)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"detail": "OK"})
