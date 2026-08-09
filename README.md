# ImmoLib

ImmoLib est un MVP de gestion locative pour les maisons en Cote d'Ivoire.

Le projet est construit pas a pas. Il contient actuellement :

- le backend Django et ses regles metier ;
- les maisons, locataires, baux et echeances ;
- les paiements répartis entre caution et plusieurs mois, reçus, quittances et
  liens sécurisés ;
- le frontend Next.js des maisons, locataires, baux, echeances, paiements,
  documents, acces public OTP et gestion complete des coproprietaires ;
- un tableau de bord calcule depuis les donnees reelles du compte connecte ;
- une synthese serveur agregee, des filtres par date et une pagination explicite
  pour les historiques volumineux ;
- le cycle de vie de la caution sans portefeuille ImmoLib : remboursement,
  retenue justifiee ou affectation au loyer avec accord explicite ;
- les numeros de telephone normalises au format E.164 et les routes OTP protegees
  par des limites anti-abus ;
- le suivi des envois push, email, WhatsApp et SMS depuis l'ecran Documents ;
- les preferences par compte avec priorite push, puis email Amazon SES ;
- le partage manuel gratuit par WhatsApp, email, partage natif ou copie ;
- l'invitation securisee d'un locataire, son inscription pre-remplie et son
  rattachement automatique apres verification de son email ou telephone ;
- l'espace locataire authentifie avec bail, solde, echeances, paiements,
  confirmation ou contestation, incidents et telechargement des preuves PDF ;
- une landing page publique et la verification d'un recu ou d'une quittance
  par sa reference, sans compte ;
- une interface sobre et responsive, avec une seule couleur de marque et un
  graphique Recharts pour les encaissements ;
- l'identité `IL Trace`, ses icônes navigateur/PWA et une grille tarifaire
  transparente sur la landing page ;
- le suivi partage des incidents de maintenance, de leur signalement a leur
  cloture par le locataire ;
- un webhook Mobile Money generique, signe et idempotent, qui confirme
  automatiquement les paiements authentiques d'un fournisseur ;
- les abonnements Gratuit, Essentiel et Pro avec paiement PayDunya, quota de
  maisons et fonctionnalites activees par plan (mode pilote sans clefs) ;
- les rappels automatiques avant echeance et les relances de retard ;
- les recus et quittances PDF telechargeables par le bailleur ou apres OTP ;
- l'inscription avec verification gratuite de l'email ou repli SMS, la recuperation du mot de passe,
  la connexion et la deconnexion, protegees par les sessions Django et CSRF ;
- un fichier public `/llms.txt` qui décrit le produit et les limites du MVP.

## Organisation

```text
immolib/
├── apps/
│   ├── api/        # API Django et regles metier
│   └── web/        # interface Next.js
├── docs/           # decisions d'architecture expliquees
├── infrastructure/ # deploiement et services techniques
└── compose.yaml
```

## Demarrage du backend

Depuis `apps/api` :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Puis ouvrir `http://127.0.0.1:8000/admin/`.

## Demarrage du frontend

Depuis `apps/web` :

```bash
cp .env.local.example .env.local
npm install
npm run dev
```

Puis ouvrir `http://localhost:3000/`. L'accueil est public et l'espace bailleur
commence sur `/tableau-de-bord`. Les espaces privés utilisent exclusivement
l’authentification, les permissions et les données de l’API Django.

## Premiers endpoints

