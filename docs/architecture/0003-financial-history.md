# ADR 0003 - Historique financier non destructif

## Decision

Un paiement ImmoLib n'est jamais corrige par suppression silencieuse.

- `Payment` decrit la somme recue.
- `PaymentAllocation` décrit chaque obligation concernée.
- `PaymentEvent` conserve chaque decision importante.
- Une erreur produit un evenement `CANCELLED` et recalcule le solde.

## Source de verite

Les allocations non annulees constituent la source de verite financiere. Le
champ `RentCharge.amount_paid` est un total mis en cache et recalcule dans la
même transaction.

## Caution et paiement multimois

`RentCharge` est le nom historique du modèle. Depuis le jalon 25, son champ
`charge_type` en fait une obligation financière de bail :

- `RENT` représente un mois de loyer ;
- `SECURITY_DEPOSIT` représente la caution ;
- une avance est une série d'obligations `RENT` futures, pas une somme flottante.

Un `Payment` peut posséder plusieurs `PaymentAllocation`. Toutes ses
affectations doivent appartenir au même bail, utiliser la même devise et leur
somme doit être strictement égale au montant du paiement. ImmoLib ne conserve
donc aucun crédit non affecté.

## Contestation

Selon la decision produit du MVP, une declaration du bailleur est valide. Une
contestation du locataire change le statut du paiement et cree un evenement,
mais ne retire pas automatiquement la somme de l'echeance.
