# Email transactionnel — Amazon SES (SPF, DKIM, DMARC, webhook)

ImmoLib envoie ses emails (quittances, confirmations de paiement, rappels de
loyer, invitations) via **Amazon SES** (adaptateur
`AmazonSesEmailAdapter`, région par défaut `af-south-1`). Ce document couvre
la mise en place complète : vérification du domaine, enregistrements DNS,
sortie du bac à sable, et le webhook de gestion des bounces/complaints.

## 1. Variables d'environnement

```env
# Région AWS du service SES (la seule en Afrique est af-south-1 / Cape Town)
AWS_SES_REGION=af-south-1

# Expéditeur officiel, doit appartenir au domaine vérifié (ex. immolib.ci).
# Vide = l'adaptateur refuse de démarrer (ImproperlyConfigured).
AWS_SES_FROM_EMAIL=no-reply@immolib.ci

# ARN du topic SNS qui reçoit les événements SES. Vide = le webhook
# /api/v1/webhooks/email/ses/ répond 503 et n'accepte rien.
AWS_SES_SNS_TOPIC_ARN=arn:aws:sns:af-south-1:123456789012:immolib-ses-bounces
```

Les identifiants AWS suivent la chaîne standard boto3 (variables d'environnement
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, profil `~/.aws`, ou rôle IAM sur
l'hébergeur). L'IAM doit autoriser au minimum `ses:SendEmail` et
`sns:ConfirmSubscription`.

## 2. Vérifier le domaine dans SES

1. Console AWS → **Amazon SES** → **Identities** → **Create identity** → type
   **Domain** : saisissez `immolib.ci` (ou un sous-domaine dédié
   `mail.immolib.ci` si vous envoyez depuis un domaine distinct du site).
2. Activez **Easy DKIM** (RSA-2048) : SES génère **3 enregistrements CNAME**,
   un par paire de clés (primaire + secondaire).
3. (Recommandé) Activez **Custom MAIL FROM** sur un sous-domaine dédié
   `bounce.immolib.ci` (voir § 3.4) — sinon l'enveloppe `Return-Path` sera
   réécrite sur le domaine Amazon SES, et l'alignement SPF de DMARC échouera.
4. Vérifiez le statut : les enregistrements doivent passer au statut
   **Verified** (quelques minutes à quelques heures après la propagation DNS).

## 3. Enregistrements DNS à créer chez le registrar

### 3.1 SPF (autoriser Amazon SES à envoyer pour votre domaine)

Type **TXT**, nom `immolib.ci` (ou `mail.immolib.ci`) :

```
v=spf1 include:amazonses.com ~all
```

`include:amazonses.com` est identique quelle que soit la région SES. Si le
domaine envoie aussi par un autre canal (ex. serveur SMTP dédié), ajoutez
son include avant `~all`. N'ajoutez pas d'autre `include` qu'Amazon et votre
propre infra : au-delà de 10 consultations DNS, le SPF devient invalide.

### 3.2 DKIM (signature des messages — indispensable pour Gmail/Orange CI)

Type **CNAME**, valeurs affichées dans **SES → Identities → `immolib.ci` →
DomainKeys Identified Mail (DKIM)**. Le format est toujours :

| Nom DNS | Valeur CNAME |
|---|---|
| `<token1>._domainkey.immolib.ci` | `<token1>.dkim.amazonses.com` |
| `<token2>._domainkey.immolib.ci` | `<token2>.dkim.amazonses.com` |
| `<token3>._domainkey.immolib.ci` | `<token3>.dkim.amazonses.com` |

Les jetons `<tokenN>` sont **propres à votre compte SES** (affichés dans la
console) et sont les mêmes dans toutes les régions pour un même compte ; le
suffixe `dkim.amazonses.com` est invariant. Créez les 3 enregistrements :
SES alterne les signatures pour les rotations de clés.

Vérification après propagation :

```text
nslookup -type=TXT _domainkey.immolib.ci
```

### 3.3 DMARC (politique d'échec d'authentification)

Type **TXT**, nom `_dmarc.immolib.ci` :

```
v=DMARC1; p=quarantine; adkim=s; aspf=r; rua=mailto:dmarc@immolib.ci; pct=100
```

- `adkim=s` : alignement DKIM strict — la signature doit porter
  `d=immolib.ci` (cas des messages `From: ...@immolib.ci` signés par Easy
  DKIM) ;
- `aspf=r` : alignement SPF relâché — le domaine d'enveloppe peut être
  `bounce.immolib.ci` si le MAIL FROM personnalisé est actif ;
- `rua` : rapport agrégé de délivrabilité ; prévoyez une boîte qui lit ces
  rapports ;
- Passez à `p=reject` après quelques semaines sans faux positifs.

### 3.4 MAIL FROM personnalisé (optionnel, recommandé)

Pour que SPF et DMARC s'alignent sur `immolib.ci`, configurez le MAIL FROM
SES sur `bounce.immolib.ci` (SES → Identities → `immolib.ci` → **MAIL FROM
domain**) :

| Type | Nom DNS | Valeur |
|---|---|---|
| MX | `bounce.immolib.ci` | `10 feedback-smtp.af-south-1.amazonses.com` |
| TXT | `bounce.immolib.ci` | `v=spf1 include:amazonses.com ~all` |

Sans MAIL FROM personnalisé, l'enveloppe devient `...@amazonses.com` : DKIM
(adkim) suffit alors pour DMARC, mais SPF est désaligné.

### 3.5 Valeurs par région

Les valeurs SES dépendant de la région sont listées dans la console AWS ;
pour la référence (région `af-south-1`) :

| Élément | Valeur |
|---|---|
| API SES (boto3 `region_name`) | `af-south-1` |
| MAIL FROM (MX) | `feedback-smtp.af-south-1.amazonses.com` |
| SMTP relay | `email-smtp.af-south-1.amazonaws.com` (ports 25/465/587) |
| Certificat de signature SNS | `https://sns.af-south-1.amazonaws.com/SimpleNotificationService-<hash>.pem` |
| URL de confirmation SNS | `https://sns.af-south-1.amazonaws.com/?Action=ConfirmSubscription&...` |

## 4. Sortir du bac à sable (sandbox)

Par défaut, un compte SES ne peut envoyer que vers des adresses vérifiées et
est plafonné à 1 email/s. Ouvrez une demande **SES Sending Limits increase**
(case "I only send to customers I have obtained" : notification
transactionnelle — quittances/rappels — et non du marketing) : demandez la
sortie de sandbox, une cible de 5-20 emails/s et un quota quotidien
cohérent avec le volume de la bêta.

## 5. Webhook bounce/complaint (SNS)

### 5.1 Créer le topic et la configuration

1. **SNS** → **Topics** → **Create topic** : type **Standard**, nom
   `immolib-ses-bounces` (exemple). Notez l'ARN : il va dans
   `AWS_SES_SNS_TOPIC_ARN`.
2. **Create subscription** : protocole **HTTPS**, endpoint :
   ```
   https://votre-domaine/backend/api/v1/webhooks/email/ses/
   ```
   ImmoLib confirme automatiquement l'abonnement (endpoint de confirmation
   AWS signé, hôte `sns.<region>.amazonaws.com` vérifié). Si la confirmation
   échoue, confirmez manuellement depuis la console SNS.
