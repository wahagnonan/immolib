from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.exceptions import ValidationError as DjangoValidationError

from ..services import MobileMoneyPaymentData, record_mobile_money_provider_event
from ..webhooks import (
    InvalidWebhookSignature,
    verify_mobile_money_webhook_signature,
)


class MobileMoneyWebhookSerializer(serializers.Serializer):
    provider = serializers.SlugField(max_length=40)
    event_id = serializers.CharField(max_length=120)
    event_type = serializers.CharField(max_length=60)
    status = serializers.ChoiceField(
        choices=("SUCCEEDED", "FAILED", "PENDING", "CANCELLED")
    )
    transaction_id = serializers.CharField(max_length=120)
    rent_charge_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(min_length=3, max_length=3)
    paid_at = serializers.DateTimeField()


class MobileMoneyWebhookView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> Response:
        raw_body = request.body
        try:
            payload_digest = verify_mobile_money_webhook_signature(
                raw_body=raw_body,
                timestamp=request.headers.get("X-ImmoLib-Timestamp", ""),
                signature=request.headers.get("X-ImmoLib-Signature", ""),
            )
        except InvalidWebhookSignature as exc:
            raise PermissionDenied("Signature du webhook invalide.") from exc
        except RuntimeError:
            return Response(
                {"detail": "Le webhook Mobile Money n'est pas configuré."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = MobileMoneyWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            result = record_mobile_money_provider_event(
                data=MobileMoneyPaymentData(
                    provider=values["provider"],
                    external_event_id=values["event_id"],
                    event_type=values["event_type"],
                    event_status=values["status"],
                    transaction_reference=values["transaction_id"],
                    rent_charge_id=values["rent_charge_id"],
                    amount=values["amount"],
                    currency=values["currency"],
                    paid_at=values["paid_at"],
                    payload_digest=payload_digest,
                )
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        return Response(
            {
                "event_id": str(result.provider_event.id),
                "event_status": result.provider_event.status,
                "payment_id": (
                    str(result.payment.id) if result.payment is not None else None
                ),
                "payment_status": (
                    result.payment.status if result.payment is not None else None
                ),
                "created": result.created,
            }
        )
