# Audit ImmoLib — Checklist des jalons (fait vs restant)

- **Date de l'audit** : 2026-08-14
- **Branche audité** : `audit-01` (basée sur `sms-01`)
- **Commit de référence** : `68e3028` (feat(sms): integration API Orange SMS CI + web push VAPID + infra production)
- **Périmètre** : vérification statique du code (grep/glob/read), aucune modification applicative.

## Tableau récapitulatif

| Jalon | Statut | % estimé | Détail |
|---|---|---|---|
| 1. Notifications + Orange SMS | ✅ Fait | 95 % | File `NotificationDelivery` + retry, adaptateur Orange complet (OAuth2, segments, DR), tests 6 fichiers |
| 2. WhatsApp | 🟡 Partiel | 80 % | Provider/webhook/adaptateur OK ; templates jamais utilisés, statuts non corrélés à la file |
| 3. Email | 🟡 Partiel | 55 % | Adaptateur SES OK ; aucun SPF/DKIM/DMARC, aucune gestion bounce/complaint |
| 4. Quittances | ✅ Fait | 90 % | Numéro unique, instantané, PDF, statut ACTIVE/VOIDED, partage, invalidation |
| 5. Vérification publique | ✅ Fait | 90 % | OTP hashé, grant signé, throttles, landing + page `/verifier-quittance` |
| 6. Paiements / échéances | ✅ Fait | 85 % | Paiement partiel, P2P, comptes de réception, webhook signé ; pas de rapprochement provider réel |
| 7. RBAC / permissions (IDOR) | ✅ Fait | 85 % | Querysets scopés partout, rôle ADMIN + matrice de permissions, tests sécurité |
| 8. Admin | 🟡 Partiel | 80 % | Backend + frontend complets en lecture ; actions d'écriture limitées (suspension, abonnements) |
| 9. Abonnements | ✅ Fait | 85 % | Plans/quotas/features, PayDunya + pilot mode, expiration, page abonnement |
| 10. i18n | 🟡 Partiel | 35 % | Module backend complet MAIS aucun catalogue traduit (`.po/.mo`), UI 100 % FR |
| 11. Sécurité | 🟡 Partiel | 80 % | OTP hashé, lockout, throttles, secrets hors repo, headers ; pas de CSP, pas de rate-limit abonnement |
| 12. Performance | ✅ Fait | 80 % | Pagination systématique, 94 `select_related/prefetch_related`, index DB, lighthouse + k6 |
| 13. Tests | ✅ Fait | 85 % | 42 fichiers pytest (14 modules), 14 vitest, 5 specs Playwright, CI complète + gitleaks |
| 14. Backup & récupération | 🟡 Partiel | 85 % | backup/restore chiffrés OK ; ligne backup absente de `crontab-prod`, offsite désactivé |
| 15. Déploiement production | 🟡 Partiel | 70 % | Render/nginx/compose/CI OK ; pas de worker planifié sur Render, `render.yaml` sur branche `prod-01`, pas de monitoring |
| 16. Beta / lancement | 🟡 Partiel | 45 % | Landing + pricing + PWA OK ; pas d'onboarding, pas de monitoring/alerte, pas de pages légales |

---

## 1. Notifications + Orange SMS — ✅ 95 %

### Fait
- **File de notifications** : `NotificationDelivery` (`apps/api/modules/documents/models.py:164`) avec 7 kinds, statuts QUEUED/PROCESSING/SENT/FAILED, `attempt_count`, `next_attempt_at`, `provider_reference`, `segments_count`, contraintes d'unicité anti-doublon, index de file (`notification_queue_idx`, :264).
- **Retry avec backoff exponentiel** : `process_notification_batch` et `_mark_failed` (`apps/api/modules/documents/notifications.py:452-470`) — `NOTIFICATION_RETRY_SECONDS × 2^(attempt-1)`, max `NOTIFICATION_MAX_ATTEMPTS=3` (settings.py:214), reprise des traitements orphelins (`recover_stale_deliveries`, :371-394).
- **Architecture multi-fournisseurs** : `NOTIFICATION_ADAPTERS` par canal (settings.py:149-166), chargement dynamique `load_configured_adapters` (notifications.py:85-97), `SimulatedNotificationAdapter` en dev.
- **Module `sms/` complet** :
  - Client OAuth2 v3 avec token en cache 3600 s et renouvellement auto sur 401 code 42 : `apps/api/modules/sms/provider.py:106-153, 243-254`.
  - Segmentation GSM-7/UCS-2 et coût estimé : `sms/segments.py`, coût tracé dans `SmsSendRecord` (`sms/models.py:10-55`, idempotent par `provider_message_id`).
  - Adaptateur avec normalisation E.164, troncature conservant le lien, pacing 5 SMS/s : `sms/adapters.py:36-151`.
  - Webhook DR avec liste blanche d'IP (vide = 503, inconnue = 403) : `sms/api/views.py:27-69` ; payload validé strictement, doublon absorbé, `DeliveryImpossible` ne downgrade jamais `DELIVERED` : `sms/services.py:41-135`.
- **Templates/erreurs/logs** : textes construits via gettext avec langue figée à la mise en file (`documents/notifications.py:100-106`), erreurs structurées (`PermanentNotificationError` vs technique), destinations masquées dans les logs (`sms/provider.py:52-54`).
- **Tests** : 6 fichiers (`sms/tests/test_provider.py`, `test_segments.py`, `test_phones.py`, `test_adapters.py`, `test_services.py`, `test_webhooks.py`) + `documents/tests/test_notifications.py`, `test_reminders.py`.
- **Routes** : `POST /api/v1/webhooks/sms/orange/delivery-receipts/` (`sms/api/urls.py:6-10`, montée dans `config/urls.py:102`).

