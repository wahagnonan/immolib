"""Traitement des payloads webhook WhatsApp (messages entrants et statuts)."""

import logging
from datetime import datetime, timezone

from .models import WhatsAppInboundMessage, WhatsAppMessageStatus

logger = logging.getLogger(__name__)


def _timestamp_to_datetime(value: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return datetime.now(tz=timezone.utc)


def _profile_names(value: dict) -> dict[str, str]:
    return {
        contact.get("wa_id", ""): contact.get("profile", {}).get("name", "")
        for contact in value.get("contacts", [])
    }


def _extract_message_content(message: dict) -> tuple[str, str, str]:
    message_type = message.get("type", "unknown")
    if message_type == "text":
        return message_type, message.get("text", {}).get("body", ""), ""
    if message_type in ("image", "video", "audio", "document", "sticker"):
        media = message.get(message_type, {}) or {}
        return (
            message_type,
            media.get("caption", "") or "",
            media.get("id", "") or "",
        )
    if message_type == "location":
        location = message.get("location", {}) or {}
        body = f"{location.get('latitude', '')}, {location.get('longitude', '')}"
        return message_type, body, ""
    if message_type == "contacts":
        return message_type, "", ""
    return message_type, "", ""


def _record_inbound_message(*, value: dict, message: dict) -> None:
    message_type, body, media_id = _extract_message_content(message)
    profiles = _profile_names(value)
    wa_id = message.get("from", "")
    timestamp = _timestamp_to_datetime(message.get("timestamp", "0"))
    _, created = WhatsAppInboundMessage.objects.get_or_create(
        message_id=message.get("id", ""),
        defaults={
            "wa_id": wa_id,
            "profile_name": profiles.get(wa_id, ""),
            "message_type": message_type,
            "body": body,
            "media_id": media_id,
            "from_me": bool(message.get("from_me", False)),
            "sent_at": timestamp,
            "raw_payload": message,
        },
    )
    if created:
        logger.info("Message WhatsApp entrant: %s (%s)", wa_id, message_type)


def _record_status(status_item: dict) -> None:
    message_id = status_item.get("id", "")
    if not message_id:
        return
    _, created = WhatsAppMessageStatus.objects.get_or_create(
        message_id=message_id,
        status=status_item.get("status", ""),
        defaults={
            "status_timestamp": str(status_item.get("timestamp", "")),
            "errors": status_item.get("errors", []) or [],
            "raw_payload": status_item,
        },
    )
    if created:
        logger.info("Statut WhatsApp %s pour %s", status_item.get("status"), message_id)


def handle_whatsapp_webhook_payload(payload: dict) -> dict:
    """Persiste les messages entrants et les statuts d'un payload webhook.

    Renvoie un résumé ``{"messages": n, "statuses": n}`` pour la réponse HTTP.
    Les doublons (nouveaux essais Meta) sont absorbés par get_or_create.
    """
    messages = 0
    statuses = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {}) or {}
            for message in value.get("messages", []) or []:
                _record_inbound_message(value=value, message=message)
                messages += 1
            for status_item in value.get("statuses", []) or []:
                _record_status(status_item)
                statuses += 1
    return {"messages": messages, "statuses": statuses}
