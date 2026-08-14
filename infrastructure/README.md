# Exploitation de production

1. Copier `production.env.example` vers `production.env` hors Git et remplacer toutes les valeurs (les secrets sont déjà générés dans le `production.env` local, hors Git).
2. Installer nginx avec `nginx-app-immolib.conf` (adapté au domaine réel) puis `certbot --nginx -d <domaine>`.
3. Lancer `docker compose build` puis `docker compose up -d`.
4. Vérifier `docker compose exec api python manage.py check --deploy --settings=config.settings_production`.

## Fichiers d'exploitation

| Fichier | Rôle |
|---|---|
| `production.env` | Secrets et configuration, hors Git |
| `nginx-app-immolib.conf` | Reverse proxy TLS (certbot) vers `web:3000` |
| `crontab-prod` | Ordonnancement des commandes planifiées |
| `run-scheduled.sh` | Lancement verrouillé (`run_billing_cycle`, `process_notifications`, `check_subscription_expirations`) |
| `backup.sh` | Sauvegarde chiffrée PostgreSQL avec rotation et option hors site |
| `restore.sh` | Restauration d'une sauvegarde chiffrée |
| `render.yaml` | Blueprint Render pour le test gratuit avec les amis |
| `render-setup.md` | Procédure complète du test Render, pas à pas |

Avant la mise en ligne réelle, remplacer `app.immolib.ci` par le domaine final
dans `production.env`, `nginx-app-immolib.conf` et `crontab-prod`.

## Migrations et retour arrière

Sauvegarder avant chaque livraison, construire les images, exécuter les migrations puis contrôler les health checks. En cas d’échec, restaurer l’image précédente et la sauvegarde associée ; ne jamais annuler une migration destructive sans procédure testée.

## Sauvegarde et restauration

```bash
docker compose exec -T db pg_dump -Fc -U immolib immolib > immolib.dump
docker compose exec -T db pg_restore --clean --if-exists -U immolib -d immolib < immolib.dump
```

Conserver les sauvegardes chiffrées hors du serveur, tester leur restauration mensuellement et superviser l’espace disque, les erreurs HTTP, la latence, les échecs de notifications et l’âge de la dernière sauvegarde.

Les commandes planifiées de rappels et de notifications doivent être exécutées par un ordonnanceur supervisé. Les clés AWS, VAPID, Firebase et Mobile Money sont injectées par le gestionnaire de secrets de la plateforme, jamais dans les images ni dans Git.
