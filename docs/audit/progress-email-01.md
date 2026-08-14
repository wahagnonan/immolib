# Suivi du jalon 3 (Email) — branche `email-01`

- **Objectif** : faire passer le jalon « 3. Email » de 55 % à ~90 % selon la
  checklist d'audit (`docs/audit/checklist-jalons.md`).
- **Périmètre autorisé** : `modules/notifications/adapters.py`,
  `modules/notifications/api/`, `modules/notifications/tests/`,
  `config/urls.py`, `.env.example`, `docs/`. Hors périmètre (autres agents) :
  `config/settings.py`, `settings_production.py`, `requirements.txt`,
  `compose.yaml`, `infrastructure/`, `i18n/`, `locale/`, `apps/web/`.

## Avancement

| Tâche | État |
|---|---|
| 1. Webhook SES (SNS) bounce/complaint + tests | ✅ fait |
| 2. Guide DNS SPF/DKIM/DMARC (`docs/email/configuration.md`) | ✅ fait |
| 3. Audit templates email (doublons de logique) | ✅ fait (aucun doublon) |
| 4. Journalisation structurée masquée (envois + événements) | ✅ fait |
| Vérification : `manage.py test modules.notifications modules.documents` | ✅ 67/67 |

## 1. Webhook SES (SNS) — design

Fichiers :

- `apps/api/modules/notifications/api/ses_notifications.py` — validation,
  signature, traitement (services).
- `apps/api/modules/notifications/api/ses_webhook.py` — vue DRF
  `SesBounceComplaintWebhookView`.
- Route : `POST /api/v1/webhooks/email/ses/` (montée dans `config/urls.py`).
- Variables : `AWS_SES_SNS_TOPIC_ARN`, `AWS_SES_CONFIGURATION_SET`
  (documentées dans `.env.example`).

### Validation

1. **Structure** : JSON → objet dict ; `Type` ∈ {Notification,
   SubscriptionConfirmation, UnsubscribeConfirmation} ; `MessageId`,
   `TopicArn`, `Signature` obligatoires (sinon 400).