```text
GET  /health/          Etat du backend
GET  /api/v1/auth/csrf/       Preparation de la protection CSRF
POST /api/v1/auth/register/   Creation d'un compte bailleur
POST /api/v1/auth/phone-verification/request/  Renvoi du code de verification
POST /api/v1/auth/phone-verification/confirm/  Verification et ouverture de session
POST /api/v1/auth/email-verification/request/  Renvoi du code par email
POST /api/v1/auth/email-verification/confirm/  Verification email et ouverture de session
POST /api/v1/auth/password-reset/request/      Demande generique de recuperation
POST /api/v1/auth/password-reset/confirm/      Nouveau mot de passe apres OTP
POST /api/v1/auth/login/      Ouverture d'une session
GET  /api/v1/auth/me/         Profil de la session courante
POST /api/v1/auth/logout/     Fermeture de la session
GET  /api/v1/houses/  Maisons de l'utilisateur connecte
POST /api/v1/houses/  Creation d'une maison
GET  /api/v1/houses/{id}/  Detail d'une maison autorisee
GET  /api/v1/co-owner-invitations/          Invitations envoyees
POST /api/v1/co-owner-invitations/          Invitation d'un coproprietaire
POST /api/v1/co-owner-invitations/{id}/revoke/  Revocation d'une invitation
GET  /api/v1/co-owners/                     Coproprietaires gerables
PATCH /api/v1/co-owners/{id}/               Acces et quote-part
DELETE /api/v1/co-owners/{id}/              Retrait d'un coproprietaire
GET  /api/v1/tenants/      Locataires des maisons autorisees
POST /api/v1/tenants/      Enregistrement d'un locataire
GET  /api/v1/tenant-invitations/      Invitations locataires autorisees
POST /api/v1/tenant-invitations/      Creation ou reutilisation d'une invitation
POST /api/v1/tenant-invitations/{id}/share/  Partage manuel ou email SES
POST /api/v1/tenant-invitations/{id}/revoke/ Revocation d'une invitation
POST /api/v1/public-tenant-invitations/preview/ Consultation publique du lien
POST /api/v1/public-tenant-invitations/claim/   Rattachement d'un compte verifie
GET  /api/v1/tenant-portal/overview/    Synthese du locataire connecte
GET  /api/v1/tenant-portal/leases/      Baux actifs ou termines du locataire
GET  /api/v1/tenant-portal/charges/     Echeances du locataire
GET  /api/v1/tenant-portal/payments/    Historique des paiements
POST /api/v1/tenant-portal/payments/{id}/confirm/  Confirmation locataire
POST /api/v1/tenant-portal/payments/{id}/dispute/  Contestation motivee
GET  /api/v1/tenant-portal/documents/   Recus et quittances du locataire
GET  /api/v1/tenant-portal/documents/{id}/pdf/  Preuve PDF authentifiee
GET/POST /api/v1/tenant-portal/incidents/ Incidents visibles ou signales
POST /api/v1/tenant-portal/incidents/{id}/comment/ Commentaire locataire
POST /api/v1/tenant-portal/incidents/{id}/respond/ Cloture ou reouverture
GET  /api/v1/leases/       Historique des baux autorises
POST /api/v1/leases/       Creation d'un bail brouillon
POST /api/v1/leases/{id}/activate/  Activation d'un bail
POST /api/v1/leases/{id}/close/     Cloture d'un bail actif
GET  /api/v1/rent-charges/           Echeances visibles
POST /api/v1/rent-charges/generate/  Generation manuelle d'un mois
GET  /api/v1/lease-obligations/       Loyers et cautions visibles
POST /api/v1/lease-obligations/prepare-payment/ Preparation d'une caution et/ou d'une plage de mois
GET  /api/v1/payments/               Paiements visibles
POST /api/v1/payments/               Paiement hors ImmoLib avec une ou plusieurs affectations
POST /api/v1/payments/{id}/cancel/   Annulation tracee d'une erreur
GET  /api/v1/security-deposits/       Cautions et soldes encore detenus hors ImmoLib
POST /api/v1/security-deposits/{id}/settle/ Remboursement, retenue ou affectation
GET  /api/v1/dashboard/overview/      Synthese agregee du tableau de bord
GET/POST /api/v1/incidents/          Suivi maintenance du bailleur
POST /api/v1/incidents/{id}/set-status/ Transition de traitement
POST /api/v1/incidents/{id}/comment/ Commentaire du bailleur
GET  /api/v1/documents/              Recus et quittances visibles
POST /api/v1/documents/{id}/share/   Partage multicanal
POST /api/v1/documents/{id}/manual-share/ Partage depuis l'appareil du bailleur
GET  /api/v1/documents/{id}/pdf/     PDF pour un bailleur autorise
GET  /api/v1/notification-deliveries/  Suivi des messages autorises
GET/PATCH /api/v1/notification-preferences/ Preferences du compte
GET/POST/DELETE /api/v1/push-subscriptions/ Appareils Firebase autorises
POST /api/v1/public-access/request-otp/       Demande d'OTP
POST /api/v1/public-access/verify-otp/        Verification d'OTP
POST /api/v1/public-access/view-document/     Consultation sans compte
POST /api/v1/public-access/download-document/ PDF apres verification OTP
POST /api/v1/public-access/payment-response/  Confirmation ou contestation
GET  /api/v1/public-access/verify-reference/?reference=... Controle public
POST /api/v1/webhooks/mobile-money/  Confirmation fournisseur signee
GET  /api/v1/subscription/         Abonnement courant, quota et usage
GET  /api/v1/subscription/plans/   Formules actives
POST /api/v1/subscription/upgrade/ Souscription ou changement de plan
POST /api/v1/subscription/cancel/  Retour au plan Gratuit
GET  /api/v1/subscription/transactions/{id}/refresh/  Confirmation PayDunya
POST /api/v1/webhooks/paydunya/    IPN PayDunya (confirmation du token)
```