3. **SES** → **Configuration sets** → créez (ex. `immolib-production`) et
   associez un **Event destination** → **SNS destination** vers le topic,
   en cochant :
   - **Bounces** (Permanent + Transient) ;
   - **Complaints** ;
   - (facultatif) **Delivery** — ImmoLib l'accepte mais ne le corrèle pas.
4. Attachez la configuration à l'identité : SES → Identities →
   `immolib.ci` → Configuration set. Sans configuration set, AUCUN événement
   n'est publié.
5. Chaque `send_email` doit référencer la configuration :
   l'adaptateur SES passe l'`X-SES-CONFIGURATION-SET` dans les en-têtes
   (variable `AWS_SES_CONFIGURATION_SET`, vide = pas d'événements).

### 5.2 Sécurité du webhook

Contrairement au webhook Orange (liste d'IP), SNS **signe chaque message**
(RSA) :

- **Signature** : vérifiée avec le certificat AWS (`SigningCertURL`), hôte
  restreint à `sns.<region>.amazonaws.com` (anti-SSRF) ;
- **Topic** : le `TopicArn` doit être identique à `AWS_SES_SNS_TOPIC_ARN`
  (sinon 403) ;
- **Horodatage** : un message de plus de 5 minutes est rejeté (anti-rejeu) ;
- **Fermé par défaut** : `AWS_SES_SNS_TOPIC_ARN` vide → réponse 503.

### 5.3 Traitement des événements

La corrélation se fait via `mail.messageId` (le MessageId SES retourné par
l'adaptateur) ↔ `NotificationDelivery.provider_reference` :

| Événement | Action |
|---|---|
| Bounce **Permanent** (`bounceType=Permanent`) | `NotificationDelivery` → **FAILED** (avec `delivery_status=FAILED`, `failure_reason` « SES bounce permanent (...) »), sauf si déjà DELIVERED/FAILED |
| Bounce **Transient** / **Undetermined** | Journalisation seulement (masquée) — SES et la file peuvent retenter |
| **Complaint** | Journalisation seulement (masquée) — l'adresse peut rester valide |
| **Delivery** | Accepté, ignoré (SMS-only pour l'instant) |

Le traitement est **idempotent** (SNS délivre au moins une fois) : les mises
à jour sont conditionnelles, un rejeu ne modifie rien. Les destinations ne
sont **jamais journalisées en clair** (`ya***@example.com`).

### 5.4 Limites connues

- Un bounce permanent marque la delivery FAILED mais ne **supprime pas
  l'adresse des contacts** (bailleur/locataire) : prévoir un nettoyage
  ultérieur (liste de suppression SES via `ses:PutSuppressedDestination` ou
  invalidation de l'email du locataire) — voir le suivi d'audit.
- L'abonnement SNS doit être confirmé une première fois ; si l'URL publique
  change, recréez la subscription.
- En environnement de développement (`IMMOLIB_EMAIL_NOTIFICATION_ADAPTER`
  non défini), l'adaptateur simulé ne publie aucun événement : inutile de
  configurer SNS localement.

## 6. Vérifications rapides

```text
# DNS
nslookup -type=TXT immolib.ci                    # SPF inclut amazonses.com
nslookup -type=CNAME _domainkey.immolib.ci       # DKIM pointe vers dkim.amazonses.com
nslookup -type=TXT _dmarc.immolib.ci             # DMARC p=quarantine ou p=reject

# Délivrabilité (après un envoi réel)
# - Gmail : afficher les en-têtes -> Authentication-Results avec dkim=pass,
#   spf=pass et une ligne DMARC pass
# - SES : Events/Console -> configuration set -> onglet Bounces/Complaints

# Webhook
curl -X POST https://votre-domaine/backend/api/v1/webhooks/email/ses/ \
     -H 'Content-Type: application/json' -d '{}'   # 503 (ARN non configuré) ou 400
```
