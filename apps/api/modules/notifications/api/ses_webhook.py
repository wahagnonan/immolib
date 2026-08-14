"""Webhook des notifications Amazon SES (bounces, complaints) via SNS.

Amazon SNS POSTe les evenements sur l'endpoint HTTPS. Contrairement au
webhook Orange, chaque message SNS est signe (RSA) : l'authenticite repose
sur la verification de la signature, pas sur une liste d'IP. Tant que
``AWS_SES_SNS_TOPIC_ARN`` est vide, le webhook repond 503 (ferme par defaut).
"""

import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .ses_notifications import (
    InvalidSnsPayload,
    SnsSignatureRejected,
    configured_sns_topic_arn,
    handle_sns_message,
)

logger = logging.getLogger(__name__)


class SesBounceComplaintWebhookView(APIView):
    """Point de terminaison des evenements SES publies par SNS.

    POST ``/api/v1/webhooks/email/ses/`` avec le message SNS brut. Repond
    200 des que le message est valide et signe (SNS relance les reponses en
    erreur) ; 400 pour un payload invalide, 403 pour une signature ou un
    topic non autorise.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> HttpResponse:
        topic_arn = configured_sns_topic_arn()
        if not topic_arn:
            logger.warning("ses.sns.rejected reason=not-configured")
            return HttpResponse(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            payload = request.data
        except ParseError:
            logger.info("ses.sns.invalid_payload reason=json")
            return Response(
                {"detail": "JSON illisible."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(payload, dict):
            logger.info("ses.sns.invalid_payload reason=structure")
            return Response(
                {"detail": "Objet JSON attendu."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            summary = handle_sns_message(payload, configured_topic_arn=topic_arn)
        except InvalidSnsPayload as exc:
            logger.info("ses.sns.invalid_payload reason=%s", exc)
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        except SnsSignatureRejected as exc:
            logger.warning("ses.sns.rejected reason=%s", exc)
            return Response(
                {"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN
            )
        return Response({"received": summary}, status=status.HTTP_200_OK)
