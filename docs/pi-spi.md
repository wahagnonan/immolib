# PI-SPI BCEAO — Intégration ImmoLib (Model B)

**Date**: 27/08/2026 — Branche `feat/pi-spi-bceao` — MVP extensible
**Principe**: ImmoLib n'est PAS participant PI-SPI. Intégration via PSP partenaire déjà connecté au switch BCEAO 24/7 (80 participants au 24/06/2026).

## Architecture

```
Tenant → ImmoLib UI (payment-requests-workspace) → POST /payment-requests/ {PI_SPI}
      → POST /payment-requests/{id}/initiate-pi-spi/ → PaymentProviderAdapter.initiate()
      → PSP partenaire → Switch PI-SPI BCEAO → Banque bénéficiaire
      ← webhook PSP POST /webhooks/pi-spi/ (HMAC timestamp.body) → PaymentProviderEvent idempotent
      → Payment(PI_SPI, CONFIRMED_BY_PROVIDER) → RentCharge recalcule → RentalDocument
```

## Abstraction PaymentProvider (Phase 7)

`modules/payments/adapters/base.py`:

- `PaymentProvider` ABC: `initiate_payment()`, `get_transaction_status()`, `verify_webhook()`
- `ProviderStatus`: PENDING/PROCESSING/SUCCESS/FAILED/CANCELLED/EXPIRED/REFUNDED
- `PiSpiProvider`: live via `PI_SPI_PSP_BASE_URL` + `PI_SPI_PSP_API_KEY` + `PI_SPI_WEBHOOK_SECRET`
- `MockPiSpiProvider`: sandbox/mock quand `PI_SPI_MOCK_ENABLED=true` ou `PI_SPI_MODE=sandbox` sans PSP
- `LegacyMobileMoneyProvider`: wrapper webhook historique
- `registry.py`: `get_provider("PI_SPI")`, auto-register

Avantages: code métier `services.py` indépendant du PSP; ajout futur Orange/Wave sans réécriture.

## Modèles

- `Payment.Method.PI_SPI`, `PaymentMethodAccount.Operator.PI_SPI`, `PaymentRequest.Operator.PI_SPI`
- `PaymentRequest.Status`: + PROCESSING/FAILED/EXPIRED (en plus de PENDING/CONFIRMED/CANCELLED/NOT_RECEIVED)
- Champs PI-SPI sur `PaymentRequest`: `external_transaction_id`, `provider`, `provider_status`, `provider_reference`, `failure_reason`, `expires_at`
- `PaymentProviderEvent.payment_request` FK nullable (traçabilité)
- Contraintes: `one_pending_payment_request_per_charge` (PENDING) + `one_active_payment_request_per_charge` (PENDING|PROCESSING) — empêche double initiation

Migrations: `0005_add_pi_spi.py`, `0006_pi_spi_active_constraint.py`

## Endpoints

| Méthode | URL | Auth | Rôle |
|---|---|---|---|
| `POST` | `/api/v1/payment-requests/` | tenant | création PI_SPI (comme MTN etc.) |
| `POST` | `/api/v1/payment-requests/{id}/initiate-pi-spi/` | tenant demandeur | initiation PSP (idempotent) |
| `GET` | `/api/v1/payment-requests/{id}/pi-spi-status/` | tenant/bailleur lié | polling statut (reconcile) |
| `POST` | `/api/v1/webhooks/pi-spi/` | AllowAny + HMAC | callback PSP (idempotent, vérifie signature, amount, currency) |

Webhook payload générique (PSP-adapté):
```json
{
  "provider": "PI_SPI",
  "event_id": "evt_...",
  "transaction_id": "txn_...",
  "payment_request_id": "uuid",
  "rent_charge_id": "uuid",
  "status": "SUCCEEDED",
  "amount": "100000.00",
  "currency": "XOF",
  "paid_at": "2026-08-05T12:00:00Z"
}
```
Signature: `X-PI-SPI-Timestamp` + `X-PI-SPI-Signature: sha256=HMAC(secret, timestamp.body)` tolérance 300s (comme Mobile Money).

## Services

`modules/payments/services_pi_spi.py`:

