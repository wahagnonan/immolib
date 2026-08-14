"""Client de l'API SMS Orange Cote d'Ivoire (OAuth 2.0 v3).

Point d'entree unique vers Orange, isole du reste de l'application. Le
fournisseur suit exactement la documentation officielle
(https://developer.orange.com/apis/sms-ci/) :

- token : POST /oauth/v3/token (grant_type=client_credentials, Basic auth) ;
- envoi : POST /smsmessaging/v1/outbound/{senderAddress}/requests ;
- le token dure 3600 secondes : il est reutilise et renouvele automatiquement
  sur l'erreur officielle "Expired credentials" (HTTP 401, code 42).

Le client_secret et l'access_token ne sont jamais journalises, ni exposes
dans une reponse API.
"""

import base64
import logging
import time
import uuid
from urllib.parse import quote

import requests

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# Duree de vie officielle du token OAuth v3 (secondes).
_TOKEN_LIFETIME_SECONDS = 3600
# Marge de securite avant l'expiration reelle : on renouvelle plus tot.
_TOKEN_SAFETY_MARGIN_SECONDS = 60

# Codes d'erreur officiels Orange (voir la reference API SMS CI).
_ERROR_EXPIRED_CREDENTIALS = 42
_ERROR_INVALID_CREDENTIALS = 41
_ERROR_MISSING_CREDENTIALS = 40
_ERROR_TOO_MANY_REQUESTS = 53
_ERROR_SERVICE_UNAVAILABLE = 5
_ERROR_OVER_CAPACITY = 6


class OrangeProviderError(Exception):
    """Erreur technique du fournisseur : un nouvel essai peut reussir."""


class OrangeProviderPermanentError(Exception):
    """Erreur fonctionnelle : inutile de reessayer (credentials, numero,
    sender name ou configuration invalides)."""


def _mask_recipient(recipient: str) -> str:
    digits = "".join(character for character in recipient if character.isdigit())
    return f"***{digits[-4:]}" if digits else "***"


