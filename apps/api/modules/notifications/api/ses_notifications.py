"""Evenements Amazon SES (bounce, complaint) recus via Amazon SNS.

Amazon SES publie ses evenements sur un topic SNS qui POSTe chaque
notification sur notre webhook. Chaque message SNS est signe (RSA) : la
confiance repose sur la verification de la signature, le controle du
TopicArn attendu et la fraicheur de l'horodatage (anti-rejeu), pas sur une
liste d'IP comme le webhook Orange.

Le MessageId SES (``mail.messageId``) est la reference retournee par
l'adaptateur a l'envoi et stockee dans ``NotificationDelivery.provider_reference`` :
c'est la cle de correlation. Le traitement est idempotent (mises a jour
conditionnelles) car SNS delivre au moins une fois.
"""

import base64
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import timedelta
from functools import lru_cache

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from modules.documents.models import NotificationDelivery

logger = logging.getLogger(__name__)

#: Champs SNS a signer, dans l'ordre impose par la documentation AWS.
_SNS_SIGNED_FIELDS_V1 = (
    "Message",
    "MessageId",
    "Subject",
    "Timestamp",
    "TopicArn",
    "Type",
    "UnsubscribeURL",
    "SubscribeURL",
    "Token",
)
_SNS_SIGNED_FIELDS_V2 = _SNS_SIGNED_FIELDS_V1 + (
    "SigningCertURL",
    "SignatureVersion",
)

#: Hote autorise pour le certificat de signature et l'URL de confirmation :
#: ``sns.<region>.amazonaws.com`` uniquement (anti-SSRF, cert AWS pine).
_SNS_HOST_RE = re.compile(r"^sns\.([a-z0-9-]+)\.amazonaws\.com$")

#: Age maximal d'une notification SNS avant rejet (rejeu).
SNS_MAX_AGE_SECONDS = 300

_DEFAULT_SES_REGION = "af-south-1"


class InvalidSnsPayload(Exception):
    """Payload SNS/SES qui ne respecte pas le contrat attendu."""


class SnsSignatureRejected(Exception):
    """Signature invalide, certificat non autorise ou topic inattendu."""


def configured_sns_topic_arn() -> str:
    """ARN du topic SNS attendu, ou vide si non configure (webhook ferme)."""
    return _config("AWS_SES_SNS_TOPIC_ARN")


def _config(name: str, default: str = "") -> str:
    """Lit une configuration sans toucher a settings.py.

    Priorite : attribut de configuration (tests via ``override_settings``)
    puis variable d'environnement (production). La cle peut etre ajoutee a
    settings.py plus tard sans changer ce comportement.
    """
    value = getattr(settings, name, None)
    if value in (None, ""):
        value = os.environ.get(name)
    return str(value or default)


def mask_email(address: str) -> str:
    """Masque une adresse email pour la journalisation (jamais en clair)."""
    if "@" in address:
        name, domain = address.split("@", 1)
        return f"{name[:2]}***@{domain}"
    return "***"


def validate_sns_message(payload: dict) -> dict:
    """Valide la structure SNS et retourne le message normalise."""
    if not isinstance(payload, dict):
        raise InvalidSnsPayload("Objet JSON attendu.")
    message_type = payload.get("Type")
    if message_type not in ("Notification", "SubscriptionConfirmation", "UnsubscribeConfirmation"):
        raise InvalidSnsPayload("Type SNS inconnu.")
    if not payload.get("MessageId"):
        raise InvalidSnsPayload("MessageId manquant.")
    if not payload.get("TopicArn"):
        raise InvalidSnsPayload("TopicArn manquant.")
    if not payload.get("Signature"):
        raise InvalidSnsPayload("Signature manquante.")
    return payload


def _sns_region_from_topic(topic_arn: str) -> str:
    match = re.match(r"^arn:aws:sns:([a-z0-9-]+):", topic_arn or "")
    if not match:
        return _config("AWS_SES_REGION", _DEFAULT_SES_REGION)
    return match.group(1)


def _parse_timestamp(value: str):
    value = (value or "").strip()
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    try:
        return django_timezone.datetime.fromisoformat(value)
    except ValueError:
        return None


