# Exploitation de production ImmoLib

Deux chemins de deploiement sont documentes : **auto-heberge** (docker
compose + nginx, production finale) et **Render** (blueprint `render.yaml`,
beta avec les amis puis lancement). Les commandes planifiees, la sauvegarde
et le monitoring sont les memes dans les deux cas.

## 1. Deploiement auto-heberge (docker compose)

1. Copier `production.env.example` vers `production.env` hors Git et
   remplacer toutes les valeurs (les secrets sont deja generes dans le
   `production.env` local, hors Git).
2. Installer nginx avec `nginx-app-immolib.conf` (adapte au domaine reel)
   puis `certbot --nginx -d <domaine>`.
3. Lancer `docker compose build` puis `docker compose up -d` (Postgres,
   Redis, API, web).
4. Verifier `docker compose exec api python manage.py check --deploy --settings=config.settings_production`.
5. Installer les crons : `sudo cp infrastructure/crontab-prod /etc/cron.d/immolib`
   puis copier `run-scheduled.sh`, `process-notifications.sh` et `backup.sh`
   dans `/opt/immolib/infrastructure/` (executables), et creer
   `/opt/immolib/backup-passphrase` (chmod 600) si la passphrase n'est pas
   dans `production.env`.

Avant la mise en ligne reelle, remplacer `app.immolib.ci` par le domaine
final dans `production.env`, `nginx-app-immolib.conf` et `crontab-prod`.

## 2. Deploiement Render (blueprint)

`infrastructure/render.yaml` decrit : base Postgres free, API Docker
(migrations au demarrage, health `/health/`), frontend Next.js, un Redis
Key Value free (cache partage), et **deux jobs cron** :

| Service | Plan | Frequence | Commande |
|---|---|---|---|
| `immolib-scheduler` | starter | toutes les 15 min | `run_billing_cycle` + `process_notifications` + `check_subscription_expirations` |
| `immolib-backup` | starter | quotidien 02:45 UTC | `backup_database` (S3) |

