"""Adaptateur PayDunya (checkout hébergé PAR).

Le paiement se fait sur la page PayDunya. ImmoLib crée la facture côté
serveur, redirige l'utilisateur, puis confirme le statut via l'API
authentifiée avant d'activer un abonnement. Les clés ne sont jamais
exposées au frontend.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings
from django.utils.translation import gettext_lazy as _


class PayDunyaError(Exception):
    pass


API_BASE = "https://app.paydunya.com/api/v1"


def is_configured() -> bool:
    return bool(
        settings.PAYDUNYA_MASTER_KEY
        and settings.PAYDUNYA_PRIVATE_KEY
        and settings.PAYDUNYA_TOKEN
    )


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "PAYDUNYA-MASTER-KEY": settings.PAYDUNYA_MASTER_KEY,
        "PAYDUNYA-PRIVATE-KEY": settings.PAYDUNYA_PRIVATE_KEY,
        "PAYDUNYA-TOKEN": settings.PAYDUNYA_TOKEN,
    }


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        API_BASE + path, data=data, headers=_headers(), method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise PayDunyaError(
            _("PayDunya a répondu HTTP {code}: {detail}").format(
                code=exc.code, detail=detail
            )
        ) from exc
    except urllib.error.URLError as exc:
        raise PayDunyaError(
            _("PayDunya injoignable : {reason}").format(reason=exc.reason)
        ) from exc


def create_checkout_invoice(
    *,
    total_amount: int,
    description: str,
    items: list[tuple[str, int]],
    custom_data: dict,
    return_url: str,
    cancel_url: str,
    callback_url: str,
) -> tuple[str, str]:
    """Crée une facture PayDunya. Retourne (token, url de redirection)."""
    payload = {
        "invoice": {
            "total_amount": int(total_amount),
            "description": description,
            "items": {
                f"item_{index}": {
                    "name": name,
                    "quantity": 1,
                    "unit_price": str(price),
                    "total_price": str(price),
                }
                for index, (name, price) in enumerate(items)
            },
        },
        "store": {"name": settings.PAYDUNYA_STORE_NAME},
        "custom_data": custom_data,
        "actions": {
            "callback_url": callback_url,
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    data = _request("POST", "/checkout-invoice/create", payload)
    if data.get("response_code") != "00":
        raise PayDunyaError(
            data.get("response_text", _("Échec de la création de la facture PayDunya."))
        )
    token = data.get("token", "")
    redirect_url = data.get("response_text", "")
    if not token or not redirect_url:
        raise PayDunyaError(_("Réponse PayDunya incomplète (token ou URL manquant)."))
    return token, redirect_url


def confirm_invoice(token: str) -> str:
    """Confirme le statut d'une facture côté PayDunya (appel authentifié).

    Retourne COMPLETED, PENDING, CANCELLED ou FAILED.
    """
    data = _request("GET", f"/checkout-invoice/confirm/{token}")
    if data.get("response_code") != "00":
        raise PayDunyaError(
            data.get("response_text", _("Échec de la confirmation PayDunya."))
        )
    raw_status = str(data.get("status", "")).upper()
    if raw_status == "COMPLETED":
        return "COMPLETED"
    if raw_status == "CANCELED":
        return "CANCELLED"
    if raw_status == "FAIL":
        return "FAILED"
    return "PENDING"
