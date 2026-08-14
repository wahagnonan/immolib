"""Client de l'API WhatsApp Cloud (Meta Graph API).

Permet à ImmoLib d'envoyer des messages écrits (quittances, rappels de
loyer, invitations) vers un numéro WhatsApp individuel via l'API officielle.
Seuls des messages texte et des modèles texte sont envoyés : pas de vocal,
d'appel ni de média. La réception se fait par le webhook
(voir modules.whatsapp.api.views).
"""

import logging

import requests

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# Codes d'erreur Meta qui ne seront jamais corrigés par une nouvelle
# tentative : le destinataire est invalide, non inscrit à WhatsApp ou
# n'a pas donné son opt-in (ou hors fenêtre de session de 24 h).
_PERMANENT_ERROR_CODES = frozenset(
    {131008, 131026, 131047, 131048, 131049, 132000, 132001}
)

_TEXT_BODY_LIMIT = 4096


class WhatsAppProviderError(Exception):
    """Erreur technique du fournisseur : un nouvel essai peut réussir."""


class WhatsAppProviderPermanentError(Exception):
    """Erreur fonctionnelle : inutile de réessayer (numéro invalide, non opt-in)."""


def _e164_without_plus(phone: str) -> str:
    return phone.removeprefix("+").strip()


class WhatsAppCloudApiClient:
    """Appelle l'endpoint ``/{version}/{phone_number_id}/messages``."""

    def __init__(
        self,
        *,
        access_token=None,
        phone_number_id=None,
        api_version=None,
        base_url=None,
        session=None,
    ):
        self.access_token = (
            access_token if access_token is not None else settings.WHATSAPP_ACCESS_TOKEN
        )
        self.phone_number_id = (
            phone_number_id
            if phone_number_id is not None
            else settings.WHATSAPP_PHONE_NUMBER_ID
        )
        self.api_version = api_version or settings.WHATSAPP_API_VERSION
        self.base_url = (base_url or settings.WHATSAPP_GRAPH_BASE_URL).rstrip("/")
        if not self.access_token or not self.phone_number_id:
            raise ImproperlyConfigured(
                _(
                    "WHATSAPP_ACCESS_TOKEN et WHATSAPP_PHONE_NUMBER_ID doivent être "
                    "configurés pour envoyer des messages WhatsApp."
                )
            )
        self.session = session or requests.Session()

    def _post(self, payload: dict) -> dict:
        url = f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"
        response = self.session.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30,
        )
        if response.status_code >= 400:
            self._raise_for_error(response)
        return response.json()

    @staticmethod
    def _raise_for_error(response: requests.Response) -> None:
        try:
            error = response.json().get("error", {})
            code = error.get("code")
            message = error.get("message", "")
        except ValueError:
            code, message = None, ""
        detail = f"WhatsApp HTTP {response.status_code} : {message}"
        if code in _PERMANENT_ERROR_CODES:
            raise WhatsAppProviderPermanentError(detail)
        raise WhatsAppProviderError(detail)

    def send_text_message(
        self, *, to: str, body: str, preview_url: bool = False
    ) -> dict:
        return self._post(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": _e164_without_plus(to),
                "type": "text",
                "text": {"preview_url": preview_url, "body": body[:_TEXT_BODY_LIMIT]},
            }
        )

    def send_template_message(
        self,
        *,
        to: str,
        template_name: str,
        language: str = "fr",
        components: list | None = None,
    ) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": _e164_without_plus(to),
            "type": "template",
            "template": {"name": template_name, "language": {"code": language}},
        }
        if components:
            payload["template"]["components"] = components
        return self._post(payload)