### Partiel
- La sécurité du webhook DR repose sur la liste d'IP (Orange ne signe pas) — contrainte documentée (`docs/sms/orange.md`), mais `ORANGE_SMS_DR_ALLOWED_IPS` doit être renseignée en production (marquée `sync: false` dans `render.yaml:69-70` : aucun moyen de la récupérer sans échange avec Orange).
- Le worker est un commande ponctuelle (`process_notifications --simulate`), pas un daemon : en auto-hébergement, il dépend de `run-scheduled.sh` (1×/jour) ; un envoi accepté par Orange mais non traité avant le crash est rejoué (au moins une fois, géré par `SmsSendRecord` idempotent).

### Reste à coder
- [ ] Test d'intégration end-to-end contre le sandbox Orange (mocked à ce jour) — vérifier le format réel du `callbackData`.
- [ ] Command `process_notifications` en mode daemon/loop (ou cron plus fréquent, ex. toutes les 5 min) pour des OTP SMS réellement rapides.
- [ ] Alerte quand un `NotificationDelivery` reste QUEUED sans adaptateur (déjà compté `unavailable` mais non alerté).
- [ ] Page d'admin pour afficher `SmsSendRecord` (coût cumulé) — non branchée dans `admin_panel`.

### Risques
- Coût SMS réel non plafonné par compte (seul le quota de maisons limite le volume).
- IP d'Orange changeantes en production → webhook silencieusement rejeté (403) ; prévoir un fallback d'IP documenté.

---

## 2. WhatsApp — 🟡 80 %

