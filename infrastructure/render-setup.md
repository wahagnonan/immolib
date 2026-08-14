# Test avec des amis sur Render.com (gratuit)

Cette procédure déploie la branche `prod-01` sur Render avec le blueprint
`render.yaml`. C'est un test de pré-production : gratuit, mais avec des
limites (voir en bas).

## 1. Pousser la branche sur GitHub

```bash
git add -A
git commit -m "chore(infra): deploiement de test Render et Web Push VAPID"
git push -u origin prod-01
```

## 2. Créer le compte Render

1. Aller sur https://dashboard.render.com et créer un compte gratuit
   (aucune carte bancaire demandée).
2. Cliquer **« New » → « Blueprint »**.
3. Connecter le dépôt `wahagnonan/immolib`, choisir la branche **`prod-01`**.
4. Render lit `infrastructure/render.yaml` et propose : base de données
   gratuite, Redis Key Value gratuit, 2 services (`immolib-api`,
   `immolib-web`) et 2 jobs cron (`immolib-scheduler`, `immolib-backup`).
5. Cliquer **« Apply »**. Le premier déploiement construit les images
   (compter 5–15 min).

## 3. Renseigner les secrets

Les variables marquées « sync: false » doivent être saisies une fois dans le
tableau de bord lors de la création du blueprint (invite), ou ensuite
(Service → **Environment**) :

| Variable | Valeur |
|---|---|
| `DJANGO_SECRET_KEY` | celle de `infrastructure/production.env` (hors Git) |
| `VAPID_PRIVATE_KEY` | celle de `infrastructure/production.env` (hors Git) |
| `VAPID_SUBJECT` | `mailto:contact@immolib.ci` |
| `ORANGE_SMS_CLIENT_ID` / `CLIENT_SECRET` / `DR_ALLOWED_IPS` | portail Orange (docs/sms/orange.md) |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` / `ACCESS_TOKEN` / `PHONE_NUMBER_ID` | dashboard Meta |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SES_REGION` / `AWS_SES_FROM_EMAIL` | console AWS (SES) |
| `SENTRY_DSN` | projet Sentry (optionnel en test) |
| `BACKUP_S3_BUCKET` / `BACKUP_PASSPHRASE` | bucket S3 + passphrase (optionnel en test) |

Les deux jobs cron sont en plan `starter` (payants, ~7 USD/mois chacun) :
`immolib-scheduler` (toutes les 15 min : facturation, file de notifications,
abonnements) et `immolib-backup` (quotidien : sauvegarde S3). Sans eux,
aucun rappel ni aucune notification ne partirait. Les services web, la base
et le Redis restent gratuits.

Puis **« Manual Deploy » → « Clear build cache & deploy »** sur `immolib-api`
pour appliquer le secret, et à nouveau sur `immolib-web`.

## 4. Créer le compte administrateur

Le shell interactif de Render est payant. Alternative : exécuter la commande
depuis ton PC contre la base Render.

1. Dans le dashboard, ouvrir la base `immolib-db` → **Connect** → copier
   l'**URL externe** (elle commence par `postgres://…`).
2. Depuis `apps/api` (avec ton venv local) :

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings_production"
$env:DJANGO_SECRET_KEY = "valeur-de-production.env"
$env:DATABASE_URL = "postgres://URL-externe-render"
$env:DJANGO_ALLOWED_HOSTS = "localhost"
.\venv\Scripts\python.exe manage.py create_admin `
  --phone +2250707070707 --password "MotDePasseFort" `
  --email toi@exemple.ci --first-name Admin --last-name ImmoLib
```

## 5. Créer les comptes des amis

Chaque ami peut s'inscrire, mais la vérification par email exige Amazon SES
(absent en test) : leurs inscriptions resteront bloquées sur l'OTP. Pour
tester vite, crée les comptes toi-même :

1. Ouvrir `https://immolib-api.onrender.com/admin/` et te connecter.
2. Utilisateurs → Ajouter : téléphone E.164 (`+225…`), email, mot de passe,
   rôle `BAILLEUR`.
3. Chaque ami se connecte ensuite normalement sur `https://immolib-web.onrender.com/login`.

## 6. Vérifier

- `https://immolib-web.onrender.com/health` → `{"status": "ok"}` (relayé vers l'API)
- `https://immolib-api.onrender.com/health/` → OK
- Notifications : Paramètres → Notifications → **Activer sur cet appareil**
  (Web Push VAPID, sans compte Google).

## Limites de ce test

- **Base gratuite** : expirera 30 jours après sa création. À cette date, soit
  la production reprend, soit on bascule vers Neon/Supabase (gratuit).
- **Arrêt automatique** : après 15 min sans visite, la première requête
  prend 30–60 s (le service redémarre).
- **Emails non envoyés** : sans clés AWS SES, aucun email (OTP, quittances
  partagées) ne part. Le push navigateur fonctionne, lui, sans rien.
- **PayDunya** : sans clés, les plans payants sont refusés ; le plan Gratuit
  suffit pour les amis.
- **Crons payants** : les deux jobs cron sont en `starter` ; les supprimer
  pendant le test n'est pas recommande (les rappels et la file s'arrêtent).
- Pour économiser les heures, Render arrête automatiquement les services
  gratuits ; rien à faire de ton côté.
