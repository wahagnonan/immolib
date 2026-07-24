# Architecture du frontend Next.js

Ce document explique le frontend ImmoLib sans supposer une connaissance avancée
de Next.js.

## Le principe

Le frontend est découpé en quatre couches simples :

```text
Page Next.js -> Composant d'interface -> Client API -> Proxy Next.js -> API Django
```

- `src/app` contient une page par URL. Next.js crée les routes à partir des dossiers.
- `src/components` contient les morceaux visuels réutilisables.
- `src/lib/api-client.ts` est le seul endroit qui connaît les endpoints Django.
- `src/types/domain.ts` décrit en TypeScript les données renvoyées par Django.

Les règles importantes restent dans Django. Le frontend collecte les informations,
affiche les résultats et explique les erreurs du backend.

## Correspondance écrans et API

| Écran | Route Next.js | Endpoints Django utilisés |
| --- | --- | --- |
| Tableau de bord | `/tableau-de-bord` | `GET /dashboard/overview/` |
| Maisons | `/maisons` | `GET/POST /houses/` |
| Locataires | `/locataires` | `GET/POST /tenants/`, `GET/POST /tenant-invitations/`, `share`, `revoke` |
| Baux | `/baux` | `GET/POST /leases/`, `activate`, `close` |
| Échéances | `/echeances` | `GET /rent-charges/`, `generate` |
| Paiements | `/paiements` | `GET/POST /payments/`, `cancel`, `GET /security-deposits/`, `settle` |
| Documents | `/documents` | `GET /documents/` paginé, `share`, téléchargement PDF, suivi des envois |
| Accès locataire | `/documents/[token]` | demande OTP, vérification, consultation, PDF et réponse |
| Copropriétaires | `/coproprietaires` | `GET/POST /co-owner-invitations/`, `revoke`, `GET/PATCH/DELETE /co-owners/` |
| Connexion | `/connexion` | `GET /auth/csrf/`, `POST /auth/login/`, `GET /auth/me/` |
| Inscription | `/inscription` | `GET /auth/csrf/`, `POST /auth/register/` |
| Invitation locataire | `/invitation-locataire/[token]` | `POST /public-tenant-invitations/preview/`, `claim`, inscription et vérification |
| Espace locataire | `/espace-locataire` | `GET /tenant-portal/overview/`, baux, échéances, paiements, documents et PDF |

L’écran Copropriétaires permet maintenant au propriétaire principal d’inviter,
modifier ou retirer un copropriétaire. Il affiche aussi les invitations en attente
et leur historique. La quote-part et le niveau d’accès restent deux réglages
indépendants.

## Les fichiers à lire en premier

1. `src/app/layout.tsx` : enveloppe HTML commune et métadonnées.
2. `src/components/app-shell.tsx` : menu et barre supérieure de l’espace bailleur.
3. `src/lib/api-client.ts` : tous les appels HTTP regroupés au même endroit.
4. `src/types/domain.ts` : contrats partagés entre l’interface et Django.
5. `src/components/houses/house-workspace.tsx` : exemple simple de liste et formulaire.
6. `src/components/leases/lease-workspace.tsx` : exemple de cycle brouillon/actif/terminé.
7. `src/components/documents/public-document-access.tsx` : parcours public avec OTP.
8. `src/components/tenants/tenant-invitation-onboarding.tsx` : inscription ou
   rattachement depuis une invitation locataire.
9. `src/components/tenant-portal/tenant-portal-workspace.tsx` : dossier,
   échéances, réponses aux paiements et documents du locataire.

## Composants serveur et client

Les pages et layouts sont des composants serveur par défaut. Ils produisent du
HTML sans envoyer de JavaScript inutile au navigateur.

Les fichiers `*-workspace.tsx` contiennent `"use client"` car ils utilisent de
l’état React, des clics, des filtres et des formulaires. Les petits composants
visuels comme `DocumentPaper` restent indépendants de la gestion des données.

## Flux du document locataire

```text
Bailleur choisit un document
  -> choisit SMS, email et/ou WhatsApp
  -> Django crée un lien sécurisé
  -> le locataire ouvre /documents/[token]
  -> demande et saisit un OTP
  -> consulte le reçu ou la quittance
  -> confirme ou conteste s'il s'agit d'un reçu de paiement
```

Le fournisseur réel de SMS, email ou WhatsApp n’est pas encore branché. Django
place les messages dans une file `NotificationDelivery`. Après l’OTP, le même
jeton temporaire autorise la consultation JSON et le téléchargement du PDF.

## Accès aux données

Tous les composants appellent `/backend`. Une règle de réécriture dans
`next.config.ts` transmet ces requêtes à Django sans exposer
une deuxième origine au navigateur :

```dotenv
API_INTERNAL_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_URL=/backend
```

Le client HTTP transmet les cookies et le jeton CSRF. `AuthProvider` charge le
profil courant une seule fois et partage la session avec l’interface. `AppShell`
masque l’espace bailleur tant que la session n’est pas vérifiée et redirige les
visiteurs anonymes vers `/connexion`. Les permissions restent contrôlées par
Django : la protection visuelle ne remplace jamais l’autorisation backend.

## Invitation d’un locataire

L’écran Locataires crée ou réutilise une invitation active. Une fenêtre propose
le partage manuel par WhatsApp, email, SMS, partage natif ou copie, ainsi que
l’envoi automatique par Amazon SES. La page publique vérifie le jeton côté
Django et pré-remplit les coordonnées que le bailleur avait enregistrées.

Un visiteur crée son compte puis prouve la possession de son email ou de son
téléphone par OTP. Un utilisateur déjà connecté peut réclamer directement
l’invitation si son compte possède déjà la preuve correspondante. L’état final
est toujours relu depuis l’API : un paramètre d’URL ne peut pas simuler une
acceptation.

## Espace locataire

`TenantPortalShell` possède sa propre navigation. Il ne réutilise pas le menu du
bailleur, car les actions et la lecture du produit sont différentes. Un compte
portant les deux rôles peut basculer entre les espaces depuis le menu du compte.

`TenantPortalWorkspace` charge en parallèle la synthèse, les baux, échéances,
paiements et documents. Les actions de confirmation, contestation et
téléchargement utilisent exclusivement les routes `/tenant-portal/`. Le
frontend ne déduit donc jamais une autorisation depuis ce qui est affiché.

## Évolution au jalon 22

La route `/` est désormais la landing page publique et le tableau de bord
bailleur se trouve sur `/tableau-de-bord`. La vérification publique vit sur
`/verifier-quittance`. Les écrans bailleur et locataire partagent aussi le
module d'incidents. Le webhook Mobile Money est traité par Django ; le frontend
affiche `CONFIRMED_BY_PROVIDER` comme une preuve déjà validée.

## Évolutions des jalons 26 à 28

- Le téléphone saisi est converti au format international E.164. Les formulaires
  donnent l'exemple `+2250700000000`.
- Les écrans publics ne reçoivent plus les identités ni l'adresse lors de la
  simple vérification d'une référence.
- L'écran Paiements affiche les cautions détenues et ouvre un formulaire de
  clôture. Une affectation au loyer exige une case d'accord et une référence.
- Le tableau de bord appelle une seule synthèse agrégée au lieu de télécharger
  toutes les maisons, échéances et opérations.
- Les paiements et documents utilisent des pages de 25 éléments avec navigation.
  Le graphique Recharts reçoit six agrégats mensuels déjà calculés par Django.
- `public/llms.txt` expose une description structurée et prudente du MVP à
  l'adresse publique `/llms.txt`.
