# Comprendre le jalon 20 : inviter un locataire

Ce jalon transforme un locataire enregistré par le bailleur en utilisateur
ImmoLib, sans dupliquer sa fiche et sans confondre lien reçu et identité prouvée.

## Le parcours visible

1. Le bailleur ouvre **Locataires** et clique sur **Inviter sur ImmoLib**.
2. Django crée une invitation valable 14 jours, ou réutilise celle déjà active.
3. Le bailleur choisit WhatsApp, email local, SMS local, partage natif, copie ou
   email automatique Amazon SES.
4. Le locataire ouvre `/invitation-locataire/[token]`.
5. Son nom, son téléphone, son email et la maison sont relus depuis Django.
6. Il crée un compte ou utilise un compte existant.
7. L’OTP prouve le contact enregistré.
8. Django lie le compte à la fiche `Tenant` et marque l’invitation `ACCEPTED`.

## États de l’invitation

| État | Signification |
| --- | --- |
| `PENDING` | Le lien est actif et peut être partagé ou réclamé |
| `ACCEPTED` | Le compte vérifié est lié au locataire |
| `REVOKED` | Un bailleur autorisé a annulé le lien |
| `EXPIRED` | La date limite est dépassée |

Le statut visible du locataire évolue en parallèle : `UNREGISTERED`, puis
`INVITED`, puis `ACTIVE` après le rattachement.

## Quelle preuve est demandée ?

| Dossier du bailleur | Inscription autorisée | Preuve finale |
| --- | --- | --- |
| Téléphone + email | Mêmes téléphone et email | OTP email |
| Téléphone sans email | Même téléphone, email vide | OTP SMS |
| Compte existant | Téléphone ou email concordant | Contact concordant déjà vérifié |
| Coordonnées différentes | Refusée | Aucune liaison |

L’email vérifié ne marque jamais le téléphone comme vérifié. Les deux preuves
restent indépendantes.

## Partage manuel ou envoi automatique

| Choix | Comportement |
| --- | --- |
| WhatsApp | Ouvre `wa.me` avec le texte pré-rempli |
| Email local | Ouvre l’application email du bailleur |
| SMS local | Ouvre l’application SMS, sans fournisseur ImmoLib |
| Partage natif | Ouvre la feuille de partage du téléphone |
| Copier | Copie le lien sécurisé |
| Email Amazon SES | Ajoute un envoi réel à `NotificationDelivery` |

Un événement manuel signifie « le bailleur a préparé le partage », pas « le
locataire a reçu le message ». Pour SES, l’état de la file indique `PENDING`,
`PROCESSING`, `SENT` ou `FAILED`.

## Endpoints

| Méthode | URL | Rôle |
| --- | --- | --- |
| `GET` | `/api/v1/tenant-invitations/` | Lister les invitations gérables |
| `POST` | `/api/v1/tenant-invitations/` | Créer ou réutiliser une invitation |
| `POST` | `/api/v1/tenant-invitations/{id}/share/` | Préparer ou envoyer le partage |
| `POST` | `/api/v1/tenant-invitations/{id}/revoke/` | Révoquer |
| `POST` | `/api/v1/public-tenant-invitations/preview/` | Lire un jeton public |
| `POST` | `/api/v1/public-tenant-invitations/claim/` | Lier un compte vérifié |

`POST /api/v1/auth/register/` accepte aussi
`tenant_invitation_token`. Ce champ réserve l’invitation pendant que
l’utilisateur vérifie son contact.

## Où lire le code

1. `modules/leases/models.py` : invitation et traces de partage.
2. `modules/leases/services.py` : signature, sécurité, partage et rattachement.
3. `modules/leases/api/` : contrats HTTP privés et publics.
4. `modules/accounts/services.py` : inscription et acceptation après OTP.
5. `modules/documents/notifications.py` : contenu de l’email SES.
6. `src/components/tenants/tenant-invitation-modal.tsx` : partage bailleur.
7. `src/components/tenants/tenant-invitation-onboarding.tsx` : parcours locataire.
8. `modules/leases/tests/test_invitations.py` : règles exécutables du jalon.

## Limite volontaire

Le jalon 20 donne au locataire un compte rattaché. Le portail complet où il
consultera ses baux, échéances, quittances et paiements appartient au jalon 21.
Le webhook Mobile Money signé reste exclu, conformément au périmètre du MVP.