Les listes d'echeances, paiements et documents acceptent `page`, `page_size`
(maximum 100) et leurs filtres de date. Sans parametre `page`, le format de
liste historique est conserve pour la compatibilite des anciens clients.

La verification publique d'une reference ne renvoie ni les noms, ni les
telephones, ni l'adresse de la maison. Elle confirme seulement qu'un document
est verifiable dans ImmoLib et expose son statut minimal.

## Cycle de vie de la caution

Une caution encaissee reste une obligation distincte du loyer. ImmoLib
memorise le montant encaisse, le montant deja libere et un journal append-only
des decisions :

- `REFUND` : remboursement realise au locataire hors ImmoLib ;
- `RETENTION` : retenue avec un motif obligatoire ;
- `APPLY_TO_RENT` : affectation a une echeance du meme bail, uniquement avec
  confirmation et reference de l'accord du locataire.

Chaque mouvement produit un releve de caution verifiable. Une affectation au
loyer solde l'echeance sans creer un nouvel encaissement : le paiement genere
porte `is_cash_movement=false`.

## Webhook Mobile Money

Le point d'entree est volontairement independant d'un operateur. L'adaptateur du
fournisseur doit convertir sa charge utile vers ce contrat :

```json
{
  "provider": "NOM_FOURNISSEUR",
  "event_id": "evt_unique",
  "event_type": "payment.succeeded",
  "status": "SUCCEEDED",
  "transaction_id": "transaction_externe",
  "rent_charge_id": "uuid-de-l-echeance",
  "amount": "250000.00",
  "currency": "XOF",
  "paid_at": "2026-07-23T12:00:00Z"
}
```

Le fournisseur envoie `X-ImmoLib-Timestamp` et `X-ImmoLib-Signature`. La
signature vaut `sha256=<HMAC_SHA256(secret, timestamp + "." + corps_brut)>`.
Un evenement `SUCCEEDED` valide le paiement, actualise l'echeance et genere les
documents. Les repetitions du meme `provider + event_id` sont idempotentes.
ImmoLib ne detient jamais les fonds. Avant la production, le format, les
statuts et la verification d'origine doivent etre adaptes au fournisseur choisi.

Les messages push, email, WhatsApp et SMS sont places dans une file
`NotificationDelivery`. Le processeur gere la reclamation, les tentatives, les
reprises et l'appel d'un adaptateur interchangeable. Pour tester sans fournisseur :

```bash
python manage.py process_notifications --simulate --limit 50
```

