# Comprendre le jalon 21 : l’espace locataire

Le jalon 21 donne une utilité durable au compte créé au jalon 20. Le locataire
retrouve son dossier sans dépendre d’un nouveau lien envoyé par le bailleur.

## Ce que voit le locataire

- sa maison et l’identité du bailleur principal ;
- son bail actif, le loyer, les charges, la caution et la date d’échéance ;
- son solde restant et sa prochaine échéance ;
- l’historique de toutes ses échéances ;
- les paiements déclarés et leur état ;
- ses reçus et quittances, consultables et téléchargeables en PDF ;
- ses préférences de notifications.

Le portail accepte plusieurs locations pour le même compte. Les soldes sont
regroupés par devise afin de rester compatibles avec l’ambition panafricaine.

## Reçu et quittance

Un **reçu de paiement** prouve qu’une somme précise a été enregistrée. Il peut
exister après un paiement partiel.

Une **quittance de loyer** est produite lorsque toute l’échéance est soldée.
Elle atteste donc le règlement complet de la période.

Un document annulé reste visible avec le statut `VOIDED` pour préserver
l’historique, mais il n’est plus une preuve active.

## États d’un paiement hors ImmoLib

| État | Signification | Action locataire |
| --- | --- | --- |
| `RECORDED_BY_OWNER` | Le bailleur déclare avoir reçu la somme | Confirmer ou contester |
| `CONFIRMED_BY_TENANT` | Le locataire reconnaît la déclaration | Consulter ou signaler ensuite un problème |
| `CONFIRMED_BY_PROVIDER` | Le fournisseur Mobile Money a confirmé la transaction | Aucune confirmation supplémentaire |
| `DISPUTED_BY_TENANT` | Le locataire a fourni un motif de contestation | Confirmer si le désaccord est résolu |
| `CANCELLED` | Le bailleur a annulé une erreur tracée | Aucune action |

La réponse ajoute un `PaymentEvent`. Elle ne supprime ni le statut précédent ni
le motif, ce qui garde une chronologie vérifiable.

## Endpoints

| Méthode | URL | Rôle |
| --- | --- | --- |
| `GET` | `/api/v1/tenant-portal/overview/` | Synthèse et prochaine échéance |
| `GET` | `/api/v1/tenant-portal/leases/` | Baux actifs ou terminés |
| `GET` | `/api/v1/tenant-portal/charges/` | Échéances |
| `GET` | `/api/v1/tenant-portal/payments/` | Paiements et événements |
| `POST` | `/api/v1/tenant-portal/payments/{id}/confirm/` | Confirmer |
| `POST` | `/api/v1/tenant-portal/payments/{id}/dispute/` | Contester avec motif |
| `GET` | `/api/v1/tenant-portal/documents/` | Reçus et quittances |
| `GET` | `/api/v1/tenant-portal/documents/{id}/pdf/` | Télécharger sa preuve |

## Pourquoi ne pas réutiliser l’API bailleur ?

Le bailleur peut créer des baux, générer des échéances, enregistrer ou annuler
des paiements et partager des documents. Le locataire peut seulement lire son
dossier et répondre aux paiements qui le concernent.

Des endpoints distincts rendent cette différence visible dans le code et
réduisent le risque d’autoriser une action par erreur.

## Où lire le code

1. `modules/tenant_portal/selectors.py` : périmètre de données par `linked_user`.
2. `modules/tenant_portal/api/views.py` : synthèse, listes, réponses et PDF.
3. `modules/payments/services.py` : transitions confirmée ou contestée.
4. `modules/tenant_portal/tests/test_api.py` : preuves d’isolation.
5. `src/components/tenant-portal/tenant-portal-shell.tsx` : navigation du rôle.
6. `src/components/tenant-portal/tenant-portal-workspace.tsx` : écran complet.

## Évolution au jalon 22

Le jalon 22 ajoute le webhook Mobile Money signé et générique ainsi que les
incidents de maintenance. Le paiement fournisseur est validé automatiquement ;
les déclarations hors ImmoLib gardent le parcours de confirmation ou
contestation du locataire.
