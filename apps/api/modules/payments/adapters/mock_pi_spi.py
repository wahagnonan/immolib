"""Adapter mock pour tests/sandbox sans PSP réel.

Ne jamais considérer comme réel — Phase 18 : distinguer sandbox/test et production.
En production avec PI_SPI_MODE=live et PI_SPI_MOCK_ENABLED=False, ce provider
n'est jamais utilisé (PiSpiProvider prend le relais).
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from decimal import Decimal

from django.conf import settings

from .base import (
    InitiatePaymentRequest,
    InitiatePaymentResult,
    PaymentProvider,
    ProviderStatus,
    ProviderTransactionStatus,
    WebhookVerificationResult,
)

_MOCK_STORE: dict[str, ProviderTransactionStatus] = {}


def _mock_signature(raw_body: bytes, timestamp: str) -> str:
    secret = getattr(settings, "PI_SPI_WEBHOOK_SECRET", "") or "mock-secret"
    payload = timestamp.encode() + b"." + raw_body
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class MockPiSpiProvider(PaymentProvider):
    provider_code = "MOCK_PI_SPI"

    def initiate_payment(self, request: InitiatePaymentRequest) -> InitiatePaymentResult:
        # Idempotence via idempotency_key dans metadata
        ext_id = f"mock-{uuid.uuid5(uuid.NAMESPACE_URL, request.idempotency_key).hex[:12].upper()}"
        status = ProviderStatus.PENDING
        # En mock, on peut simuler succès immédiat si amount < 500000
        # pour permettre tests sans webhook
        if getattr(settings, "PI_SPI_MOCK_AUTO_SUCCESS", False):
            status = ProviderStatus.SUCCESS
            _MOCK_STORE[ext_id] = ProviderTransactionStatus(
                external_transaction_id=ext_id,
                status=ProviderStatus.SUCCESS,
                amount=request.amount,
                currency=request.currency,
                paid_at=None,
            )
        else:
            _MOCK_STORE[ext_id] = ProviderTransactionStatus(
                external_transaction_id=ext_id,
                status=ProviderStatus.PENDING,
                amount=request.amount,
                currency=request.currency,
            )
        return InitiatePaymentResult(
            provider=self.provider_code,
            external_transaction_id=ext_id,
            external_reference=request.reference,
            status=status,
            raw_response={"mock": True, "request_reference": request.reference},
        )

    def get_transaction_status(self, external_transaction_id: str) -> ProviderTransactionStatus:
        return _MOCK_STORE.get(
            external_transaction_id,
            ProviderTransactionStatus(
                external_transaction_id=external_transaction_id,
                status=ProviderStatus.PENDING,
                failure_reason="Transaction inconnue en mock",
            ),
        )

    def verify_webhook(self, raw_body: bytes, headers: dict) -> WebhookVerificationResult:
        lower = {k.lower(): v for k, v in headers.items()}
        ts = lower.get("x-pi-spi-timestamp", "") or lower.get("x-immolib-timestamp", "")
        sig = lower.get("x-pi-spi-signature", "") or lower.get("x-immolib-signature", "")
        if not ts or not sig:
            return WebhookVerificationResult(
                is_valid=False,
                provider=self.provider_code,
                external_event_id="",
                external_transaction_id="",
                failure_reason="Headers manquants",
            )
        try:
            expected = _mock_signature(raw_body, ts)
            if not hmac.compare_digest(expected.lower(), sig.lower()):
                return WebhookVerificationResult(
                    is_valid=False,
                    provider=self.provider_code,
                    external_event_id="",
                    external_transaction_id="",
                    failure_reason="Signature invalide",
                )
            # Anti-replay : tolérance
            if abs(int(time.time()) - int(ts)) > getattr(settings, "PI_SPI_WEBHOOK_TOLERANCE_SECONDS", 300):
                return WebhookVerificationResult(
                    is_valid=False,
                    provider=self.provider_code,
                    external_event_id="",
                    external_transaction_id="",
                    failure_reason="Timestamp expiré",
                )
        except Exception as exc:  # noqa: BLE001
            return WebhookVerificationResult(
                is_valid=False,
                provider=self.provider_code,
                external_event_id="",
                external_transaction_id="",
                failure_reason=str(exc),
            )
        # Parse event_id / txn_id depuis body si possible
        import json  # noqa: PLC0415

        try:
            data = json.loads(raw_body)
            event_id = str(data.get("event_id") or data.get("external_event_id") or "")
            txn_id = str(data.get("transaction_id") or data.get("external_transaction_id") or "")
        except Exception:  # noqa: BLE001
            event_id = ""
            txn_id = ""
        return WebhookVerificationResult(
            is_valid=True,
            provider=self.provider_code,
            external_event_id=event_id,
            external_transaction_id=txn_id,
        )

    @staticmethod
    def _test_signature(raw_body: bytes, timestamp: str | None = None) -> tuple[str, str]:
        if timestamp is None:
            timestamp = str(int(time.time()))
        return timestamp, _mock_signature(raw_body, timestamp)
