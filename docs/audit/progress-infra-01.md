# Progression infra-01 — jalons 14 (Backup), 15 (Déploiement prod), 16 (Monitoring/beta)

Branche : `infra-01` (worktree `immolib-worktrees\infra-01`). Dernière mise à jour : 2026-08-14.

## Fait

### Jalon 15 — Worker/ordonnanceur
- `infrastructure/render.yaml` : + 2 jobs cron Render (spec blueprint vérifiée sur render.com/docs/blueprint-spec) :
  - `immolib-scheduler` (plan `starter`, toutes les 15 min) : `run_billing_cycle` + `process_notifications` + `check_subscription_expirations` ;
  - `immolib-backup` (plan `starter`, quotidien 02:45 UTC) : `python manage.py backup_database`.
- Commentaire audité corrigé en tête de `render.yaml` : avant « pas de worker planifié » → désormais 2 crons ; la branche reste `prod-01` pour le test, bascule sur `main` documentée comme action AVANT lancement.
- Redis Key Value free ajouté au blueprint (`immolib-redis`, `fromService connectionString` → `REDIS_URL`).
- `envVarGroups` introduit pour mutualiser les variables non secrètes ; secrets en `sync: false` par service.
- `infrastructure/crontab-prod` (auto-hébergé) : + ligne backup `45 2 * * *` et + ligne horaire de la file (`process-notifications.sh`, nouveau script verrouillé).

### Jalon 14 — Backup
- Nouvelle commande Django `backup_database` (`modules/admin_panel/management/commands/backup_database.py`) : pg_dump (format custom) si binaire présent, sinon dumpdata gzip ; chiffrement openssl optionnel (`BACKUP_PASSPHRASE[_FILE]`) ; upload S3 (`BACKUP_S3_BUCKET`, SSE-S3) et/ou disque local avec rotation `BACKUP_RETENTION_DAYS`. Utilisée par le cron Render ; `backup.sh` reste pour l'auto-hébergé.
- Restauration testée documentée dans `infrastructure/README.md` (restore.sh + procédure Render/S3).
- `production.env.example` complété : VAPID_PRIVATE_KEY/VAPID_SUBJECT, AWS SES (access/secret/région/from), ORANGE_SMS_* complets, WhatsApp, PayDunya, Mobile Money, DATABASE_URL vs POSTGRES_*, REDIS_URL, SENTRY_DSN/ENV/RELEASE, BACKUP_*, DJANGO_DEBUG, DJANGO_COOKIE_SECURE, etc.

### Jalon 16 — Monitoring
- `sentry-sdk[django]` dans `apps/api/requirements.txt` ; bloc Sentry dans `config/settings.py` (activé si `SENTRY_DSN`, import sous condition, `environment`/`traces_sample_rate`/`release` configurables). Rien n'est écrasé.
- Endpoint `/api/v1/health/` (`config/health.py`, sans auth, pour sondes externes) : 200 si OK, 503 si base injoignable ou file de notifications bloquée (NotificationDelivery QUEUED éligible sans adaptateur pour son canal depuis > `IMMOLIB_HEALTH_QUEUE_STALL_MINUTES`, défaut 15). `/health/` existant conservé pour la liveness Render.
- Alertes documentées : sonder `/api/v1/health/` (UptimeRobot/cron), alertes Sentry, contrôles admin (deliveries, DR Orange).

### Jalon 15 (suite) — Redis partagé
- `compose.yaml` : service `redis` (redis:7-alpine, AOF, healthcheck) + `REDIS_URL` injectée à l'API + volume `redis_data`.
- `config/settings.py` : `CACHES` = django-redis si `REDIS_URL` (IGNORE_EXCEPTIONS=True, KEY_PREFIX immolib), fallback locmem sinon. Logique métier des throttles/lockout inchangée (`modules/accounts/services.py` non touché).
- `django-redis` ajouté aux requirements.

### Doc
- `infrastructure/README.md` réécrit : déploiement auto-hébergé + Render, tableau des commandes planifiées, backup/restore, monitoring/alertes, fichiers d'exploitation.
- `infrastructure/render-setup.md` : secrets `sync: false` (tableau élargi), jobs cron, budget.

## Vérifications
- Tests cibles nouveaux : 7/7 OK (config.tests + modules.admin_panel.tests.test_backup).
- Suite complète backend : **318 tests, 0 échec** (SQLite dev, ~23 min).
- `manage.py check` OK ; `check --deploy` avec `settings_production` + `DATABASE_URL` + `REDIS_URL` + `SENTRY_DSN` : 0 problème.
- `makemigrations --check --dry-run` : aucun changement.
- YAML `render.yaml` + `compose.yaml` : parsing OK (pas de validation Render CLI, pas d'API Render dispo).
- Packages installés dans le venv partagé : sentry-sdk 2.68, django-redis 5.4 (redis 8.1).

## Reste à faire (hors code, par le chef de projet / opérateur)
1. Renseigner les vraies variables sur Render (secrets `sync: false`) : DJANGO_SECRET_KEY, VAPID_PRIVATE_KEY/VAPID_SUBJECT, ORANGE_SMS_* (+ IP webhooks DR à demander à Orange), WHATSAPP_*, AWS SES, SENTRY_DSN, BACKUP_S3_BUCKET/PASSPHRASE, PAYDUNYA_*, MOBILE_MONEY_WEBHOOK_SECRET.
2. Basculer `render.yaml` sur la branche `main` avant le lancement (case 15 de la checklist) + relancer le sync du blueprint.
3. Créer le bucket S3 + règle de cycle de vie (ex. 30 jours) ; tester une restauration réelle depuis S3.
4. Configurer le moniteur externe sur `/api/v1/health/` + alertes Sentry (projet + règles).
5. Test de charge/limite des crons starter (5 min d'exécution max sur ce plan) : passer en `standard` si `run_billing_cycle` dépasse.
6. Auto-hébergé : copier `process-notifications.sh` vers `/opt/immolib/infrastructure/` (mis à jour dans la doc README).

## Risques
- Le plan free de la base Render expire après 30 jours ; la base gratuite n'a pas de sauvegardes automatisées Render — la commande `backup_database` (S3) couvre ce trou.
- Cron starter : limite d'exécution 5 min — file drainée par lots de 50, mais un gros `run_billing_cycle` pourrait s'approcher de la limite.
- `sentry-sdk` importé sous condition : si `SENTRY_DSN` est mal saisi, Sentry est silencieusement désactivé (pas d'échec applicatif).
- `IGNORE_EXCEPTIONS=True` sur le cache Redis : une panne Redis rend le verrouillage login best-effort (choix assumé : pas de blocage des requêtes).
- Le health 503 sur file bloquée repose sur `NOTIFICATION_ADAPTERS` : si un adaptateur est configuré mais que son fournisseur est en panne, la file n'est pas détectée comme bloquée (les messages passent en retry/échec — visibles dans l'admin).