Les jobs cron sont les seuls elements payants (~7 USD/mois chacun, limite
d'execution 5 min : la file est drainee par lots de 50). Avant le lancement
public, basculer `branch: prod-01` sur `main` et renseigner les secrets
`sync: false` (invites a la creation du blueprint, puis dans Service >
Environment). Procedure pas a pas : `render-setup.md`.

## 3. Commandes planifiees (identiques partout)

| Frequence | Commande | Effet |
|---|---|---|
| journaliere (08:30) | `run_billing_cycle` | genere les echeances du mois, actualise les statuts, place les rappels de loyer en file |
| toutes les heures | `process_notifications` | draine la file (SMS/email/WhatsApp/push), max 50 messages par passe |
| journaliere (08:30) | `check_subscription_expirations` | expire les abonnements arrives a terme |
| quotidienne (02:45) | `backup.sh` (hote) ou `backup_database` (Render) | sauvegarde chiffree |

Auto-heberge : `crontab-prod` (fichier cron.d) lance `run-scheduled.sh`
(journalier, verrouille) et `process-notifications.sh` (horaire, verrouille).
Render : les deux jobs cron du blueprint. Toutes ces commandes sont
idempotentes : un chevauchement est inoffensif (la file est reclamee de
facon atomique par statut).

## 4. Sauvegarde et restauration

### Auto-heberge

`backup.sh` realise un `pg_dump -Fc` chiffre AES-256-CBC (openssl), avec
rotation 14 jours et option hors site `BACKUP_OFFSITE_CMD` (ex. rclone).

```bash
# Sauvegarde manuelle
sudo /opt/immolib/backup.sh

# Restauration (arreter l'API d'abord)
docker compose stop api
infrastructure/restore.sh /opt/immolib/backups/immolib_2026-08-10_020000.dump.enc
docker compose start api
```

### Render

Le job cron `immolib-backup` execute `python manage.py backup_database` :
`pg_dump` si le binaire est dans l'image, sinon export `dumpdata` compresse ;
destination S3 (`BACKUP_S3_BUCKET`, cle `backups/<date>.dump`, SSE-S3) et/ou
disque local avec rotation (`BACKUP_RETENTION_DAYS`, defaut 14). Une
passphrase `BACKUP_PASSPHRASE` ajoute un chiffrement AES-256-CBC
(parite avec `backup.sh`). Une restauration manuelle se fait depuis le
poste de l'operateur, comme l'admin : `psql`/`pg_restore` sur l'URL externe
de la base Render, ou `python manage.py loaddata` pour un export `dumpdata`.

### Regles

- Conserver les sauvegardes chiffrees hors du serveur (S3 = hors site).
- **Tester la restauration mensuellement** (restore.sh sur un environnement
  jetable), superviser l'age de la derniere sauvegarde et l'espace disque.
- Ajouter une regle de cycle de vie S3 (ex. retention 30 jours) sur le
  bucket de sauvegarde.

## 5. Migrations et retour arriere

Sauvegarder avant chaque livraison, construire les images, executer les
migrations puis controler les health checks. En cas d'echec, restaurer
l'image precedente et la sauvegarde associee ; ne jamais annuler une
migration destructive sans procedure testee.

## 6. Monitoring et alertes

### Sante

- `/health/` (liveness, Render) : toujours 200 si le process repond.
- `/api/v1/health/` (readiness, sans auth) : 200 sinon **503** quand :
  - la base ne repond pas ;
  - la file de notifications est bloquee : des `NotificationDelivery`
    QUEUED eligibles sans adaptateur configure pour leur canal depuis plus
    de `IMMOLIB_HEALTH_QUEUE_STALL_MINUTES` (defaut 15) minutes — elles ne
    seront jamais envoyees (adaptateur mal configure ou worker arrete).

Sonder `/api/v1/health/` toutes les 1-5 min depuis un moniteur externe
(UptimeRobot, Better Uptime, cron local) : toute reponse 503 alerte
(Slack/email). Ne pas brancher Render `healthCheckPath` sur ce endpoint :
un 503 ne doit pas redemarrer le service, c'est une alerte operateur.

### Sentry

Active des que `SENTRY_DSN` est renseigne (`settings.py`, import sous
condition) : exceptions backend, commandes cron en erreur, traces
(`SENTRY_TRACES_SAMPLE_RATE`). Variables : `SENTRY_ENV`, `SENTRY_RELEASE`.
Creer des alertes Sentry (ex. taux d'erreur > 0 sur `production`) vers
email/Slack.

### Controles manuels

- File : `docker compose exec api python manage.py process_notifications` —
  verifier les compteurs `reclamees/envoyees/echecs`.
- Admin Django : onglet Notification deliveries (statuts, tentatives,
  raisons d'echec) et Sms delivery receipts (accuses Orange).

## Fichiers d'exploitation

| Fichier | Role |
|---|---|
| `production.env` / `production.env.example` | Secrets et configuration, hors Git / modele |
| `nginx-app-immolib.conf` | Reverse proxy TLS (certbot) vers `web:3000` |
| `crontab-prod` | Ordonnancement auto-heberge (billing, file, backup) |
| `run-scheduled.sh` | Lancement verrouille (billing, file, abonnements) |
| `process-notifications.sh` | Lancement verrouille horaire de la file |
| `backup.sh` | Sauvegarde chiffree PostgreSQL avec rotation et option hors site |
| `restore.sh` | Restauration d'une sauvegarde chiffree |
| `render.yaml` | Blueprint Render (API, web, Redis, 2 jobs cron) |
| `render-setup.md` | Procedure pas a pas du deploiement Render |

Les cles AWS, VAPID, Orange, PayDunya et Mobile Money sont injectees par le
gestionnaire de secrets de la plateforme, jamais dans les images ni dans Git.