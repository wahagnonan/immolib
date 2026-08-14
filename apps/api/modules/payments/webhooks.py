import hashlib
import hmac
import time

from django.conf import settings


class InvalidWebhookSignature(Exception):
    pass


def verify_mobile_money_webhook_signature(
    *,
    raw_body: bytes,
    timestamp: str,
    signature: str,
) -> str:
    secret = settings.MOBILE_MONEY_WEBHOOK_SECRET
    if not secret:
        raise RuntimeError(_("Le secret du webhook Mobile Money n'est pas configuré."))
    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise InvalidWebhookSignature(_("Horodatage invalide.")) from exc
    if abs(int(time.time()) - timestamp_value) > (
        settings.MOBILE_MONEY_WEBHOOK_TOLERANCE_SECONDS
    ):
        raise InvalidWebhookSignature(_("Webhook expiré."))

    supplied = signature.removeprefix("sha256=").strip().lower()
    signed_payload = timestamp.encode("ascii") + b"." + raw_body
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise InvalidWebhookSignature(_("Signature invalide."))
    return hashlib.sha256(raw_body).hexdigest()
