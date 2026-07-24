# Infrastructure

Ce dossier contiendra progressivement les configurations de deploiement,
sauvegarde, surveillance et stockage prive.

## Taches planifiees

Deux commandes Django sont maintenant pretes a etre lancees par un planificateur :

```bash
python manage.py run_billing_cycle
python manage.py process_notifications --limit 100
```

La seconde commande peut etre executee chaque minute. Elle quitte apres un lot et
ne maintient pas de processus infini. En local, `--simulate` teste le flux sans
contacter de fournisseur ; ce mode marque les messages comme envoyes et ne doit
donc etre utilise que sur des donnees de developpement.

La premiere commande doit etre lancee chaque jour. En plus des echeances et des
statuts, elle cree les rappels de loyer planifies pour la date courante. Elle est
idempotente : une reprise ou une execution double ne duplique pas les messages.

Exemple de frequence cible :

```cron
5 6 * * * cd /app/apps/api && python manage.py run_billing_cycle
* * * * * cd /app/apps/api && python manage.py process_notifications --limit 100
```

Le planificateur reel du fournisseur d'hebergement peut remplacer cron tout en
gardant ces deux commandes et ces frequences.
