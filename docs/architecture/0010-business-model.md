# ADR 0010 — Modèle économique du MVP

## Décision

ImmoLib suit un modèle d'abonnement payé par le bailleur. Le locataire et les
copropriétaires ne paient pas pour consulter ou confirmer les informations qui
les concernent.

Le prix dépend du nombre de maisons actives, pas du montant des loyers :

| Offre | Prix mensuel indicatif | Limite |
|---|---:|---:|
| Découverte | 0 FCFA | 1 maison |
| Essentiel | 3 000 FCFA | 5 maisons |
| Pro | 7 500 FCFA | 20 maisons |
| Patrimoine | 15 000 FCFA | 50 maisons |

Ces montants sont des hypothèses de lancement à tester avec 20 à 30 bailleurs.
Les règles d'abonnement ne doivent pas être développées avant cette validation.

## Canaux de notification

- l'application, le push et l'email font partie de l'abonnement ;
- le partage WhatsApp manuel reste inclus ;
- les SMS et WhatsApp automatisés utilisent des crédits séparés ;
- aucun canal payant ne doit être présenté comme illimité.

## Paiements des loyers

ImmoLib ne prélève pas de pourcentage sur les loyers et ne détient pas les
fonds. Les frais du fournisseur Mobile Money restent visibles et distincts.

## Indicateurs du pilote

- conversion vers une offre payante : au moins 30 % ;
- revenu moyen visé par bailleur payant : 5 500 à 7 500 FCFA ;
- volume initial : 150 à 300 maisons ;
- mesure principale : nombre de bailleurs qui continuent à utiliser le suivi
  mensuel après trois mois.

ImmoLib ne vend pas les données des bailleurs ou des locataires.
