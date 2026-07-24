# ADR 0011 — Cycle de vie de la caution sans portefeuille

## Décision

ImmoLib trace la caution mais ne détient jamais les fonds. L'obligation
`RentCharge` de type `SECURITY_DEPOSIT` conserve deux montants :

- `amount_paid` : somme encaissée historiquement au titre de la caution ;
- `amount_released` : somme remboursée, retenue ou affectée à un loyer.

Le solde encore détenu hors ImmoLib est calculé par
`amount_paid - amount_released`.

## Journal append-only

Chaque libération crée un `SecurityDepositMovement` :

- `REFUND` pour un remboursement réalisé hors ImmoLib ;
- `RETENTION` avec un motif obligatoire ;
- `APPLY_TO_RENT` vers une échéance du même bail.

Une affectation au loyer exige `agreement_confirmed=true` et une
`agreement_reference`. Elle crée un `Payment` marqué
`is_cash_movement=false`, afin de solder le loyer sans compter deux fois la
même trésorerie.

Les mouvements ne sont ni modifiés ni supprimés. Une clé d'idempotence empêche
les doublons. Chaque mouvement produit un document
`DEPOSIT_SETTLEMENT` vérifiable.

## Conséquences

- Un versement de caution déjà partiellement libéré ne peut plus être annulé
  s'il ferait passer l'encaissement sous le montant libéré.
- Le bailleur garde la responsabilité du remboursement ou de la retenue réelle.
- ImmoLib fournit une chronologie et des documents, pas un compte séquestre.
