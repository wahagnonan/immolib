# Exploitation de production

1. Copier `production.env.example` vers `production.env` hors Git et remplacer toutes les valeurs.
2. Terminer TLS sur un reverse proxy et transmettre `X-Forwarded-Proto: https`.
3. Lancer `docker compose build` puis `docker compose up -d`.
4. Vérifier `docker compose exec api python manage.py check --deploy --settings=config.settings_production`.

## Migrations et retour arrière

Sauvegarder avant chaque livraison, construire les images, exécuter les migrations puis contrôler les health checks. En cas d’échec, restaurer l’image précédente et la sauvegarde associée ; ne jamais annuler une migration destructive sans procédure testée.

## Sauvegarde et restauration

```bash
docker compose exec -T db pg_dump -Fc -U immolib immolib > immolib.dump
docker compose exec -T db pg_restore --clean --if-exists -U immolib -d immolib < immolib.dump
```

Conserver les sauvegardes chiffrées hors du serveur, tester leur restauration mensuellement et superviser l’espace disque, les erreurs HTTP, la latence, les échecs de notifications et l’âge de la dernière sauvegarde.

Les commandes planifiées de rappels et de notifications doivent être exécutées par un ordonnanceur supervisé. Les clés AWS, Firebase et Mobile Money sont injectées par le gestionnaire de secrets de la plateforme, jamais dans les images ni dans Git.
