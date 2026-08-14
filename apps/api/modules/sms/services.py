"""Traitement des Delivery Receipts Orange.

Orange n'envoie aucune signature sur ses webhooks : la securite repose sur le
HTTPS, la validation stricte de la structure du payload et la liste blanche
d'IP (ORANGE_SMS_DR_ALLOWED_IPS). Un meme accuse recu deux fois n'update le
message qu'une seule fois : la contrainte d'unicite du modele absorbe les
repetitions.
"""

import logging

from django.db import transaction
from django.utils import timezone

from modules.documents.models import NotificationDelivery

from .models import SmsDeliveryReceipt

logger = logging.getLogger(__name__)

#: Statuts officiels Orange -> etat de livraison ImmoLib.
DR_STATUS_MAP = {
    "DeliveredToTerminal": "DELIVERED",
    "DeliveredToNetwork": "DELIVERED",
    "DeliveryImpossible": "FAILED",
    "DeliveryUncertain": "UNKNOWN",
    "MessageWaiting": "PENDING_DR",
}

#: Statuts officiels qui n'ont pas de traduction ImmoLib : acceptes, traces.
KNOWN_DR_STATUSES = frozenset(DR_STATUS_MAP)

NORMALIZED_DELIVERED = {"DELIVERED"}
NORMALIZED_FINAL = {"DELIVERED", "FAILED"}


class InvalidDrPayload(Exception):
    """Payload webhook Orange qui ne respecte pas le contrat documente."""


def validate_dr_payload(payload: dict) -> tuple[str, str, str]:
    """Valide la structure d'un Delivery Receipt Orange.

    Retourne ``(resource_id, delivery_status, address)`` ou leve
    ``InvalidDrPayload``. Le format attendu est celui de la documentation
    officielle : ``deliveryInfoNotification.{callbackData, deliveryInfo.{address,
    deliveryStatus}}``.
    """
    notification = payload.get("deliveryInfoNotification")
    if not isinstance(notification, dict):
        raise InvalidDrPayload("deliveryInfoNotification manquant.")
    callback_data = str(notification.get("callbackData") or "")
    delivery_info = notification.get("deliveryInfo")
    if not isinstance(delivery_info, dict):
        raise InvalidDrPayload("deliveryInfo manquant.")
    delivery_status = str(delivery_info.get("deliveryStatus") or "")
    address = str(delivery_info.get("address") or "")
    if not callback_data or not delivery_status:
        raise InvalidDrPayload("callbackData ou deliveryStatus manquant.")
    return callback_data, delivery_status, address


def _apply_to_delivery(
    *, resource_id: str, delivery_status: str, address: str, now
) -> bool:
    """Met a jour la delivery correlee, une seule fois par statut.

    Retourne True si une ligne NotificationDelivery a ete mise a jour.
    """
    normalized = DR_STATUS_MAP.get(delivery_status, "UNKNOWN")
    queryset = NotificationDelivery.objects.filter(provider_reference=resource_id)
    if normalized == "DELIVERED":
        updated = queryset.filter(delivered_at__isnull=True).update(
            delivery_status=normalized,
            delivered_at=now,
        )
        if updated:
            return True
        return bool(
            queryset.filter(delivery_status=normalized).exists()
        )
    # Statut intermediaire ou d'echec : on ne downgrade jamais DELIVERED.
    updated = queryset.exclude(delivery_status="DELIVERED").update(
        delivery_status=normalized,
    )
    if updated and normalized == "FAILED":
        return True
    return bool(updated)


@transaction.atomic
def handle_orange_dr_payload(payload: dict) -> dict:
    """Enregistre un Delivery Receipt Orange et actualise le message.

    Idempotent : le (provider_message_id, delivery_status) est unique ; le
    deuxieme exemplaire ne modifie rien. Retourne un resume pour la reponse
    HTTP (jamais de donnees sensibles).
    """
    resource_id, delivery_status, address = validate_dr_payload(payload)
    receipt, created = SmsDeliveryReceipt.objects.get_or_create(
        provider_message_id=resource_id,
        delivery_status=delivery_status,
        defaults={
            "address": address,
            "raw_payload": payload,
        },
    )
    if not created:
        logger.info(
            "sms.delivery.duplicate resource_id=%s status=%s", resource_id, delivery_status
        )
        return {
            "message_id": resource_id,
            "delivery_status": delivery_status,
            "created": False,
        }
    now = timezone.now()
    updated = _apply_to_delivery(
        resource_id=resource_id,
        delivery_status=delivery_status,
        address=address,
        now=now,
    )
    normalized = DR_STATUS_MAP.get(delivery_status, "UNKNOWN")
    if normalized in NORMALIZED_FINAL:
        logger.info("sms.delivery.%s resource_id=%s", normalized.lower(), resource_id)
    else:
        logger.info("sms.delivery.received resource_id=%s status=%s", resource_id, delivery_status)
    return {
        "message_id": resource_id,
        "delivery_status": delivery_status,
        "normalized_status": normalized,
        "correlated": updated,
        "created": True,
    }
