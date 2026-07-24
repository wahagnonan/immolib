# ImmoLib Web

Interface bailleur du MVP ImmoLib, construite avec Next.js 16, React 19,
TypeScript, Tailwind CSS 4 et Recharts.

## Demarrage

```bash
cp .env.local.example .env.local
npm install
npm run dev
```

Ouvrir ensuite `http://localhost:3000`.

Le frontend utilise directement l’API Django :

```dotenv
API_INTERNAL_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_URL=/backend
```

Les routes `/connexion` et `/inscription` utilisent les sessions Django et la
protection CSRF. L'espace bailleur redirige les utilisateurs sans
session vers la connexion et le menu du compte permet de se deconnecter.
La route `/` est la landing page publique. Le tableau de bord bailleur se trouve
sur `/tableau-de-bord`.

Le système visuel utilise un rouge principal `#D4342B`, un fond chaud et des
surfaces blanches. Les états métier gardent leurs couleurs sémantiques, mais les
icônes et indicateurs restent neutres afin de réduire le bruit visuel.

La route `/verifier-quittance` accepte une reference de recu ou de quittance et
interroge l'endpoint public. Elle n'affiche ni telephone ni identifiant interne.

Depuis l'écran Locataires, un bailleur peut préparer un lien d'invitation,
l'envoyer manuellement ou par Amazon SES, puis suivre le statut du locataire.
La route `/invitation-locataire/[token]` pré-remplit l'inscription et rattache
le compte seulement après vérification de l'email ou du téléphone enregistré.

La route `/espace-locataire` fournit ensuite un espace authentifié distinct :
bail et maison, solde, échéances, paiements à confirmer ou contester, reçus,
quittances, incidents et téléchargement PDF. Un compte qui possède aussi une maison peut
basculer entre les espaces bailleur et locataire.

L'écran `/incidents` permet au bailleur de prendre en compte un signalement,
démarrer l'intervention et annoncer sa résolution. Le locataire confirme ensuite
la clôture ou rouvre le dossier avec un motif. Tous les changements et
commentaires restent dans un historique partagé.

Le tableau de bord réel charge les maisons, échéances et paiements du compte
connecté. Ses indicateurs mensuels sont recalculés à partir des montants déjà
validés par Django. Le graphique Recharts compare les montants attendus et
encaissés des six dernières périodes.

L'écran Documents charge aussi la file de notifications du compte. Il permet de
filtrer les messages en attente, en cours, envoyés ou en échec et n'affiche que
des coordonnées de locataire masquées. Un second filtre sépare les rappels de
loyer, les liens de document, les invitations locataires et les codes OTP.

Chaque reçu ou quittance peut être téléchargé en PDF. Le locataire obtient le
même fichier depuis son lien public uniquement après la vérification OTP.

## Commandes

```bash
npm run dev     # serveur de developpement
npm run lint    # controle ESLint
npm run build   # build de production et controle TypeScript
```

## Organisation

```text
src/
├── app/          # pages et routes App Router
├── components/   # interface partagee et composants interactifs
├── lib/          # client HTTP et utilitaires
└── types/        # contrats TypeScript alignes sur l'API Django
```
