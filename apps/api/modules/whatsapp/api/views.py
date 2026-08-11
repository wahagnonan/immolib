from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services import handle_whatsapp_webhook_payload


class WhatsAppWebhookView(APIView):
    """Point de terminaison webhook de l'API WhatsApp Cloud.

    GET  : handshake de vérification demandé par Meta. Il faut répondre le
           ``hub.challenge`` en texte brut (jamais de JSON) avec HTTP 200 si
           ``hub.mode == "subscribe"`` et que le ``hub.verify_token``
           correspond à WHATSAPP_WEBHOOK_VERIFY_TOKEN ; sinon HTTP 403.
    POST : notifications d'événements (messages entrants, statuts). Répondre
           200 rapidement : Meta relance les demandes non-200 pendant 7 jours.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request: Request) -> HttpResponse:
        expected = settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        if expected and mode == "subscribe" and token and challenge and token == expected:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse(status=status.HTTP_403_FORBIDDEN)

    def post(self, request: Request) -> Response:
        payload = request.data
        if not isinstance(payload, dict) or payload.get("object") != (
            "whatsapp_business_account"
        ):
            return Response(
                {"detail": "Payload webhook WhatsApp inconnu."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        summary = handle_whatsapp_webhook_payload(payload)
        return Response({"received": summary}, status=status.HTTP_200_OK)
