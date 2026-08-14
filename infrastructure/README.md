# Exploitation de production

1. Copier `production.env.example` vers `production.env` hors Git et remplacer toutes les valeurs.
2. Terminer TLS sur un reverse proxy et transmettre `X-Forwarded-Proto: https`.
3. Lancer `docker compose build` puis `docker compose up -d`.
4. Vérifier `docker compose exec api python manage.py check --deploy --settings=config.settings_production`.

## Configuration PayDunya (abonnements)

### Variables d'environnement

Ajouter dans `production.env` :

```bash
# PayDunya (abonnements)
PAYDUNYA_MASTER_KEY=votre_master_key
PAYDUNYA_PRIVATE_KEY=votre_private_key
PAYDUNYA_TOKEN=votre_token
```

### Obtenir les clés

1. Créer un compte sur https://paydunya.com
2. Aller dans **Intégrations** > **Configurer une nouvelle application**
3. Choisir **Mode test** pour les tests
4. Copier les clés (Master Key, Private Key, Token)

### Configuration IPN (Instant Payment Notification)

Dans les paramètres de votre application PayDunya :

| Champ | Valeur (production) |
|-------|---------------------|
| **URL de notification (IPN)** | `https://immolib.com/api/v1/webhooks/paydunya/` |
| **URL de succès** | `https://immolib.com/abonnement?status=success` |
| **URL d'annulation** | `https://immolib.com/abonnement?status=cancelled` |

### Tester en local

PayDunya envoie les webhooks depuis leurs serveurs. Pour recevoir les notifications en local, vous devez exposer votre serveur local :

```bash
# Option 1 : ngrok
ngrok http 8000
# L'URL publique sera : https://abc123.ngrok.io
# IPN : https://abc123.ngrok.io/api/v1/webhooks/paydunya/

# Option 2 : localtunnel
npx localtunnel --port 8000
```

**Important** : En mode test, PayDunya utilise les clés de test. Ne jamais mélanger clés de test et production.

## Migrations et retour arrière

Sauvegarder avant chaque livraison, construire les images, exécuter les migrations puis contrôler les health checks. En cas d'échec, restaurer l'image précédente et la sauvegarde associée ; ne jamais annuler une migration destructive sans procédure testée.

## Sauvegarde et restauration

```bash
docker compose exec -T db pg_dump -Fc -U immolib immolib > immolib.dump
docker compose exec -T db pg_restore --clean --if-exists -U immolib -d immolib < immolib.dump
```

Conserver les sauvegardes chiffrées hors du serveur, tester leur restauration mensuellement et superviser l'espace disque, les erreurs HTTP, la latence, les échecs de notifications et l'âge de la dernière sauvegarde.

Les commandes planifiées de rappels et de notifications doivent être exécutées par un ordonnanceur supervisé. Les clés AWS, Firebase et Mobile Money sont injectées par le gestionnaire de secrets de la plateforme, jamais dans les images ni dans Git.