class OrangeSmsApiClient:
    """Appelle l'API Orange SMS CI avec un token OAuth v3 en cache."""

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        sender_address: str | None = None,
        sender_name: str | None = None,
        timeout: float | None = None,
        session: requests.Session | None = None,
    ):
        self.client_id = (
            client_id if client_id is not None else settings.ORANGE_SMS_CLIENT_ID
        )
        self.client_secret = (
            client_secret
            if client_secret is not None
            else settings.ORANGE_SMS_CLIENT_SECRET
        )
        if not self.client_id or not self.client_secret:
            raise ImproperlyConfigured(
                "ORANGE_SMS_CLIENT_ID et ORANGE_SMS_CLIENT_SECRET doivent etre "
                "configures pour envoyer des SMS Orange."
            )
        self.base_url = (base_url or settings.ORANGE_SMS_BASE_URL).rstrip("/")
        self.sender_address = sender_address or settings.ORANGE_SMS_SENDER_ADDRESS
        self.sender_name = (
            sender_name if sender_name is not None else settings.ORANGE_SMS_SENDER_NAME
        )
        self.timeout = timeout or settings.ORANGE_SMS_TIMEOUT_SECONDS
        self.session = session or requests.Session()
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def _token_url(self) -> str:
        return f"{self.base_url}/oauth/v3/token"

    @property
    def _messaging_base_url(self) -> str:
        return f"{self.base_url}/smsmessaging/v1"

    def _authorization_header(self) -> str:
        credentials = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(credentials).decode("ascii")

    def _fetch_token(self) -> None:
        logger.info("sms.auth.started")
        try:
            response = self.session.post(
                self._token_url,
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": self._authorization_header(),
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("sms.auth.failed reason=network")
            raise OrangeProviderError(f"Impossible de joindre Orange : {exc}") from exc
        if response.status_code >= 400:
            code, message = self._error_details(response)
            logger.warning("sms.auth.failed status=%s code=%s", response.status_code, code)
            if response.status_code in (401, 403):
                raise OrangeProviderPermanentError(
                    "Les credentials Orange sont invalides ou refuses "
                    f"(HTTP {response.status_code})."
                )
            raise OrangeProviderError(
                f"Orange n'a pas delivre de token (HTTP {response.status_code})."
            )
        try:
            payload = response.json()
            token = payload.get("access_token", "")
            expires_in = int(payload.get("expires_in", _TOKEN_LIFETIME_SECONDS))
        except (ValueError, TypeError) as exc:
            logger.warning("sms.auth.failed reason=invalid-response")
            raise OrangeProviderError(_("Reponse de token Orange illisible.")) from exc
        if not token:
            logger.warning("sms.auth.failed reason=missing-token")
            raise OrangeProviderError(_("Orange n'a pas renvoye d'access_token."))
        self._token = token
        self._token_expires_at = (
            time.monotonic() + expires_in - _TOKEN_SAFETY_MARGIN_SECONDS
        )
        logger.info("sms.auth.success")

    def get_token(self) -> str:
        """Retourne le token en cache ou en demande un nouveau."""
        if self._token is None or time.monotonic() >= self._token_expires_at:
            self._fetch_token()
        return self._token

    @staticmethod
    def _error_details(response: requests.Response) -> tuple[str | None, str]:
        try:
            error = response.json().get("requestError", {}).get("policyException")
            if error is None:
                error = response.json().get("requestError", {}).get("serviceException")
            if error is None:
                error = response.json().get("serviceException")
            code = error.get("messageId") or error.get("code")
            message = error.get("text") or error.get("message") or ""
        except (ValueError, AttributeError):
            code, message = None, ""
        return str(code) if code is not None else None, str(message)

    def _send_payload(
        self, *, recipient: str, message: str, client_correlator: str
    ) -> dict:
        payload: dict = {
            "outboundSMSMessageRequest": {
                "address": f"tel:{recipient}",
                "senderAddress": self.sender_address,
                "outboundSMSTextMessage": {"message": message},
                "clientCorrelator": client_correlator,
            }
        }
        if self.sender_name:
            payload["outboundSMSMessageRequest"]["senderName"] = self.sender_name
        return payload

    def _outbound_url(self) -> str:
        encoded = quote(self.sender_address, safe="")
        return f"{self._messaging_base_url}/outbound/{encoded}/requests"

    def _post_message(
        self, *, recipient: str, message: str, client_correlator: str
    ) -> requests.Response:
        return self.session.post(
            self._outbound_url(),
            json=self._send_payload(
                recipient=recipient,
                message=message,
                client_correlator=client_correlator,
            ),
            headers={"Authorization": f"Bearer {self.get_token()}"},
            timeout=self.timeout,
        )

    def _raise_for_send_error(
        self, response: requests.Response, *, refreshed: bool = False
    ) -> None:
        code, message = self._error_details(response)
        detail = f"Orange SMS HTTP {response.status_code} : {message or code or ''}".strip()
        if response.status_code == 401:
            if not refreshed and code == str(_ERROR_EXPIRED_CREDENTIALS):
                raise OrangeProviderError(detail)
            raise OrangeProviderPermanentError(detail)
        if response.status_code in (403, 400):
            raise OrangeProviderPermanentError(detail)
        raise OrangeProviderError(detail)

    @staticmethod
    def _extract_resource_id(payload: dict) -> str:
        request = payload.get("outboundSMSMessageRequest") or {}
        resource_url = request.get("resourceURL") or ""
        return resource_url.rsplit("/", 1)[-1]

    def send_sms(
        self,
        *,
        recipient: str,
        message: str,
        client_correlator: str | None = None,
    ) -> str:
        """Envoie un SMS et retourne le resource_id de correlation Orange.

        Le ``clientCorrelator`` est un identifiant cote client qui sera
        renvoye tel quel par Orange dans le callbackData du Delivery Receipt :
        c'est la cle de correlation de la remise. S'il n'est pas fourni, un
        identifiant est genere (utile en dehors de la file de notifications).
        """
        logger.info("sms.send.started recipient=%s", _mask_recipient(recipient))
        if not client_correlator:
            client_correlator = str(uuid.uuid4())
        response = self._post_message(
            recipient=recipient,
            message=message,
            client_correlator=client_correlator,
        )
        refreshed = False
        if response.status_code == 401:
            code, _message = self._error_details(response)
            if code == str(_ERROR_EXPIRED_CREDENTIALS):
                logger.info("sms.auth.refreshing")
                self._token = None
                response = self._post_message(
                    recipient=recipient,
                    message=message,
                    client_correlator=client_correlator,
                )
                refreshed = True
        if response.status_code >= 400:
            self._raise_for_send_error(response, refreshed=refreshed)
        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("sms.send.failed reason=invalid-response")
            raise OrangeProviderError(_("Reponse Orange illisible.")) from exc
        resource_id = self._extract_resource_id(payload)
        if not resource_id:
            logger.warning("sms.send.failed reason=missing-resource-id")
            raise OrangeProviderError(_("Orange n'a pas renvoye de resource_id."))
        logger.info("sms.send.success resource_id=%s", resource_id)
        return resource_id
