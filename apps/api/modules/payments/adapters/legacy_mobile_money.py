"""Wrapper legacy Mobile Money pour registry (optionnel)."""

from .base import (
    InitiatePaymentRequest,
    InitiatePaymentResult,
    PaymentProvider,
    ProviderStatus,
    ProviderTransactionStatus,
    WebhookVerificationResult,
)


class LegacyMobileMoneyProvider(PaymentProvider):
    provider_code = "MOBILE_MONEY"

    def initiate_payment(self, request: InitiatePaymentRequest) -> InitiatePaymentResult:
        raise NotImplementedError("Legacy Mobile Money n'initie pas via adapter")

    def get_transaction_status(self, external_transaction_id: str) -> ProviderTransactionStatus:
        return ProviderTransactionStatus(
            external_transaction_id=external_transaction_id,
            status=ProviderStatus.PENDING,
        )

    def verify_webhook(self, raw_body: bytes, headers: dict) -> WebhookVerificationResult:
        from modules.payments.webhooks import verify_mobile_money_webhook_signature  # noqa: PLC0415

        try:
            digest = verify_mobile_money_webhook_signature(
                raw_body=raw_body,
                timestamp=headers.get("X-ImmoLib-Timestamp", ""),
                signature=headers.get("X-ImmoLib-Signature", ""),
            )
            return WebhookVerificationResult(
                is_valid=True,
                provider=self.provider_code,
                external_event_id=digest[:16],
                external_transaction_id="",
            )
        except Exception as exc:  # noqa: BLE001
            return WebhookVerificationResult(
                is_valid=False,
                provider=self.provider_code,
                external_event_id="",
                external_transaction_id="",
                failure_reason=str(exc),
            )
