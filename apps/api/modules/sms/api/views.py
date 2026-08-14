"""Webhook des Delivery Receipts Orange SMS.

Orange n'offre ni signature ni token de verification : l'authenticite repose
sur le HTTPS, la validation stricte du payload et la liste blanche d'IP
``ORANGE_SMS_DR_ALLOWED_IPS``. On repond 200 des que le payload est valide,
Orange ne relancant que les reponses en erreur.
"""

import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services import (
    InvalidDrPayload,
    handle_orange_dr_payload,
)

logger = logging.getLogger(__name__)


class OrangeSmsDeliveryReceiptView(APIView):
    """Point de terminaison des accuses de reception Orange SMS.

    POST ``/api/v1/webhooks/sms/orange/delivery-receipts/`` avec un payload
    ``deliveryInfoNotification``. Repond 200 (creation) ou 202 (doublon,
    aucune modification). Le payload valide est enregistre brut pour le
    diagnostic ; rien de sensible n'est renvoye a Orange.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> HttpResponse:
        allowed = getattr(settings, "ORANGE_SMS_DR_ALLOWED_IPS", None)
        if not allowed:
            logger.warning("sms.delivery.rejected reason=not-configured")
            return HttpResponse(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not self._ip_allowed(request, allowed):
            logger.warning("sms.delivery.rejected ip=%s", self._client_ip(request))
            return HttpResponse(status=status.HTTP_403_FORBIDDEN)
        payload = request.data
        try:
            summary = handle_orange_dr_payload(payload)
        except InvalidDrPayload as exc:
            logger.info("sms.delivery.invalid_payload reason=%s", exc)
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"received": summary}, status=status.HTTP_200_OK)

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    @staticmethod
    def _ip_allowed(request: Request, allowed) -> bool:
        if "*" in allowed:
            return True
        return OrangeSmsDeliveryReceiptView._client_ip(request) in allowed
