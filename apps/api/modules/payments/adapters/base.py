"""Abstraction PaymentProvider — Phase 7 (infrastructure extensible).

Le code métier ImmoLib (services.py, views) ne doit jamais dépendre
directement d'un PSP. Chaque prestataire implémente cette interface.

Conception :
- PaymentProvider est l'abstraction (cf. prompt Phase 7)
- ExistingProvider = Mobile Money legacy (via webhook HMAC existant)
- PiSpiProvider = PI-SPI via PSP participant (Model B)
- FutureProvider = Orange/Wave direct si besoin

Le switch PI-SPI BCEAO n'est pas appelé directement par ImmoLib
(non participant régulé). L'adapter parle au PSP partenaire,
qui lui-même est connecté au switch 24/7.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


class ProviderStatus(str, Enum):
    """Statuts normalisés côté ImmoLib (Phase 8)."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REFUNDED = "REFUNDED"


@dataclass(frozen=True)
class InitiatePaymentRequest:
    """Données d'initiation — mapping 1:1 avec PaymentRequest."""

    payment_request_id: UUID
    reference: str  # PR-XXXXXXXX
    rent_charge_id: UUID
    amount: Decimal
    currency: str  # XOF
    tenant_id: UUID
    tenant_phone: str
    tenant_name: str
    payee_account_identifier: str  # IBAN / phone du bailleur
    payee_name: str
    operator: str  # PI_SPI
    idempotency_key: str  # UUID5 deterministe
    metadata: dict


@dataclass(frozen=True)
class InitiatePaymentResult:
    """Réponse du PSP après initiation."""

    provider: str  # ex: PI_SPI
    external_transaction_id: str  # id chez PSP / PI-SPI
    external_reference: str  # référence PSP
    status: ProviderStatus
    redirect_url: str | None = None  # si paiement hébergé
    raw_response: dict | None = None


@dataclass(frozen=True)
class ProviderTransactionStatus:
    """Statut d'une transaction côté PSP (pour reconcile/polling)."""

    external_transaction_id: str
    status: ProviderStatus
    amount: Decimal | None = None
    currency: str | None = None
    failure_reason: str = ""
    failure_code: str = ""
    paid_at: datetime | None = None
    raw_payload: dict | None = None


@dataclass(frozen=True)
class WebhookVerificationResult:
    """Résultat de vérification d'un callback PSP."""

    is_valid: bool
    provider: str
    external_event_id: str
    external_transaction_id: str
    failure_reason: str = ""


class PaymentProvider(abc.ABC):
    """Interface à implémenter par chaque prestataire."""

    provider_code: str  # ex: PI_SPI, MOBILE_MONEY

    @abc.abstractmethod
    def initiate_payment(self, request: InitiatePaymentRequest) -> InitiatePaymentResult:
        """Initie un paiement chez le PSP. Doit être idempotent (key)."""

    @abc.abstractmethod
    def get_transaction_status(self, external_transaction_id: str) -> ProviderTransactionStatus:
        """Requête de statut (reconcile). Utilisé par cron/polling."""

    @abc.abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: dict) -> WebhookVerificationResult:
        """Vérifie signature/auth du webhook PSP. Ne jamais faire confiance aveuglément."""

    def supports_refund(self) -> bool:
        return False

    def refund(self, external_transaction_id: str, amount: Decimal, reason: str):  # pragma: no cover
        raise NotImplementedError("Refund non supporté par ce provider")