- `initiate_pi_spi_payment(tenant, payment_request)` → transaction atomic, vérifie ownership, idempotence via `uuid5(immolib:pi-spi:{request.id})`, appelle adapter, passe à PROCESSING, TTL `PI_SPI_TRANSACTION_TTL_SECONDS` (900s), crée `PaymentProviderEvent` initiation
- `handle_pi_spi_webhook(data)` → idempotence `provider+external_event_id` + `payload_digest`, valide amount/currency/beneficiary vs `PaymentRequest`, vérifie outstanding, crée `Payment(PI_SPI, CONFIRMED_BY_PROVIDER)` + `PaymentAllocation`, recalcule charge, génère `RentalDocument`, passe `PaymentRequest` → CONFIRMED + `NotificationDelivery PAYMENT_CONFIRMED`
- `expire_stale_pi_spi_requests()` → commande `check_pi_spi_expirations`

## Frontend

- `src/types/domain.ts`: `PaymentRequestOperator.PI_SPI`, `PaymentRequestStatus PROCESSING/FAILED/EXPIRED`, champs `external_transaction_id` etc.
- `src/lib/api-client.ts`: `initiatePiSpiPayment(id)`, `getPiSpiStatus(id)`
- `src/components/payments/payment-requests-workspace.tsx`: 
  - Tenant: PENDING PI_SPI → bouton "Payer via PI-SPI" → initiation; PROCESSING → spinner + "En cours PI-SPI" + bouton Actualiser (polling) + Annuler; affichage `provider_status`, `expires_at`, `failure_reason`
  - Bailleur: voit `external_transaction_id` abrégé et statut prestataire

## Configuration

```env
PI_SPI_ENABLED=true
PI_SPI_MODE=sandbox # ou live
PI_SPI_PSP_BASE_URL= # vide → mock en sandbox
PI_SPI_PSP_API_KEY=
PI_SPI_WEBHOOK_SECRET=
PI_SPI_WEBHOOK_TOLERANCE_SECONDS=300
PI_SPI_TIMEOUT_SECONDS=15
PI_SPI_MOCK_ENABLED=true # false en live
PI_SPI_MOCK_AUTO_SUCCESS=false
PI_SPI_TRANSACTION_TTL_SECONDS=900
```

`apps/api/.env.example` et `infrastructure/production.env.example` documentés. En production `PI_SPI_MOCK_ENABLED=false`, `PI_SPI_MODE=live`, secrets via gestionnaire secrets.

## Sécurité (Phase 9)

- Idempotence initiation: `uuid5(request.id)` + vérifie `external_transaction_id` déjà présent → retourne sans ré-appeler PSP
- Idempotence webhook: `PaymentProviderEvent(provider, external_event_id)` unique + `payload_digest` SHA256(raw_body)
- Validation stricte: amount==request.amount, currency==XOF, beneficiary via `PaymentMethodAccount`, outstanding non dépassé, échéance non annulée
- Anti-replay: timestamp HMAC 300s
- Pas de quittance avant confirmation provider (source de vérité = succès webhook)

## Observabilité (Phase 13)

Chaque transaction traçable via `payment_request.reference` (PR-...), `external_transaction_id`, `PaymentProviderEvent`, `Payment.id`, `rent_charge_id`, `tenant_id`, `amount`, `provider_status`. Logs sans PII sensible.

## Tests (Phase 14)

`modules/payments/tests/test_pi_spi.py` (7 tests):

- initiation mock pending + idempotence
- webhook success → payment + receipt + charge PAID
- replay idempotent
- amount mismatch rejeté 400
- signature invalide → 403
- outsider ne peut initier → 403
- polling status

`python -c "from django.test.utils import get_runner ... run_tests(['modules.payments.tests.test_pi_spi'])"` → OK

## Cron

Ajouter à `infrastructure/crontab-prod` ou Render cron:

```
*/5 * * * * /opt/immolib/run-scheduled.sh # déjà inclus
0 * * * * docker compose exec api python manage.py check_pi_spi_expirations
```

Ou intégrer à `run_billing_cycle` si besoin.

## Limites MVP

- Pas de refund PI-SPI (adapter retourne False)
- Pas de paiement partiel via PI-SPI (montant doit == request.amount)
- Pas de génération automatique d'échéances PI-SPI (réutilise `prepare_payment_obligations`)
- Mock sans mouvement réel en sandbox (distinguer via `PI_SPI_MOCK_AUTO_SUCCESS`)

## Prochaines étapes

- Choisir PSP partenaire ivoirien connecté (liste BCEAO) et renseigner `PI_SPI_PSP_BASE_URL` sandbox
- Tester E2E avec PSP sandbox (montants 100-1000 XOF)
- Ajouter monitoring `/health` PI-SPI stall si besoin