2. **Topic** : `TopicArn` doit être exactement égal à
   `AWS_SES_SNS_TOPIC_ARN` (sinon 403). ARN vide → webhook **503** (fermé
   par défaut, même logique que la liste d'IP Orange).
3. **Fraîcheur** : `Timestamp` > 5 min → 400 (anti-rejeu).
4. **Signature RSA** (versions 1 et 2, SHA1/SHA256) : vérifiée avec le
   certificat `SigningCertURL` — hôte restreint à
   `sns.<region>.amazonaws.com` (anti-SSRF, la région provient du TopicArn),
   certificats mis en cache (lru_cache). Échec → 403.
5. **SubscriptionConfirmation** : confirmation automatique via
   `SubscribeURL` (hôte SNS vérifié) ; sinon confirmation manuelle en
   console documentée.

### Idempotence

SNS délivre au moins une fois : toutes les mises à jour de
`NotificationDelivery` sont conditionnelles (`.exclude(status=FAILED)`,
`.exclude(delivery_status=DELIVERED)`). Un rejeu du même événement ne
modifie rien (`correlated=false` en réponse) — vérifié par test.

### Mapping des statuts

| Événement SES | Action sur la delivery |
|---|---|
| Bounce Permanent | `status=FAILED`, `delivery_status=FAILED`, `failure_reason="SES bounce permanent (<sous-type>)"`, `next_attempt_at=None` — jamais de downgrade d'une delivery DELIVERED |
| Bounce Transient / Undetermined | log uniquement (masqué), pas de changement (SES/file peuvent retenter) |
| Complaint | log uniquement (masqué) — l'adresse peut rester valide ; alimente une future liste de suppression |
| Delivery | accepté, ignoré |
| Bounce sans `mail.messageId` | log, `correlated=false` (aucune référence) |

Corrélation : `mail.messageId` ↔ `NotificationDelivery.provider_reference`
(le MessageId SES stocké par l'adaptateur à l'envoi).

### Configuration set

SES ne publie les événements que si le message référence un configuration
set : l'adaptateur passe désormais `ConfigurationSetName` quand
`AWS_SES_CONFIGURATION_SET` est renseigné (optionnel).

## 2. Guide DNS

`docs/email/configuration.md` : SPF (`v=spf1 include:amazonses.com ~all`),
DKIM Easy DKIM (3 CNAME `<token>._domainkey.<domaine>` →
`<token>.dkim.amazonses.com`), DMARC (`p=quarantine`, `adkim=s`, `aspf=r`),
MAIL FROM personnalisé (MX `feedback-smtp.af-south-1.amazonses.com`), sortie
du bac à sable SES, création topic SNS + configuration set, vérifications
DNS.

## 3. Templates email — audit

- Tous les contenus (quittance/confirmation/rappel/invitation/OTP) sont
  construits au seul endroit central : `modules/documents/notifications.py`
  (gettext, langue figée par `delivery.language`), rendu HTML dans
  `AmazonSesEmailAdapter` (escape + wrapper). **Aucun doublon de logique
  d'envoi email** trouvé hors du système de file.
- Le `mailto:` de `documents/services.py:409` est le partage *manuel*
  (l'appareil du bailleur ouvre son client mail) : intentionnel, hors file.
- Signalé dans la checklist : `production.env.example` (infrastructure/)
  ne contient pas les variables SES — à compléter par l'agent
  infrastructure (hors périmètre).

## 4. Logs

- Adaptateur SES : `email.send.ok delivery_id=... destination=<masqué>
  reference=...` — masquage `pré***@domaine` (réutilise `mask_email`).
- Webhook : `ses.sns.rejected` (not-configured/signature/topic/cert-url),
  `ses.sns.invalid_payload`, `ses.sns.subscription`, `ses.bounce.permanent`
  (destinations masquées, `correlated`), `ses.bounce.transient`,
  `ses.complaint.received` (masqué + feedback type), `ses.delivery.received`.
  Les adresses ne sont jamais journalisées en clair.

## Tests

- `modules/notifications/tests/test_ses_webhook.py` (17 tests) : signature
  réelle RSA (clé + certificat auto-signé, `_load_certificate` mocké) ;
  503 non-configuré ; 400 JSON invalide / type inconnu / champs manquants /
  notification périmée ; 403 topic étranger / mauvaise signature /
  certificat hors hôte SNS ; bounce permanent → FAILED ; rejeu idempotent ;
  bounce transient ; complaint (pas de FAILED) ; jamais de downgrade
  DELIVERED ; bounce sans référence ; événement Delivery ignoré ;
  confirmation d'abonnement (auto + URL étrangère refusée).
- `modules/notifications/tests/test_adapters.py` : +2 tests
  `ConfigurationSetName` (présent / absent).
- Exécution complète : `python manage.py test modules.notifications
  modules.documents` → **67/67 OK** (48 préexistants + 19 nouveaux).
- `manage.py check` OK, `makemigrations --check` : aucune migration à
  générer (aucun modèle ajouté — l'idempotence repose sur les mises à jour
  conditionnelles, pas sur une table de reçus).

## Reste à faire (hors périmètre ou à planifier)

- [ ] Config réelle côté AWS : domaine SES vérifié + records DNS chez le
  registrar, topic SNS + subscription HTTPS vers
  `/backend/api/v1/webhooks/email/ses/`, configuration set, sortie du
  sandbox (voir guide).
- [ ] `infrastructure/production.env.example` : section
  `AWS_SES_REGION`, `AWS_SES_FROM_EMAIL`, `AWS_SES_SNS_TOPIC_ARN`,
  `AWS_SES_CONFIGURATION_SET` (agent infrastructure).
- [ ] Nettoyage des adresses en bounce permanent dans les contacts
  (liste de suppression SES `PutSuppressedDestination` ou invalidation de
  l'email du locataire) — décision produit, hors jalon 3.
- [ ] Test du rendu HTML dans un vrai client (e2e).
- [ ] `AWS_SES_SNS_MAX_AGE_SECONDS` si on veut régler la fenêtre
  anti-rejeu (valeur fixée à 300 s).