def _assert_fresh(message: dict, *, now=None) -> None:
    now = now or django_timezone.now()
    timestamp = _parse_timestamp(message.get("Timestamp") or "")
    if timestamp is None:
        raise InvalidSnsPayload("Timestamp manquant ou illisible.")
    if now - timestamp > timedelta(seconds=SNS_MAX_AGE_SECONDS):
        raise InvalidSnsPayload("Notification SNS trop ancienne (rejeu).")


def _canonical_string(message: dict, version: str) -> str:
    fields = _SNS_SIGNED_FIELDS_V2 if version == "2" else _SNS_SIGNED_FIELDS_V1
    return "".join(
        f"{name}\n{message[name]}\n" for name in fields if name in message
    )


@lru_cache(maxsize=16)
def _load_certificate(cert_url: str) -> x509.Certificate:
    with urllib.request.urlopen(cert_url, timeout=10) as response:
        pem = response.read()
    return x509.load_pem_x509_certificate(pem)


def _verify_signature(message: dict, region: str) -> bool:
    """Verifie la signature RSA du message SNS (versions 1 et 2)."""
    version = message.get("SignatureVersion")
    signature = message.get("Signature")
    cert_url = message.get("SigningCertURL")
    if version not in ("1", "2") or not signature or not cert_url:
        return False
    parsed = urllib.parse.urlparse(cert_url)
    match = _SNS_HOST_RE.match(parsed.netloc)
    if parsed.scheme != "https" or not match or match.group(1) != region:
        logger.warning("ses.sns.rejected reason=signing-cert-url host=%s", parsed.netloc)
        return False
    try:
        certificate = _load_certificate(cert_url)
        public_key = certificate.public_key()
        if not isinstance(public_key, RSAPublicKey):
            return False
        digest = hashes.SHA1() if version == "1" else hashes.SHA256()
        public_key.verify(
            base64.b64decode(signature),
            _canonical_string(message, version).encode("utf-8"),
            padding.PKCS1v15(),
            digest,
        )
    except Exception:
        logger.warning("ses.sns.rejected reason=signature-error")
        return False
    return True


def _confirm_subscription(message: dict) -> bool:
    """Confirme l'abonnement SNS en appelant l'URL signee par AWS."""
    url = message.get("SubscribeURL") or ""
    region = _sns_region_from_topic(message.get("TopicArn") or "")
    parsed = urllib.parse.urlparse(url)
    match = _SNS_HOST_RE.match(parsed.netloc)
    if parsed.scheme != "https" or not match or match.group(1) != region:
        logger.warning("ses.sns.rejected reason=subscribe-url")
        return False
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status == 200
    except Exception:
        logger.warning("ses.sns.subscription.error")
        return False


@transaction.atomic
def _mark_permanent_bounce(
    *, ses_message_id: str, addresses: list[str], subtype: str
) -> bool:
    """Marque FAILED la delivery correlee, sans jamais downgrader DELIVERED.

    Idempotent : une delivery deja FAILED ou DELIVERED n'est pas touchee
    (SNS relivre au moins une fois).
    """
    if not ses_message_id:
        logger.warning(
            "ses.bounce.no_reference destinations=%s",
            ",".join(mask_email(a) for a in addresses) or "-",
        )
        return False
    reason = f"SES bounce permanent ({subtype or 'General'})"[:500]
    updated = (
        NotificationDelivery.objects.filter(provider_reference=ses_message_id)
        .exclude(status=NotificationDelivery.Status.FAILED)
        .exclude(delivery_status="DELIVERED")
        .update(
            status=NotificationDelivery.Status.FAILED,
            delivery_status="FAILED",
            next_attempt_at=None,
            failure_reason=reason,
        )
    )
    return bool(updated)


