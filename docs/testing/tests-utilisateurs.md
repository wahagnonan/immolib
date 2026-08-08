# Tests utilisateurs (UAT)

Les tests automatisés couvrent la logique. Les tests utilisateurs valident le
parcours réel tel qu'un propriétaire ou un locataire le vivrait. À exécuter
manuellement sur la version déployée (ou locale) avant chaque mise en production.

## Préparation

1. Base de données vierge (ou jeu de données propre).
2. Backend démarré avec `EXPOSE_TEST_OTP=true` en développement.
3. Navigateurs : un navigateur récent (Chrome/Firefox) et un mobile (Chrome Android / Safari iOS).

## Scénario 1 — Nouveau propriétaire

- [ ] Ouvrir `/inscription` sur mobile et sur desktop : aucun débordement horizontal.
- [ ] L'indicatif +225 est pré-sélectionné ; la liste contient tous les pays.
- [ ] Saisir un numéro de téléphone invalide (ex. 4 chiffres) : l'enregistrement est bloqué ou le backend renvoie une erreur claire.
- [ ] Saisir deux mots de passe différents : message « Les deux mots de passe ne correspondent pas. »
- [ ] Saisir un email déjà utilisé : message clair.
- [ ] S'inscrire avec un email unique : l'étape de vérification s'affiche, le code est reçu (SMS simulé ou email).
- [ ] Saisir un code erroné 5 fois : le code devient invalide (message clair).
- [ ] Saisir le bon code : redirection vers le tableau de bord.

## Scénario 2 — Connexion

- [ ] Se connecter avec l'email et le bon mot de passe : accès au tableau de bord.
- [ ] Se connecter avec un mauvais mot de passe : « Email ou mot de passe incorrect. »
- [ ] « Mot de passe oublié ? » : recevoir un code, le saisir, changer le mot de passe, se reconnecter avec le nouveau.
- [ ] Se déconnecter puis accéder à une page privée : redirection vers la connexion.

## Scénario 3 — Gestion locative (propriétaire)

- [ ] Créer une maison (nom, ville, commune, adresse, repère) : carte visible avec « 1 propriétaire ».
- [ ] Ajouter un locataire (maison, nom complet, téléphone avec indicatif, email) : fiche visible.
- [ ] Inviter le locataire sur ImmoLib : statut passe à « Invité », lien de partage disponible.
- [ ] Créer un bail (maison, locataire, dates, loyer, jour limite) : brouillon créé.
- [ ] Activer le bail : la maison passe à « Occupée ».
- [ ] Générer les échéances du mois : lignes créées, montants corrects (loyer + charges).
- [ ] Initier un paiement P2P (choix opérateur et montant) : transaction créée avec référence.
- [ ] Confirmer la réception depuis l'écran Paiements (montant du contrat corrigé) : échéance soldée, quittance générée.
- [ ] Ouvrir la quittance générée : montant, périodes et référence cohérents.
- [ ] Signaler un incident (titre, description, priorité) : suivi créé, commentaire possible.

## Scénario 4 — Lien public (locataire)

- [ ] Depuis la quittance, partager le lien sécurisé (ex. WhatsApp simulé).
- [ ] Ouvrir le lien dans un navigateur sans session : demande de code à 6 chiffres.
- [ ] Saisir le code reçu : la quittance s'affiche sans connexion.
- [ ] Vérifier une référence publique (page d'accueil, champ « IMM-QUT-2026-… ») : résultat correct pour une référence valide et une invalide.

## Règles d'acceptation

- Aucun message d'erreur technique (stack trace, JSON brut) visible.
- Aucune étape sans retour visuel (état de chargement ou message).
- Tous les formulaires navigables au clavier (Tab, Entrée).
- Pas de page blanche sur Chrome, Firefox, Safari et un mobile récent.
- Les montants sont formatés (ex. 200 000 FCFA) et cohérents partout.

## Compte rendu

Noter pour chaque scénario : statut (OK / KO), navigateur, capture d'écran en
cas de KO, et reproduction minimale.
