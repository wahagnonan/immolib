# Canal SMS Orange (Côte d'Ivoire)

ImmoLib envoie ses SMS via l'API SMS CI d'Orange (OAuth 2.0 v3). Ce document
décrit la configuration du portail développeur, les variables d'environnement
et le webhook de Delivery Receipt.

## 1. Créer les credentials

1. Créez un compte sur <https://developer.orange.com>.
2. Dans **My Apps**, créez une application et choisissez l'API **SMS Côte
   d'Ivoire** (`/smsmessaging/v1`).
3. Une fois l'API approuvée, la section **My Keys** affiche :
   - `client_id` (identifiant) ;
   - `client_secret` (mot de passe) ;
   - votre **sender address** : pour la Côte d'Ivoire, la valeur officielle est
     `tel:+2250000` (voir la table *country_sender_number* de la documentation).

Le `client_secret` ne doit jamais être journalisé ni exposé dans une réponse
API : seul le backend le détient.

## 2. Variables d'environnement

```env
# Active l'adaptateur Orange pour le canal SMS
IMMOLIB_SMS_NOTIFICATION_ADAPTER=modules.sms.adapters.OrangeSmsAdapter

# Credentials du portail Orange Developer (section My Keys)
ORANGE_SMS_CLIENT_ID=replace-with-your-client-id
ORANGE_SMS_CLIENT_SECRET=replace-with-your-client-secret
ORANGE_SMS_BASE_URL=https://api.orange.com

# Adresse d'expéditeur officielle pour la Côte d'Ivoire
ORANGE_SMS_SENDER_ADDRESS=tel:+2250000

# Nom d'expéditeur optionnel (max 11 caractères, whitelisté par Orange).
# Vide = nom par défaut de la plateforme.
ORANGE_SMS_SENDER_NAME=IMMOLIB

# Délai d'attente réseau (secondes)
ORANGE_SMS_TIMEOUT_SECONDS=10

# IP publiques d'où Orange enverra les Delivery Receipts
ORANGE_SMS_DR_ALLOWED_IPS=1.2.3.4,5.6.7.8

# Coût estimé d'un segment, en FCFA
ORANGE_SMS_COST_PER_SEGMENT_XOF=10

# Limite officielle Orange : 5 SMS par seconde
IMMOLIB_SMS_RATE_PER_SECOND=5

# Longueur maximale d'un SMS (1 segment GSM-7)
IMMOLIB_SMS_MAX_CHARS=160
```

## 3. Webhook de Delivery Receipt

Orange ne signe pas ses webhooks. La protection repose sur :

- le HTTPS ;
- la validation stricte de la structure du payload
  (`deliveryInfoNotification.{callbackData, deliveryInfo.{address,
  deliveryStatus}}`) ;
- la liste blanche `ORANGE_SMS_DR_ALLOWED_IPS` : tant qu'elle est vide, le
  webhook répond `503` et n'accepte aucun accusé.

Déclarez l'URL de rappel dans le portail Orange :

```
https://votre-domaine/backend/api/v1/webhooks/sms/orange/delivery-receipts/
```

Transmettez à Orange la liste des IP publiques de vos serveurs et renseignez-les
dans `ORANGE_SMS_DR_ALLOWED_IPS`.

### Corrélation d'un accusé

Chaque envoi porte un `clientCorrelator` : l'identifiant (UUID) de la
notification en file. Orange le renvoie à l'identique dans le `callbackData`
de l'accusé ; ImmoLib le stocke comme `provider_reference` de la
notification. C'est cette clé — un UUID non énumérable, inconnu d'Orange —
qui autorise la mise à jour : un accusé ne peut affecter qu'une notification
dont le corrélateur est connu. Le `resource_id` renvoyé à l'envoi est tracé
dans `SmsSendRecord.provider_message_id` pour le support Orange, mais n'est
pas utilisé pour la corrélation.

### Réponses HTTP

- `200` : accusé accepté (créé ou doublon, traitement idempotent) ;
- `400` : payload qui ne respecte pas le contrat documenté ;
- `403` : IP non listée dans `ORANGE_SMS_DR_ALLOWED_IPS` ;
- `503` : liste blanche vide, webhook non configuré.

Un même accusé reçu deux fois est absorbé (contrainte d'unicité) ; un échec de
livraison (`DeliveryImpossible`) n'écrase jamais un statut `DELIVERED` déjà
enregistré. Statuts Orange reconnus : `DeliveredToTerminal` et
`DeliveredToNetwork` → `DELIVERED`, `DeliveryImpossible` → `FAILED`,
`MessageWaiting` → `PENDING_DR`, tout autre → `UNKNOWN` (tracé).

## 4. Coûts

Chaque SMS est découpé en segments (GSM-7 : 160 caractères, puis 153 ;
UCS-2 : 70, puis 67). Le coût estimé d'un envoi est
`segments × ORANGE_SMS_COST_PER_SEGMENT_XOF`, tracé dans `SmsSendRecord` avec
le destinataire et l'heure d'envoi.

## 5. Limites

Orange plafonne l'envoi à **5 SMS par seconde**. L'adaptateur espace les envois
(`IMMOLIB_SMS_RATE_PER_SECOND`) et le token OAuth (durée de vie officielle
3600 s) est réutilisé puis renouvelé automatiquement sur l'erreur officielle
*Expired credentials* (HTTP 401, code 42).

## Références

- API SMS Côte d'Ivoire : <https://developer.orange.com/apis/sms-ci/>
- Segmentisation SMS : `apps/api/modules/sms/segments.py`
- Tests : `apps/api/modules/sms/tests/`
