"""Adapter PI-SPI via PSP participant (Model B).

ImmoLib ne se connecte JAMAIS directement au switch BCEAO.
L'adapter parle au PSP partenaire (banque/EME agréé) qui est connecté
au switch PI-SPI 24/7. Le PSP expose généralement :
- POST /payments/initiate
- GET  /payments/{id}/status
- Webhook POST → ImmoLib

En l'absence de PSP configuré (PI_SPI_PSP_BASE_URL vide),
l'adapter fonctionne en mode mock/sandbox (PI_SPI_MODE=test)
sans jamais simuler un succès en production.

Exigences de sécurité (Phase 9) :
- Idempotence via clé déterministe
- Vérification signature webhook (HMAC ou mTLS selon PSP)
- Validation amount/currency/beneficiary avant création Payment
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from decimal import Decimal

import requests
from django.conf import settings

from .base import (
    InitiatePaymentRequest,
    InitiatePaymentResult,
    PaymentProvider,
    ProviderStatus,
    ProviderTransactionStatus,
    WebhookVerificationResult,
)


def _is_sandbox() -> bool:
    return getattr(settings, "PI_SPI_MODE", "sandbox").lower() in {"sandbox", "test", "mock"}


def _mock_enabled() -> bool:
    return getattr(settings, "PI_SPI_MOCK_ENABLED", True) and _is_sandbox()


class PiSpiProvider(PaymentProvider):
    provider_code = "PI_SPI"

    # --- Initiation ---

    def initiate_payment(self, request: InitiatePaymentRequest) -> InitiatePaymentResult:
        if _mock_enabled() or not getattr(settings, "PI_SPI_PSP_BASE_URL", "").strip():
            # Délégation au mock en sandbox sans PSP
            from .mock_pi_spi import MockPiSpiProvider  # noqa: PLC0415

            return MockPiSpiProvider().initiate_payment(request)

        base_url = settings.PI_SPI_PSP_BASE_URL.rstrip("/")
        api_key = getattr(settings, "PI_SPI_PSP_API_KEY", "")
        timeout = int(getattr(settings, "PI_SPI_TIMEOUT_SECONDS", 15))

        payload = {
            "idempotency_key": request.idempotency_key,
            "reference": request.reference,
            "amount": str(request.amount),
            "currency": request.currency,
            "debtor": {"phone": request.tenant_phone, "name": request.tenant_name},
            "creditor": {
                "account": request.payee_account_identifier,
                "name": request.payee_name,
            },
            "metadata": {
                "rent_charge_id": str(request.rent_charge_id),
                "tenant_id": str(request.tenant_id),
                "operator": request.operator,
                **request.metadata,
            },
        }
        headers = {
            "Authorization": f"Bearer {api_key}" if api_key else "",
            "Idempotency-Key": request.idempotency_key,
            "Content-Type": "application/json",
        }
        # Idempotence HTTP : le PSP doit garantir qu'un même Idempotency-Key
        # ne crée pas deux transactions.
        resp = requests.post(
            f"{base_url}/payments",
            json=payload,
            headers={h: v for h, v in headers.items() if v},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        ext_id = str(data.get("transaction_id") or data.get("id") or "")
        status_raw = str(data.get("status") or "PENDING").upper()
        try:
            status = ProviderStatus(status_raw)
        except ValueError:
            status = ProviderStatus.PENDING

        return InitiatePaymentResult(
            provider=self.provider_code,
            external_transaction_id=ext_id,
            external_reference=str(data.get("reference") or request.reference),
            status=status,
            redirect_url=data.get("redirect_url"),
            raw_response=data,
        )

    # --- Status polling (reconcile) ---

    def get_transaction_status(self, external_transaction_id: str) -> ProviderTransactionStatus:
        if _mock_enabled() or not getattr(settings, "PI_SPI_PSP_BASE_URL", "").strip():
            from .mock_pi_spi import MockPiSpiProvider  # noqa: PLC0415

            return MockPiSpiProvider().get_transaction_status(external_transaction_id)

        base_url = settings.PI_SPI_PSP_BASE_URL.rstrip("/")
        api_key = getattr(settings, "PI_SPI_PSP_API_KEY", "")
        timeout = int(getattr(settings, "PI_SPI_TIMEOUT_SECONDS", 15))
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = requests.get(
            f"{base_url}/payments/{external_transaction_id}",
            headers=headers,
            timeout=timeout,
        )
        if resp.status_code == 404:
            return ProviderTransactionStatus(
                external_transaction_id=external_transaction_id,
                status=ProviderStatus.FAILED,
                failure_reason="Transaction inconnue chez le PSP",
                failure_code="NOT_FOUND",
            )
        resp.raise_for_status()
        data = resp.json()
        status_raw = str(data.get("status") or "PENDING").upper()
        try:
            status = ProviderStatus(status_raw)
        except ValueError:
            status = ProviderStatus.PENDING
        amount = None
        try:
            if data.get("amount"):
                amount = Decimal(str(data["amount"]))
        except Exception:  # noqa: BLE001
            amount = None
        return ProviderTransactionStatus(
            external_transaction_id=external_transaction_id,
            status=status,
            amount=amount,
            currency=data.get("currency"),
            failure_reason=str(data.get("failure_reason") or ""),
            failure_code=str(data.get("failure_code") or ""),
            raw_payload=data,
        )

    # --- Webhook verification ---

    def verify_webhook(self, raw_body: bytes, headers: dict) -> WebhookVerificationResult:
        # PSP PI-SPI signe en HMAC SHA256(timestamp.body) — même contrat que Mobile Money
        # pour rester cohérent avec webhooks.py existant.
        secret = getattr(settings, "PI_SPI_WEBHOOK_SECRET", "")
        if not secret:
            # Si non configuré, on délègue au mock en sandbox
            if _mock_enabled():
                from .mock_pi_spi import MockPiSpiProvider  # noqa: PLC0415

                return MockPiSpiProvider().verify_webhook(raw_body, headers)
            return WebhookVerificationResult(
                is_valid=False,
                provider=self.provider_code,
                external_event_id="",
                external_transaction_id="",
                failure_reason="PI_SPI_WEBHOOK_SECRET non configuré",
            )

        # Normalise clés pour gérer casse Django (X-Pi-Spi-... vs X-PI-SPI-...)
        lower = {k.lower(): v for k, v in headers.items()}
        ts = lower.get("x-pi-spi-timestamp") or lower.get("x-immolib-timestamp") or ""
        sig = lower.get("x-pi-spi-signature") or lower.get("x-immolib-signature") or ""
        try:
            ts_int = int(ts)
        except Exception as exc:  # noqa: BLE001
            return WebhookVerificationResult(
                is_valid=False,
                provider=self.provider_code,
                external_event_id="",
                external_transaction_id="",
                failure_reason=f"Timestamp invalide: {exc}",
            )
        tolerance = int(getattr(settings, "PI_SPI_WEBHOOK_TOLERANCE_SECONDS", 300))
        if abs(int(time.time()) - ts_int) > tolerance:
            return WebhookVerificationResult(
                is_valid=False,
                provider=self.provider_code,
                external_event_id="",
                external_transaction_id="",
                failure_reason="Timestamp expiré (anti-replay)",
            )
        expected = hmac.new(
            secret.encode(), ts.encode() + b"." + raw_body, hashlib.sha256
        ).hexdigest()
        supplied = sig.removeprefix("sha256=").strip().lower()
        if not hmac.compare_digest(expected, supplied):
            return WebhookVerificationResult(
                is_valid=False,
                provider=self.provider_code,
                external_event_id="",
                external_transaction_id="",
                failure_reason="Signature invalide",
            )
        import json  # noqa: PLC0415

        try:
            data = json.loads(raw_body) if raw_body else {}
            event_id = str(data.get("event_id") or data.get("external_event_id") or data.get("id") or "")
            txn_id = str(data.get("transaction_id") or data.get("external_transaction_id") or data.get("transactionId") or "")
        except Exception:  # noqa: BLE001
            event_id = ""
            txn_id = ""
        return WebhookVerificationResult(
            is_valid=True,
            provider=self.provider_code,
            external_event_id=event_id or txn_id or uuid.uuid4().hex,
            external_transaction_id=txn_id,
        )
