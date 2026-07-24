# Comprendre le jalon 22 : incidents, confiance publique et Mobile Money

Ce jalon ajoute trois flux qui se rejoignent autour de la traçabilité. Le code
est séparé par domaine afin que chacun puisse évoluer sans gonfler les vues HTTP.

## 1. Pourquoi un incident n'est pas un simple message

Un message seul ne permet pas de savoir si le problème a été pris en compte,
réparé ou confirmé par le locataire. Le modèle sépare donc :

- `MaintenanceIncident` : la situation courante ;
- `MaintenanceEvent` : chaque action passée.

La vue valide les données et choisit le bon objet. Le service applique les
transitions autorisées. Le sélecteur décide quels objets l'utilisateur peut
voir. Cette séparation évite de dupliquer les règles entre l'API bailleur et
l'API locataire.

### Parcours complet

1. le locataire ou le bailleur signale un incident sur un bail actif ;
2. le bailleur le prend en compte ;
3. l'intervention démarre ;
4. le bailleur annonce la résolution ;
5. le locataire clôture, ou rouvre avec un motif ;
6. chaque transition et chaque commentaire reste horodaté.

Les routes bailleur sont :

| Méthode | URL | Usage |
| --- | --- | --- |
| `GET/POST` | `/api/v1/incidents/` | Lister ou signaler |
| `POST` | `/api/v1/incidents/{id}/set-status/` | Changer l'état |
| `POST` | `/api/v1/incidents/{id}/comment/` | Ajouter un commentaire |

Les routes locataire sont volontairement séparées :

| Méthode | URL | Usage |
| --- | --- | --- |
| `GET/POST` | `/api/v1/tenant-portal/incidents/` | Lister ou signaler |
| `POST` | `/api/v1/tenant-portal/incidents/{id}/comment/` | Commenter |
| `POST` | `/api/v1/tenant-portal/incidents/{id}/respond/` | Clôturer ou rouvrir |

## 2. Vérification publique et accès OTP ne sont pas la même chose

La page `/verifier-quittance` répond à une question courte : « cette référence
existe-t-elle dans ImmoLib et le document est-il actif ? »

Elle n'ouvre pas le PDF et ne donne pas accès aux coordonnées. Pour consulter
le document complet reçu par email, WhatsApp ou SMS, le destinataire conserve
le parcours par lien sécurisé et OTP.

Cette distinction permet une vérification simple depuis la landing page sans
affaiblir la protection du document complet.

## 3. Pourquoi le webhook utilise le corps HTTP brut

Une signature HMAC doit couvrir exactement les octets envoyés. Si le JSON est
analysé puis reconstruit avant la vérification, l'ordre des champs ou les
espaces peuvent changer et invalider une signature légitime.

ImmoLib calcule donc :

```text
HMAC_SHA256(secret, timestamp + "." + raw_body)
```

Le fournisseur transmet :

```text
X-ImmoLib-Timestamp: 1784808000
X-ImmoLib-Signature: sha256=<signature_hexadécimale>
```

Le timestamp limite la réutilisation tardive d'une requête capturée. La clé
`provider + event_id` garantit l'idempotence : un fournisseur peut répéter sa
notification après un timeout sans créer deux paiements.

## 4. Ce qui se passe après un succès authentique

Dans une transaction atomique, le service :

1. verrouille l'échéance ;
2. vérifie qu'elle existe, n'est pas annulée et utilise la même devise ;
3. empêche un montant négatif ou supérieur au solde ;
4. crée un paiement `MOBILE_MONEY / CONFIRMED_BY_PROVIDER` ;
5. affecte le montant et recalcule l'échéance ;
6. génère le reçu, puis la quittance si le solde devient nul ;
7. rattache le paiement à l'événement fournisseur.

Le locataire n'a rien à confirmer. Le bailleur ne peut pas annuler ce paiement
manuellement. Ces règles différencient clairement une preuve fournisseur d'une
déclaration en espèces.

## 5. Où lire le code

1. `modules/maintenance/models.py` : incident et journal.
2. `modules/maintenance/services.py` : transitions métier.
3. `modules/maintenance/api/views.py` : APIs bailleur et locataire.
4. `modules/payments/webhooks.py` : signature et tolérance temporelle.
5. `modules/payments/api/webhook_views.py` : contrat d'entrée générique.
6. `modules/payments/services.py` : idempotence et création atomique.
7. `modules/documents/api/views.py` : vérification publique.
8. `src/components/maintenance/maintenance-workspace.tsx` : écran bailleur.
9. `src/components/tenant-portal/tenant-incident-panel.tsx` : écran locataire.
10. `src/components/public/document-verification.tsx` : contrôle public.

## 6. Avant de choisir un fournisseur réel

Le contrat du jalon est un socle et non une promesse de compatibilité directe.
Pour brancher un opérateur ou agrégateur, créer un adaptateur qui :

- vérifie sa méthode de signature officielle ;
- traduit son payload vers le contrat interne ;
- mappe explicitement ses états vers `SUCCEEDED`, `FAILED`, `PENDING` ou
  `CANCELLED` ;
- associe de façon sûre la transaction à l'UUID de l'échéance ;
- traite séparément remboursements et annulations fournisseur.

Ne placez jamais une clé réelle dans `.env.example`, les tests ou le dépôt.
