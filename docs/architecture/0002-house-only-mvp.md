# ADR 0002 - MVP limite aux maisons

## Decision

L'utilisateur ne peut creer que des maisons dans le MVP.

Le modele interne s'appelle `Property` avec `property_type=HOUSE`. Le vocabulaire
de l'interface utilisera toujours le mot **Maison**.

## Regles

- une maison doit avoir exactement un proprietaire principal ;
- elle peut avoir zero, un ou plusieurs coproprietaires ;
- un utilisateur ne peut apparaitre qu'une fois parmi les proprietaires d'une
  meme maison ;
- seuls les niveaux `ACTIVE` et `OBSERVER` existent pour les coproprietaires ;
- la somme des quotes-parts sera controlee par le service metier lors d'un
  prochain jalon.

## Evolution

De nouveaux types de biens pourront etre ajoutes sans changer les relations des
baux, echeances et paiements.
