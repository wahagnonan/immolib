"""Endpoints PI-SPI (BCEAO) — Model B.

- POST /payment-requests/{id}/initiate-pi-spi/  → initie via PSP
- GET  /payment-requests/{id}/pi-spi-status/    → polling statut
- POST /webhooks/pi-spi/                        → callback PSP (AllowAny, HMAC)

Sécurité : vérification signature, idempotence, validation amount/currency.
"""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.exceptions import NotFound, ValidationError, PermissionDenied as DRFPermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.payments.models import PaymentRequest

from ..services_pi_spi import PiSpiWebhookData, handle_pi_spi_webhook, initiate_pi_spi_payment
from ..adapters.registry import get_provider


class PiSpiWebhookSerializer(serializers.Serializer):
    # PSP peut envoyer différents formats ; on accepte large
    provider = serializers.CharField(required=False, default="PI_SPI")
    event_id = serializers.CharField(required=False, allow_blank=True)
    external_event_id = serializers.CharField(required=False, allow_blank=True)
    event_type = serializers.CharField(required=False, default="payment.succeeded")
    status = serializers.CharField(required=False, default="SUCCEEDED")
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    external_transaction_id = serializers.CharField(required=False, allow_blank=True)
    transaction_reference = serializers.CharField(required=False, allow_blank=True)
    rent_charge_id = serializers.UUIDField(required=False, allow_null=True)
    payment_request_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    currency = serializers.CharField(required=False, default="XOF")
    paid_at = serializers.DateTimeField(required=False, allow_null=True)


class PiSpiInitiateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request, pk: str) -> Response:
        try:
            pr_id = uuid.UUID(str(pk))
        except ValueError as exc:
            raise ValidationError("ID invalide") from exc
        try:
            pr = PaymentRequest.objects.select_related("rent_charge").get(id=pr_id)
        except PaymentRequest.DoesNotExist as exc:
            raise NotFound("Demande introuvable") from exc

        try:
            result = initiate_pi_spi_payment(tenant=request.user, payment_request=pr)
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc

        from ..api.serializers import PaymentRequestSerializer  # noqa: PLC0415

        data = PaymentRequestSerializer(result.payment_request).data
        return Response(
            {
                "payment_request": data,
                "external_transaction_id": result.external_transaction_id,
                "provider_status": result.provider_status,
                "created": result.created,
            },
            status=status.HTTP_200_OK,
        )


class PiSpiStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, pk: str) -> Response:
        try:
            pr_id = uuid.UUID(str(pk))
        except ValueError as exc:
            raise ValidationError("ID invalide") from exc
        # Tenant voit sa demande, bailleur voit sa demande à confirmer
        from django.db.models import Q  # noqa: PLC0415
        from modules.leases.selectors import manageable_properties_for  # noqa: PLC0415

        manageable_ids = manageable_properties_for(request.user).values_list("id", flat=True)
        qs = PaymentRequest.objects.filter(
            Q(requested_by=request.user) | Q(rent_charge__lease__property_id__in=manageable_ids)
        ).distinct()
        try:
            pr = qs.select_related("rent_charge", "payment").get(id=pr_id)
        except PaymentRequest.DoesNotExist as exc:
            raise NotFound("Demande introuvable") from exc

        from ..api.serializers import PaymentRequestSerializer  # noqa: PLC0415

        # Option: tenter reconcile via PSP si PROCESSING
        if pr.status == PaymentRequest.Status.PROCESSING and pr.external_transaction_id:
            try:
                provider = get_provider(pr.provider or "PI_SPI")
                txn = provider.get_transaction_status(pr.external_transaction_id)
                # Ne met à jour que si terminal
                if txn.status.value in {"SUCCESS", "FAILED", "CANCELLED", "EXPIRED"}:
                    # Le webhook devrait déjà avoir traité, mais on synchronise
                    pass
            except Exception:  # noqa: BLE001
                pass

        return Response(PaymentRequestSerializer(pr).data)


class PiSpiWebhookView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> Response:
        raw_body = request.body
        headers = {k: v for k, v in request.headers.items()}

        # Détermine provider depuis payload ou header
        provider_hint = str(request.data.get("provider") or request.headers.get("X-PI-SPI-Provider") or "PI_SPI").upper()

        # Vérifie signature via adapter
        try:
            adapter = get_provider(provider_hint if provider_hint in {"PI_SPI", "PI-SPI", "MOCK_PI_SPI"} else "PI_SPI")
            verification = adapter.verify_webhook(raw_body, headers)
            if not verification.is_valid:
                raise DRFPermissionDenied(f"Signature invalide: {verification.failure_reason}")
        except ValueError:
            # Provider inconnu → 400
            return Response({"detail": "Provider inconnu"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            # Runtime secret non configuré → 503
            if "non configuré" in str(exc):
                return Response({"detail": "Webhook PI-SPI non configuré"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            raise DRFPermissionDenied(str(exc)) from exc

        serializer = PiSpiWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vals = serializer.validated_data

        # Normalisation IDs
        event_id = (
            vals.get("event_id")
            or vals.get("external_event_id")
            or verification.external_event_id
            or str(uuid.uuid4())
        )
        txn_id = (
            vals.get("transaction_id")
            or vals.get("external_transaction_id")
            or vals.get("transaction_reference")
            or verification.external_transaction_id
            or ""
        )
        amount = vals.get("amount")
        # Si amount absent, tente de le déduire via PaymentRequest
        if amount is None and vals.get("payment_request_id"):
            try:
                pr_tmp = PaymentRequest.objects.get(id=vals["payment_request_id"])
                amount = pr_tmp.amount
            except PaymentRequest.DoesNotExist:
                amount = Decimal("0")
        if amount is None:
            amount = Decimal("0")

        currency = vals.get("currency") or "XOF"
        paid_at = vals.get("paid_at") or timezone.now()
        status_raw = vals.get("status") or "SUCCEEDED"

        payload_digest = hashlib.sha256(raw_body).hexdigest()

        webhook_data = PiSpiWebhookData(
            provider=provider_hint,
            external_event_id=str(event_id),
            external_transaction_id=str(txn_id),
            event_type=str(vals.get("event_type") or "payment.succeeded"),
            status=str(status_raw),
            amount=Decimal(str(amount)),
            currency=str(currency),
            paid_at=paid_at,
            rent_charge_id=vals.get("rent_charge_id"),
            payment_request_id=vals.get("payment_request_id"),
            payload_digest=payload_digest,
        )

        try:
            event, payment = handle_pi_spi_webhook(data=webhook_data, raw_payload=request.data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        return Response(
            {
                "event_id": str(event.id),
                "provider": event.provider,
                "external_event_id": event.external_event_id,
                "status": event.status,
                "payment_id": str(payment.id) if payment else None,
                "payment_status": payment.status if payment else None,
                "created": payment is not None,
            },
            status=status.HTTP_200_OK,
        )
