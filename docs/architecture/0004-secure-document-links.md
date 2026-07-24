# ADR 0004 - Liens de documents signes et OTP

## Decision

Un locataire sans compte peut consulter un recu ou une quittance apres deux
preuves successives :

1. un lien signe, temporaire et revocable ;
2. un code OTP envoye vers son telephone ou son email.

Le jeton du lien n'est pas stocke en clair. Il est signe avec la cle secrete de
l'application et contient seulement l'identifiant du lien.

## Durees

- lien de document : 30 jours ;
- OTP : 10 minutes et cinq essais ;
- autorisation apres OTP : 24 heures.

## Environnements

`EXPOSE_TEST_OTP` reste desactive par defaut. Cette option ne doit jamais etre
activee en production. Les tests l'activent temporairement pour verifier le
parcours complet.