Le mode simulation ne contacte personne. Sans `--simulate`, aucun message ne
quitte la file tant qu'un adaptateur reel n'est pas configure pour son canal.
L'email reel utilise `AmazonSesEmailAdapter`; le push utilise
`FirebasePushAdapter`. Les identifiants AWS et Firebase restent hors du depot.
L'ecran Documents affiche les etats en attente, en cours, envoye ou en echec,
ainsi que les tentatives et les destinations masquees.

Depuis l'ecran Locataires, le bailleur peut creer un lien d'invitation valable
14 jours. Il peut l'envoyer gratuitement avec WhatsApp, l'application email,
le partage natif ou une copie, ou placer un email dans la file Amazon SES. Le
lien pre-remplit l'inscription mais ne suffit pas a rattacher le compte : le
locataire doit aussi verifier l'email ou le telephone deja enregistre.

Apres le rattachement, `/espace-locataire` utilise des endpoints separes de
l'espace bailleur. Le locataire ne voit que les fiches liees a son compte, jamais
les baux brouillons. Un compte qui est a la fois bailleur et locataire peut
basculer entre les deux espaces depuis le menu du compte.

Le cycle automatique peut etre lance par un planificateur :

```bash
python manage.py run_billing_cycle
```

Avant le 25, la commande assure la presence des echeances du mois courant. A
partir du 25, elle prepare le mois suivant. Elle peut etre relancee sans creer
de doublon. Elle place aussi les rappels de loyer du jour dans la file. Par
defaut, ils sont prevus a J-3, jour J, J+3 et J+7. Le routage `AUTO`
privilegie le push, puis l'email. WhatsApp necessite un opt-in et le SMS reste
desactive tant que l'utilisateur ne le choisit pas.

La creation passe par `modules/properties/services.py`. La vue HTTP ne contient
pas la regle metier : elle valide la requete puis appelle ce service.

## Abonnements

Trois formules : Gratuit (0 FCFA, 1 maison), Essentiel (2 000 FCFA/mois,
5 maisons, coproprietaires et rappels) et Pro (4 000 FCFA/mois, 15 maisons,
exports et statistiques avancees). Le quota compte les maisons dont
l'utilisateur est proprietaire principal. Sans clefs PayDunya, la souscription
active immediatement le plan (mode pilote) en tracant une transaction
`MANUAL/SUCCESSFUL`. Avec PayDunya, la souscription cree une facture et renvoie
l'URL de paiement ; l'activation suit la confirmation authentifiee du token
auprès de PayDunya. Les montants sont toujours calcules par le serveur.

L'expiration replace l'abonnement sur le plan Gratuit sans jamais supprimer
les donnees. Les nouveaux comptes obtiennent le plan Gratuit automatiquement.
Les fonctionnalites payantes sont controlees dans les services metier
(`assert_has_feature`), avec des erreurs 403 structurees
(`FEATURE_NOT_AVAILABLE`, `HOUSE_LIMIT_REACHED` avec `limit` et `required_plan`).

Configuration (fichier .env) :

```text
PAYDUNYA_MASTER_KEY=
PAYDUNYA_PRIVATE_KEY=
PAYDUNYA_PUBLIC_KEY=
PAYDUNYA_TOKEN=
PAYDUNYA_MODE=test|live
SUBSCRIPTION_ESSENTIAL_PRICE=2000
SUBSCRIPTION_ESSENTIAL_MAX_HOUSES=5
SUBSCRIPTION_PRO_PRICE=4000
SUBSCRIPTION_PRO_MAX_HOUSES=15
```

Verification manuelle des expirations :

```bash
python manage.py check_subscription_expirations
```

## Tests

```bash
cd apps/api
python manage.py test

cd ../web
npm run lint
npm run build
```

## Principe d'evolution

L'interface parle uniquement de **maison** dans le MVP. Le modele interne se
nomme `Property` et contient actuellement seulement le type `HOUSE`. Cette
petite abstraction permettra d'ajouter plus tard des appartements ou des
immeubles sans reconstruire les baux et les paiements.