### Fait
- **Provider Cloud API** : `apps/api/modules/whatsapp/provider.py` (send text, codes d'erreur permanents 131008/131026/… : :22-24, `send_template_message` :108-125).
- **Adaptateur** branché sur la file : `modules/notifications/adapters.py:107-132` (`WhatsAppCloudApiAdapter`, erreur permanente = téléphone non WhatsApp).
- **Webhook** : handshake GET `hub.challenge` + POST idempotent (`whatsapp/api/views.py:12-45`), messages entrants et statuts persistés via `get_or_create` (`whatsapp/services.py:45-103`).
- **Modèles** : `WhatsAppInboundMessage`, `WhatsAppMessageStatus` avec contrainte `one_whatsapp_status_per_message` (`whatsapp/models.py:62-66`).
- **Opt-in** : `NotificationPreference.whatsapp_opted_in_at` (`notifications/models.py:33`), validé dans le serializer (`notifications/api/serializers.py:55-68`).
- **Tests** : `whatsapp/tests/test_provider.py`, `test_webhooks.py`, `test_adapter.py` ; routage testé (`notifications/tests/test_routing.py:23`).
- **Route** : `GET/POST /api/v1/webhooks/whatsapp/` (`config/urls.py:104-107`).

### Partiel (pourquoi)
- Les **modèles de messages** (`send_template_message`) sont implémentés et testés mais **jamais appelés par l'adaptateur** : la file n'envoie que du texte brut (`notifications/adapters.py:123-125`). Or Meta exige des modèles hors fenêtre de 24 h (rappel de loyer à J+7, quittance à J+30 → risque de rejet 131026).
- Les **statuts reçus** (sent/delivered/read/failed) sont enregistrés mais **jamais corrélés** à `NotificationDelivery.delivery_status` (aucun `provider_reference` joignable : `WhatsAppMessageStatus.message_id` n'est pas relié à la file).
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN` non renseigné par défaut (handshake 403 tant que non configuré).

### Reste à coder
- [ ] `WhatsAppCloudApiAdapter` : envoyer un modèle (`send_template_message`) quand le message sort de la fenêtre de session, avec fallback texte.
- [ ] Corrélation statuts → `NotificationDelivery` (mettre à jour `delivery_status`/`delivered_at` comme le fait Orange, via le `provider_reference` stocké à l'envoi).
- [ ] Écran d'opt-in WhatsApp dans le parcours locataire (l'opt-in est aujourd'hui déclaré côté bailleur via les préférences).
- [ ] Tests du worker avec `WhatsAppCloudApiAdapter` réel (mock du provider).

### Risques
- Envoi de rappels WhatsApp hors modèle → erreurs permanentes `131026` → notifications FAILED définitives ; la promesse « WhatsApp pour les rappels » n'est pas fiable en l'état.

---

## 3. Email — 🟡 55 %

### Fait
- **Adaptateur SES** : `modules/notifications/adapters.py:15-52` (`AmazonSesEmailAdapter`, body texte + HTML escape, message-id comme référence).
- **Templates** : construits par gettext (`documents/notifications.py`), langue figée par delivery (`delivery.language`, :100-106).
- **Routage** : préférence push → email, tenant sans email exclu proprement (`reminders.py:31-37`).
- **Partage manuel** : `mailto:` via `prepare_manual_share` (`documents/services.py:404-410`).

### Partiel (pourquoi)
- **Aucune gestion bounce/complaint** : aucun code SES notification/SNS (grep `bounce|complaint|SNS` : 0 résultat). Une adresse qui bounce reste indéfiniment dans les listes.
- **SPF/DKIM/DMARC** : aucun enregistrement DNS ni documentation dans `infrastructure/` (nginx, render-setup, README). L'email partant de `af-south-1` sans DKIM sera filtré par Gmail/Orange CI.
- `AWS_SES_FROM_EMAIL` vide par défaut → l'adaptateur lève `ImproperlyConfigured` tant que non renseigné ; aucune gestion de liste de suppression.
- `production.env.example` ne contient **aucune** variable AWS SES.

### Reste à coder
- [ ] Documentation DNS : SPF `include:amazonses.com`, DKIM (3 CNAME générés par SES), DMARC ; intégrer dans `docs/` ou `infrastructure/`.
- [ ] Webhook SES (SNS) `bounces`/`complaints` → marquer la delivery FAILED et supprimer le contact des rappels.
- [ ] `production.env.example` : section `AWS_SES_REGION`, `AWS_SES_FROM_EMAIL`.
- [ ] Test du rendu HTML dans un vrai client (les e2e actuels ne couvrent pas le contenu des emails).

### Risques
- Quittances/rappels envoyés par SES non délivrés (spam) sans DKIM : impact direct sur le jalon « fiabilité des rappels ».
- Adresses invalides jamais nettoyées → coût SES et réputation du domaine.

---

## 4. Quittances — ✅ 90 %

### Fait
- **Modèle** : `RentalDocument` (`documents/models.py:14-118`) — référence unique `IMM-REC/QUT/CAU/SOL-AAAA-…` (`documents/services.py:73-74`), snapshot immuable (noms, adresse, période, `breakdown` JSON), statuts ACTIVE/VOIDED avec `void_reason`, contraintes `one_active_*` par paiement/échéance.
- **Génération** : `issue_documents_for_payment` (`documents/services.py:114-201`) — reçu + quittance par échéance soldée + reçu caution ; relevé de caution `issue_security_deposit_settlement_document` (:204-246) ; invalidation à l'annulation `void_documents_after_cancellation` (:249-276).
- **PDF** : `documents/pdfs.py` (reportlab A4, marque IL, statut ACTIF/INVALIDE, filigrane « DOCUMENT INVALIDE », tableau d'affectation, bloc vérification). Nom de fichier `quittance-<ref>.pdf` (:81-87).
- **Routes** : `GET /api/v1/documents/` + filtres, `GET /api/v1/documents/{id}/pdf/` (headers anti-cache, :72-80), `POST .../share/` multi-canal, `POST .../manual-share/` (`documents/api/views.py:83-176`).
- **Lien sécurisé** : `DocumentAccessLink` signé (HMAC via `signing.dumps`, `documents/services.py:285-301`), 30 jours, révocable.
- **Tests** : `documents/tests/test_api.py`, `test_services.py`, `test_notifications.py`.

### Partiel
- Pas d'archive PDF hors BDD (le PDF est régénéré depuis le snapshot — acceptable, le snapshot est immuable).
- Pas d'export groupé (N quittances en ZIP) — feature Pro annoncée (`data_export` dans les features) mais non implémentée.

### Reste à coder
- [ ] Export ZIP / PDF multiple des quittances (feature `data_export`).
- [ ] `voided` côté tenant portal : le locataire voit-il la mention « invalide » ? (PDF oui, liste non vérifiée).

### Risques
- Faible : le snapshot garantit l'intégrité ; surveiller la cohérence `breakdown` si une affectation change après émission.

---

## 5. Vérification publique — ✅ 90 %

### Fait
- **Endpoints** : `PublicDocumentAccessViewSet` (`documents/api/views.py:208-344`) — `verify-reference` (GET, statut minimal, throttle 30/min :55-56), `request-otp` (cooldown 60 s, reuse du challenge), `verify-otp` (grant signé 24 h), `view-document`, `download-document` (PDF après OTP), `payment-response` (confirmation/contestation).
- **OTP** : code 6 chiffres, **hashé** (`salted_hmac`, `documents/services.py:429-436`), `compare_digest`, 5 tentatives max puis expiration, `select_for_update` (:511-544).
- **Throttles** : par IP + par payload hashé (`documents/throttles.py:10-48` : 3/min request, 10/min verify, 60/min grant).
- **Landing** : `apps/web/src/app/page.tsx` (lien « Vérifier une quittance » :102-106) + page dédiée `apps/web/src/app/verifier-quittance/page.tsx`.
- **Sécurité des données** : `verify-reference` ne renvoie ni noms ni téléphones ni adresse (README.md:172-174, doc jalon 26).

### Partiel
- `EXPOSE_TEST_OTP` permet de renvoyer le code en réponse (dev uniquement, bloqué hors DEBUG par settings.py:120-121).
- La vérification par `reference` est limitée à 30 requêtes/min/IP (risque d'énumération doux des références, mais les références contiennent un UUID partiel non énumérable).

### Reste à coder
- [ ] Test Playwright du parcours complet landing → vérifier → OTP → PDF (actuellement couvert par l'API seulement).
- [ ] Message d'erreur côté front quand le lien est révoqué (état 410).

### Risques
- Faible. Surveiller le volume d'OTP SMS généré par des bots (déjà limité par cooldown + throttles).

---

## 6. Paiements / échéances — ✅ 85 %

### Fait
- **Échéances** : `RentCharge` avec `amount_paid`, `amount_released`, statuts temporels (`temporal_status`, `billing/services.py:38-43`, `refresh_temporal_statuses` :252), génération mensuelle idempotente (`generate_monthly_charges`, :216), commande `run_billing_cycle` (bascule J-25).
- **Rappels/relances** : `queue_rent_reminders` (`documents/reminders.py:35-88`) avec offsets J-3/J/J+3/J+7 et canaux AUTO (push puis email), déclenché par `run_billing_cycle`.
- **Paiement partiel/complet** : allocations multiples (`PaymentAllocation`), `record_allocated_offline_payment` (`payments/services.py`), annulation tracée `cancel_payment` + `PaymentEvent` journal append-only (`payments/models.py:228-272`).
- **P2P** : `PaymentRequest` (référence unique, `amount_received` différent du demandé, statuts PENDING/CONFIRMED/NOT_RECEIVED/CANCELLED), `PaymentMethodAccount` (comptes de réception MTN/Orange/Moov/Wave, `payments/models.py:336-500`), notifications `PAYMENT_REQUEST`/`PAYMENT_CONFIRMED`.
- **Rapprochement** : `PaymentProviderEvent` idempotent (unique `provider+event_id`, `payments/models.py:275-333`), webhook signé HMAC SHA-256 avec timestamp (`payments/webhooks.py:12-39`, `MobileMoneyWebhookView` `webhook_views.py:31-84`).
- **Validation manuelle mobile money** : confirmation par le bailleur via `confirm_payment_request` + confirmation/contestation locataire (`confirm_payment_by_tenant`, `dispute_payment_by_tenant`).
- **Caution** : cycle complet REFUND/RETENTION/APPLY_TO_RENT avec preuve d'accord (`SecurityDepositMovement` + contraintes `deposit_movement_target_matches_type`, :163-177).
- **Tests** : 5 fichiers (`test_api`, `test_requests`, `test_security_deposits`, `test_services`, `test_webhooks`).

### Partiel (pourquoi)
- Le webhook Mobile Money est un **contrat générique documenté** (README.md:191-215) : aucun adaptateur provider CI réel (Orange Money/MTN/Moov/Wave) n'est codé ; la production doit l'implémenter.
- Pas de tableau de « rapprochement » (relevé impayés vs encaissements attendus) pour le bailleur ; pas de relance automatique des `PaymentRequest` PENDING après 48 h.

### Reste à coder
- [ ] Adaptateur provider réel (ex. Orange Money API) implémentant le contrat `MobileMoneyWebhookSerializer`.
- [ ] Relance/expiration automatique des `PaymentRequest` en PENDING (cron).
- [ ] Écran « rapprochement » dans l'espace bailleur (feature `unpaid_tracking`/`financial_reports` du plan Pro).
- [ ] Test e2e du flux complet locataire → paiement P2P → confirmation → quittance.

### Risques
- Le secret `MOBILE_MONEY_WEBHOOK_SECRET` vide rend le webhook 503 (sécurisé par défaut) — OK, mais le déploiement doit renseigner ce secret dès le premier PSP.

---

## 7. RBAC / permissions (IDOR) — ✅ 85 %

### Fait
- **Scoping systématique** : tous les querysets passent par des selectors filtrés par utilisateur : `visible_documents_for` (`documents/selectors.py:7-11`), `visible_payments_for` (`payments/selectors.py`), `visible_rent_charges_for` (`billing/selectors.py:8-12`), `manageable_properties_for` (`leases/selectors.py`), `primary_owned_properties_for` (`properties/selectors.py:6-10`).
- **Vérification explicite à la création** : `PaymentViewSet.create` contrôle que chaque `rent_charge_id` appartient aux biens gérables avant d'enregistrer (`payments/api/views.py:109-143`) ; `_assert_can_share` refuse le partage hors biens gérés (`documents/services.py:279-282`).
- **Rôle ADMIN** : `User.role` (`accounts/models.py:13-22`), `admin_panel/permissions.py` (matrice `Perm`, `IsAdmin`, `admin_permission()`), `AdminSessionAuthentication` (401 propre), journal d'audit.
- **Tests de sécurité** : `admin_panel/tests/test_security.py` (matrice ADMIN 200 / bailleur 403 / locataire 403 / anonyme 401).
- **Portail locataire isolé** : endpoints séparés (`tenant_portal/`) avec ses propres selectors (`tenant_portal/selectors.py`), brouillons de bail invisibles.

### Partiel
- Un seul rôle admin (pas de hiérarchie SUPER_ADMIN actif ; prévu dans `permissions.py:49-52`).
- Pas de matrice de tests IDOR par module (maison A vs maison B) au-delà de l'admin ; le scoping est correct statiquement mais non verrouillé par des tests cross-tenant systématiques.

### Reste à coder
- [ ] Série de tests IDOR paramétrés : utilisateur A ne peut ni lire ni écrire sur les objets de B (houses, leases, charges, payments, documents, incidents, invitations) — au moins un test par module.
- [ ] Activer la gestion des admins (création/rotation) dans l'admin UI ou documenter la CLI `create_admin` comme unique voie.
- [ ] Vérifier `NotificationDeliveryViewSet` : il expose les deliveries liées aux objets visibles, y compris `body` des OTP (déjà masqué côté front ?) — à confirmer par un test.

### Risques
- Élevé si régression : un queryset non scopé sur une route Retrieve expose les données d'un autre bailleur. Les tests IDOR par module sont le filet de sécurité manquant.

---

## 8. Admin — 🟡 80 %

### Fait
- **Backend** : `admin_panel/` — dashboard + métriques (`services.dashboard_metrics`), séries utilisateurs/revenus/maisons, listes paginées users/landlords/tenants/houses/subscriptions/payments/notifications/audit-logs (`admin_panel/api/views.py:51-281`), actions abonnements (change_plan, extend, activate, cancel) et suspension utilisateur, journal d'audit append-only (`admin_panel/models.py:8-49`, `audit.py`), commande `create_admin`.
- **Frontend** : `apps/web/src/app/admin/` (9 pages : users, landlords, tenants, houses, subscriptions, payments, notifications, audit-logs, dashboard) + workspaces (`components/admin/*.tsx`, 10 composants + 3 tests vitest).
- **Tests** : `admin_panel/tests/test_api.py` + `test_security.py`.

### Partiel (pourquoi)
- Lecture seule pour la plupart des ressources : pas de détail/édition d'une maison, d'un paiement, d'une notification ; pas de modification d'un utilisateur (hors suspension) ; pas de gestion des admins (SUPER_ADMIN réservé).
- Le dashboard admin du frontend dépend de séries temporelles non testées e2e.
- Pas d'export CSV des listes admin.

### Reste à coder
- [ ] Actions admin manquantes : détail + édition utilisateur (email, rôle), détail maison/locataire, forcer l'expiration d'un abonnement, invalider un document.
- [ ] Export CSV des listes (users, paiements, notifications).
- [ ] Notifications d'alerte dans le dashboard (file bloquée, webhooks en erreur, SMS coût cumulé).
- [ ] E2E Playwright du parcours admin complet.

### Risques
- Modéré : l'admin doit pouvoir débloquer un utilisateur coincé (OTP, abonnement) — aujourd'hui limité à la suspension/abonnement.

---

## 9. Abonnements — ✅ 85 %

### Fait
- **Plans** : Gratuit/Essentiel/Pro avec `max_houses` et liste de features (`settings.py:258-320`), seed via migration `0002_seed_plans_and_free_subscriptions`.
- **Quotas** : `get_usage`/`can_create_house`/`assert_can_create_house` (`subscriptions/services.py:163-191`), feature gating `has_feature`/`assert_has_feature` avec erreurs 403 structurées (`FeatureDenied`, `HouseLimitReached`).
- **Expiration** : lazy à la lecture (`_is_active`, :135-144) + commande `check_subscription_expirations` + endpoint admin ; jamais de suppression de données.
- **PayDunya** : checkout hébergé + confirmation authentifiée du token (`paydunya.py:56-118`), IPN `webhooks/paydunya/` (la confiance repose sur la re-confirmation serveur, `views.py:147-174`), refresh transaction, mode pilote tracé `MANUAL/SUCCESSFUL` avec garde production (`services.py:279-282`).
- **Frontend** : page `/abonnement` (`apps/web/src/app/abonnement/page.tsx`), grille tarifaire sur la landing (`page.tsx:57-80`).
- **Tests** : `subscriptions/tests/test_api.py`, `test_services.py`, `test_paydunya.py`.

### Partiel
- Pas de **renouvellement automatique** (facture récurrente) : l'expiration revient au plan Gratuit ; l'utilisateur doit re-souscrire manuellement.
- Pas de reçu/facture de l'abonnement (documents locatifs seulement).
- `PILOT_MODE` doit être basculé en production avec les vraies clés PayDunya (`render.yaml:51-52` le fait, bien).

### Reste à coder
- [ ] Renouvellement automatique (cron mensuel + facture PayDunya récurrente ou relance manuelle par email).
- [ ] Document « reçu d'abonnement » (PDF) et historique des transactions dans l'UI.
- [ ] Réflexion quotas : forcer la dégradation des biens au-delà du quota après expiration (aujourd'hui : blocage à la création seulement).

### Risques
- Modéré : sans renouvellement auto, le chiffre d'affaires dépend d'un rappel ; à planifier avant le lancement payant réel.

---

## 10. i18n — 🟡 35 %

### Fait (backend)
- Module `i18n/` complet : registre des langues (`languages.py` — fr/en/es/pt/ar actives), middleware `ImmoLocaleMiddleware` (profil → cookie → Accept-Language → fr, `i18n/middleware.py:23-56`), préférences par compte (`/api/v1/profile/preferences/`), formats devise/date (`i18n/format.py`), fuseaux, devises (`i18n/currencies.py`, `timezones.py`).
- Tous les textes backend passent par gettext (`documents/notifications.py`, `reminders.py`, serializers, erreurs 403 abonnement…).
- Tests : `i18n/tests/test_middleware.py`, `test_api.py`, `test_registries.py`.

### Partiel (pourquoi)
- **Aucun catalogue de traduction** : le dossier `apps/api/locale/` **n'existe pas** (Test-Path : False) — pas de fichier `.po`/`.mo`. `LANGUAGE_CODE = "fr"` (settings.py:101) et aucune langue alternative n'est réellement traduite : un utilisateur EN recevra des messages français.
- **PDF 100 % français** : mois codés en dur (`pdfs.py:40-53`), textes des quittances en dur (:361-392) — pas de gettext dans le PDF.
- **Frontend 100 % français** : `html lang="fr"` (`apps/web/src/app/layout.tsx:74`), aucun framework i18n (grep `useTranslation/i18n` : seulement `i18n-iso-countries` pour les indicatifs téléphoniques), landing et toutes les pages hardcodées en français.
- Les templates SMS/WhatsApp/email suivent gettext mais resteront en FR tant que les catalogues n'existent pas.

### Reste à coder
- [ ] Générer les catalogues `locale/en/LC_MESSAGES/*.po` (makemessages), traduire, compiler (compilemessages), activer la bascule UI.
- [ ] i18n des PDF (au minimum EN, en passant les libellés par gettext).
- [ ] Framework i18n frontend (ex. next-intl) + bascule langue dans `parametres`.
- [ ] Landing bilingue FR/EN.
- [ ] Test e2e de bascule de langue et des notifications EN.

### Risques
- Élevé pour un lancement international ; modéré pour un lancement CI uniquement francophone (aucune promesse EN aujourd'hui).

---

## 11. Sécurité — 🟡 80 %

### Fait
- **OTP hashés** : `AccountOtpChallenge.code_hash` (salted_hmac, `accounts/services.py:84-87`) et `OtpChallenge.code_hash` (`documents/services.py:433-436`), comparaison `compare_digest`, tentatives plafonnées.
- **Verrouillage login** : cache avec `LOGIN_LOCKOUT_MAX_ATTEMPTS=10`/fenêtre 900 s/durée 300 s (`accounts/services.py:27-49`), throttles email 10/min (`accounts/throttles.py:41-52`).
- **Rate limiting** : par IP (`RegisterIpThrottle` 100/h, `PublicAuthIpThrottle` 300/min, `PublicDocumentIpThrottle` 30/min), par téléphone (5/h), par payload hashé (OTP document 3/min, 10/min).
- **Validation** : sérialiseurs DRF + `full_clean` dans les services (ex. paiements), contraintes DB (CheckConstraint positives, statuts).
- **Uploads** : aucun `FileField`/`ImageField` dans le projet (grep : 0) → surface d'attaque nulle mais fonctionnalité absente.
- **Secrets hors repo** : `.gitignore` (`infrastructure/production.env`, `.env.*`), `.env.example` sans secrets réels, `production.env` non tracké (git ls-files le confirme), CI gitleaks (`.github/workflows/ci.yml:197-204`).
- **Web** : headers Next (`next.config.ts` : nosniff, X-Frame-Options DENY, Referrer-Policy, Permissions-Policy), `settings_production.py` (HSTS 1 an + preload, SSL redirect, cookies secure, `X_FRAME_OPTIONS=DENY`, `SECURE_CONTENT_TYPE_NOSNIFF`), sessions HttpOnly SameSite=Lax, CSRF double soumission via proxy same-origin.
- **Fail-fast** : `DEBUG=False` sans SECRET_KEY → RuntimeError (settings.py:11-12) ; `EXPOSE_TEST_OTP` interdit hors DEBUG (:120-121).

### Partiel
- **Pas de CSP** (Content-Security-Policy) dans `next.config.ts` (seulement les 4 headers cités).
- Pas de rate-limit dédié sur `/api/v1/subscription/upgrade/` et `/public-access/payment-response/`.
- Login lockout basé sur `cache` : OK en mono-processus, fragile avec plusieurs workers Gunicorn sans cache partagé (locmem par défaut) — en production `gunicorn --workers 3` (`compose.yaml`) → le lockout n'est PAS partagé entre workers.
- Pas de `security.txt`, pas de rotation documentée des secrets.

### Reste à coder
- [ ] En-tête CSP stricte sur Next (ou gating) — priorité basse/moyenne.
- [ ] Cache partagé (Redis/Memcached) pour le lockout login et les throttles en multi-workers, ou `--workers 1` documenté.
- [ ] Throttles sur les endpoints d'abonnement et `payment-response`.
- [ ] Test e2e anti-brute-force (10 tentatives → 429) déjà présent ? (test_api accounts — vérifier la couverture du lockout).

### Risques
- Élevé à moyen selon le mode de déploiement : le lockout non partagé est un écart réel à corriger avant production.

---

## 12. Performance — ✅ 80 %

### Fait
- **Pagination systématique** : `LargeListPagination` (`config/pagination.py:4-13`, 25 par page, max 100) appliquée aux listes (payments, documents, notification-deliveries, admin, tenants…).
- **N+1 maîtrisé** : 94 occurrences de `select_related`/`prefetch_related` couvrant les vues principales (payments/api/views.py:77, documents/api/views.py:92,186, tenant_portal/selectors.py, admin_panel/selectors.py, maintenance, leases, properties…).
- **Index DB** : index explicites dans les migrations (ex. `payment_status_received_idx`, `notification_queue_idx`, `rental_doc_status_issued_idx`, `sms_send_record_stats_idx`, `audit_*_idx`, `ntf_delivery_status_idx`).
- **Frontend** : tableau de bord agrégé serveur (`DashboardOverviewView` calcule les indicateurs, `billing/api/dashboard_views.py`), Recharts avec 6 lignes seulement.
- **Scripts** : `apps/web/scripts/lighthouse.mjs` (seuils perf 70 / a11y 90 / best-practices 80 / SEO 80) + workflow `perf.yml` (dispatch manuel), k6 (`scripts/k6/load.js`, `stress.js` — 50/500 VU) + `load.yml`.

### Partiel
- Pas de cache HTTP/API (pas de Redis), pas de CDN pour le front (Render free), pas de `gzip` explicite (Next `compress: true`).
- Les tests k6/lighthouse sont en dispatch manuel, pas dans la CI quotidienne.
- `db.sqlite3` en dev ; en prod PostgreSQL — aucune migration de données volumineuses testée (index partiels, `CONN_MAX_AGE=60` OK).

### Reste à coder
- [ ] Rapport Lighthouse dans la CI sur `main` (seuil bloquant) — ou au moins sur `prod-01`.
- [ ] Test k6 sur l'API avec Postgres (le CI e2e utilise Postgres, mais pas le load test).
- [ ] Audit des requêtes lentes (envisager `django-silk` en staging ou EXPLAIN sur les listes paginées).

### Risques
- Faible pour le volume MVP ; à re-mesurer après le premier millier de comptes.

---

## 13. Tests — ✅ 85 %

### Fait
- **Backend (pytest/Django)** : 42 fichiers `test_*.py` répartis sur 14 modules : accounts (2), admin_panel (2), billing (3), documents (4), i18n (3), leases (3), maintenance (1), notifications (3), payments (5), properties (3), sms (6), subscriptions (3), tenant_portal (1), whatsapp (3).
- **Frontend (vitest)** : 14 fichiers (`components/admin/*.test.tsx` ×3, `components/auth/*` ×4, houses, maintenance, subscription, ui ×3, `lib/web-push.test.ts`).
- **E2E (Playwright)** : `apps/web/e2e/` — `auth.setup.ts`, `auth.spec.ts`, `parcours-complets.spec.ts`, `accessibilite.spec.ts`, `responsive.spec.ts` + `global-setup.ts` (identité jetable), config multi-navigateurs (`playwright.config.ts`).
- **CI** : `.github/workflows/ci.yml` — 5 jobs : backend (`makemigrations --check`, `manage.py check`, tests), frontend lint/typecheck/build/audit, unit vitest, e2e complet sur Postgres + check-links, gitleaks.
- Note : `python manage.py test` (test runner Django natif) existe bien et est utilisé par la CI ; pas de pytest.

### Partiel
- Pas de seuils de couverture (pas de `--cov` bloquant ni badge).
- Pas de tests des commandes cron (`run_billing_cycle` couvert via `test_services`/`test_reminders`, mais pas la commande elle-même).
- `docs/testing/tests-utilisateurs.md` documente des tests manuels non automatisés.

### Reste à coder
- [ ] Seuil de couverture par module (ex. ≥ 80 % sur sms, payments, subscriptions) et badge.
- [ ] Tests unitaires des commandes (`run_billing_cycle`, `check_subscription_expirations`, `create_admin`).
- [ ] E2E : parcours admin, parcours abonnement PayDunya (mocké), parcours P2P locataire.

### Risques
- Faible : la suite est riche ; le manque de couverture sur les commandes cron est le principal angle mort.

---

## 14. Backup & récupération — 🟡 85 %

### Fait
- `infrastructure/backup.sh` : dump PostgreSQL chiffré **AES-256-CBC + PBKDF2**, rotation locale `RETENTION_DAYS=14`, option hors site `BACKUP_OFFSITE_CMD` (rclone, désactivé par défaut).
- `infrastructure/restore.sh` : déchiffrement + `pg_restore --clean`, usage documenté.
- `infrastructure/crontab-prod` : exécution quotidienne 08:30 de `run-scheduled.sh` (run_billing_cycle + process_notifications + check_subscription_expirations) sous `flock`.

### Partiel (pourquoi)
- **La ligne de backup est absente de `crontab-prod`** : le commentaire de `backup.sh:9-10` dit d'ajouter `45 2 * * * root /opt/immolib/backup.sh` à `/etc/cron.d/immolib`, mais `crontab-prod` ne contient que la ligne 08:30 (grep `backup` : 0 résultat). En suivant la procédure telle quelle, **aucune sauvegarde n'est planifiée**.
- Hors site désactivé par défaut (`BACKUP_OFFSITE_CMD` vide) : pas de sauvegarde hors serveur → perte totale en cas de sinistre du serveur.
- Restauration jamais testée en CI (aucun job de restauration).

### Reste à coder
- [ ] Ajouter la ligne de sauvegarde à `crontab-prod` (et documenter le fichier unique comme source de vérité).
- [ ] Configurer `BACKUP_OFFSITE_CMD` (rclone/S3) et documenter la clé de chiffrement dans le gestionnaire de secrets.
- [ ] Job CI (ou script) de test de restauration hebdomadaire sur une base jetable.

### Risques
- Élevé en l'état : sans ligne backup dans le cron, le jalon « sauvegarde » est en réalité non opérationnel.

---

## 15. Déploiement production — 🟡 70 %

### Fait
- **Render** : `infrastructure/render.yaml` (blueprint : base Postgres free + `immolib-api` Docker avec migrations au démarrage + health `/health/` + `immolib-web`), procédure complète `render-setup.md`.
- **Self-hosted** : `compose.yaml` (db + api gunicorn 3 workers + web), `nginx-app-immolib.conf` (TLS certbot, proxy `/backend` via web:3000, limite 20m), `production.env.example`, `settings_production.py` (HSTS, cookies secure, WhiteNoise, `manage.py check --deploy` documenté dans `infrastructure/README.md`).
- **CI/CD** : `ci.yml` (5 jobs dont gitleaks), `load.yml` et `perf.yml` (dispatch manuel).
- **Worker/cron** : `run-scheduled.sh` (flock) + `crontab-prod` pour l'auto-hébergement ; commandes Django créées (`run_billing_cycle`, `process_notifications`, `check_subscription_expirations`, `create_admin`, `seed_demo_data`).

### Partiel (pourquoi)
- **Render n'a pas de worker planifié** : `render.yaml` ne déclare aucun cron/worker pour `run_billing_cycle`/`process_notifications`/`check_subscription_expirations` — sur Render (test avec les amis), les rappels et la file ne tournent jamais sauf action manuelle.
- `render.yaml` pointe sur la branche **`prod-01`** (branche de test, `render-setup.md` le confirme) — à basculer sur `main` avant le lancement.
- `production.env.example` **incomplet** : manquent VAPID (publique/privée), AWS SES, Firebase, `MOBILE_MONEY_WEBHOOK_SECRET`, clés PayDunya, `SUBSCRIPTION_*`, `IMMOLIB_PUSH_NOTIFICATION_ADAPTER`, `DATABASE_URL`.
- Pas de déploiement automatique sur `main` (pas de workflow deploy), pas de monitoring/alerting (aucun Sentry/Prometheus — 0 occurrence), pas de gestion des IP du webhook Orange en prod.

### Reste à coder
- [ ] Service cron sur Render (ou Background Workers) pour `run_billing_cycle`, `process_notifications` (toutes les ~5 min) et `check_subscription_expirations`.
- [ ] Compléter `production.env.example` (toutes les variables citées dans settings.py).
- [ ] Basculer `render.yaml` sur `main` + workflow de déploiement automatique.
- [ ] Monitoring : erreurs serveur (Sentry ou équivalent léger), health check externe (UptimeRobot), alertes file de notifications bloquée.

### Risques
- Élevé : en configuration Render telle quelle, **aucun rappel de loyer n'est envoyé** (le worker n'est jamais invoqué).

---

## 16. Beta / lancement — 🟡 45 %

### Fait
- Landing complète (`apps/web/src/app/page.tsx`, 574 lignes : hero, services, fonctionnement, tarifs, FAQ, footer) avec SEO/OG (`metadata`, canonical), grille tarifaire, marque « IL Trace » (`public/immolib-mark.svg`), PWA (`public/sw.js`, `components/pwa/register-service-worker.tsx`), `/llms.txt`.
- Page publique de vérification de quittance (jalon 5).
- `seed_demo_data` pour le jeu de démo ; `docs/testing/tests-utilisateurs.md` pour les tests manuels.

### Partiel / manquant
- **Onboarding** : aucun parcours de bienvenue post-inscription (grep « onboarding » : 0) — l'utilisateur arrive directement sur un tableau de bord vide sans guide (créer maison → inviter locataire → créer bail).
- **Monitoring** : aucun (voir jalon 15) — pas de Sentry frontend/backend, pas d'analytics, pas de journal d'erreurs client.
- **Pages légales** : pas de CGU, politique de confidentialité, mentions légales (essentielles pour un service traitant des données locatives et téléphoniques).
- Pas de contact/support dans l'app (que le footer).
- Pas de programme de feedback (in-app), pas de changelog.

### Reste à coder
- [ ] Onboarding : checklist de démarrage (3 étapes : maison, locataire, bail) avec liens directs + état vide du tableau de bord amélioré.
- [ ] Pages CGU / confidentialité / mentions + liens dans le footer et à l'inscription.
- [ ] Monitoring minimal : Sentry (frontend + backend) ou équivalent, alertes email, erreurs JS captées.
- [ ] Formulaire de contact/support (email).
- [ ] Changelog public (page `/changelog` ou GitHub Releases).

### Risques
- Modéré : un bailleur perdu au premier usage ne revient pas ; l'absence de monitoring rend aveugles les incidents de la bêta.

---

## Priorités recommandées (top 10 par impact/risque)

| # | Chantier | Justification | Branche suggérée |
|---|---|---|---|
| 1 | **Worker/planification en production** : service cron Render + compléter `crontab-prod` (backup manquante, fréquence notifications) | Sans worker, aucun rappel, aucune notification, aucune sauvegarde : 3 jalons « faits » inopérants | `prod-01` |
| 2 | **i18n réel** : catalogues `locale/*` (EN), i18n PDF + frontend (next-intl), bascule langue | Jalon 10 à 35 % ; promesse produit FR/EN non tenue ; impact perception international | `i18n-01` (nouvelle) |
| 3 | **Email production** : doc DNS SPF/DKIM/DMARC, webhook SES bounce/complaint, compléter `production.env.example` | Sans DKIM/bounce, délivrabilité faible et adresses mortes jamais nettoyées | `prod-01` ou `correction-01` |
| 4 | **Monitoring + alertes** : Sentry (ou équivalent), health checks externes, alerte file bloquée / webhook en erreur | Bêta aveugle aujourd'hui ; indisponibilité silencieuse | `prod-01` |
| 5 | **Tests IDOR cross-tenant par module + lockout partagé** (Redis) | Filet de sécurité du multi-tenant ; lockout non partagé entre workers gunicorn | `correction-01` |
| 6 | **WhatsApp templates + corrélation des statuts** vers `NotificationDelivery` | Évitement des rejets 131026 hors fenêtre 24 h ; promesse « statuts envoyé/livré/lu » | `whatsapp-01` |
| 7 | **Abonnements : renouvellement automatique + reçu d'abonnement + compléter `production.env.example` PayDunya** | CA récurrent ; facturation pré-lancement | `abonnements-01` |
| 8 | **Admin : actions d'écriture manquantes + export CSV + alerte file SMS** | Opérationnalité support (déblocage, invalidation, exports) | `admin-01` |
| 9 | **Onboarding post-inscription + pages légales + support** | Rétention bêta ; conformité données locatives | `correction-01` |
| 10 | **Adaptateur Mobile Money réel (Orange Money/MTN CI) + rapprochement bailleur + relance PaymentRequest PENDING** | Le webhook générique n'est pas un PSP ; jalon 6 à 85 % | `paiement-01` |

---

## Notes de méthode

- Vérification statique uniquement : grep/glob/read sur la branche `audit-01` (commit `68e3028`), aucune suite de tests exécutée (la CI est la source de vérité pour l'exécution : `.github/workflows/ci.yml` lance `python manage.py test` et `npx playwright test`).
- Les « ✅ Fait » signifient « présent et cohérent dans le code », pas « vérifié par une exécution en environnement réel » (ex. envoi Orange réel non testé).
- Le dossier `docs/audit/` est créé pour ce livrable ; aucun fichier applicatif n'a été modifié.