def _handle_bounce(event: dict, *, sns_message_id: str) -> dict:
    bounce = event.get("bounce") or {}
    bounce_type = bounce.get("bounceType") or "unknown"
    subtype = bounce.get("bounceSubType") or ""
    recipients = bounce.get("bouncedRecipients") or []
    addresses = [
        recipient.get("emailAddress") or ""
        for recipient in recipients
        if isinstance(recipient, dict)
    ]
    addresses = [address for address in addresses if address]
    masked = [mask_email(address) for address in addresses]
    ses_message_id = (event.get("mail") or {}).get("messageId") or ""
    reference = ses_message_id or sns_message_id

    if bounce_type != "Permanent":
        logger.info(
            "ses.bounce.%s message_id=%s destinations=%s subtype=%s",
            str(bounce_type).lower(),
            reference,
            ",".join(masked) or "-",
            subtype,
        )
        return {
            "notification_type": "Bounce",
            "bounce_type": bounce_type,
            "destinations": masked,
            "correlated": False,
        }

    correlated = _mark_permanent_bounce(
        ses_message_id=ses_message_id, addresses=addresses, subtype=subtype
    )
    logger.info(
        "ses.bounce.permanent message_id=%s destinations=%s subtype=%s correlated=%s",
        reference,
        ",".join(masked) or "-",
        subtype,
        correlated,
    )
    return {
        "notification_type": "Bounce",
        "bounce_type": "Permanent",
        "destinations": masked,
        "correlated": correlated,
    }


def _handle_complaint(event: dict, *, sns_message_id: str) -> dict:
    """Une plainte ne marque pas la delivery FAILED : l'adresse peut rester
    valide. Elle est tracee (destinations masquees) pour alimenter plus tard
    une liste de suppression cote SES."""
    complaint = event.get("complaint") or {}
    recipients = complaint.get("complainedRecipients") or []
    addresses = [
        recipient.get("emailAddress") or ""
        for recipient in recipients
        if isinstance(recipient, dict)
    ]
    masked = [mask_email(address) for address in addresses if address]
    feedback_type = complaint.get("complaintFeedbackType") or "unknown"
    ses_message_id = (event.get("mail") or {}).get("messageId") or ""
    logger.info(
        "ses.complaint.received message_id=%s destinations=%s feedback=%s",
        ses_message_id or sns_message_id,
        ",".join(masked) or "-",
        feedback_type,
    )
    return {
        "notification_type": "Complaint",
        "destinations": masked,
        "feedback_type": feedback_type,
        "handled": False,
    }


@transaction.atomic
def _process_ses_event(message: dict) -> dict:
    try:
        event = json.loads(message.get("Message") or "")
    except (TypeError, ValueError) as exc:
        raise InvalidSnsPayload("Message SES illisible.") from exc
    if not isinstance(event, dict):
        raise InvalidSnsPayload("Message SES illisible.")

    notification_type = event.get("notificationType")
    sns_message_id = message.get("MessageId", "")
    if notification_type == "Bounce":
        return _handle_bounce(event, sns_message_id=sns_message_id)
    if notification_type == "Complaint":
        return _handle_complaint(event, sns_message_id=sns_message_id)
    if notification_type == "Delivery":
        logger.info("ses.delivery.received message_id=%s", sns_message_id)
        return {"notification_type": "Delivery", "handled": False}
    logger.warning(
        "ses.event.unknown message_id=%s type=%s", sns_message_id, notification_type
    )
    return {"notification_type": notification_type or "unknown", "handled": False}


def handle_sns_message(
    payload: dict, *, configured_topic_arn: str | None = None, now=None
) -> dict:
    """Valide, verifie puis traite une notification SNS.

    Retourne un resume sans donnees sensibles pour la reponse HTTP. SNS
    relivre en cas d'erreur : le webhook repond 200 des que le message est
    valide et signe, meme si l'evenement ne correle aucune delivery.
    """
    message = validate_sns_message(payload)
    if configured_topic_arn and message["TopicArn"] != configured_topic_arn:
        raise SnsSignatureRejected("Topic ARN inattendu.")
    _assert_fresh(message, now=now)
    region = _sns_region_from_topic(message["TopicArn"])
    if not _verify_signature(message, region):
        raise SnsSignatureRejected("Signature invalide ou certificat non autorise.")

    message_type = message["Type"]
    if message_type == "SubscriptionConfirmation":
        confirmed = _confirm_subscription(message)
        logger.info(
            "ses.sns.subscription message_id=%s topic=%s confirmed=%s",
            message["MessageId"],
            message["TopicArn"],
            confirmed,
        )
        return {"type": "subscription-confirmation", "confirmed": confirmed}
    if message_type == "UnsubscribeConfirmation":
        logger.info(
            "ses.sns.unsubscribe message_id=%s topic=%s",
            message["MessageId"],
            message["TopicArn"],
        )
        return {"type": "unsubscribe-confirmation", "confirmed": True}

    return _process_ses_event(message)
