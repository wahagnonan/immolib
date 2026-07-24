# Comprendre la refonte frontend

Cette refonte ne change pas les règles Django ni les contrats de l'API. Elle
améliore la manière dont les utilisateurs comprennent et accomplissent les
actions existantes.

## 1. Les tokens avant les pages

La première étape est `src/app/globals.css`. Les couleurs, bordures, boutons,
champs, cartes, tableaux et badges y sont définis une seule fois. Cette
approche évite de corriger vingt pages lorsqu'un rayon ou une couleur change.

La palette principale est :

```text
brand   #D4342B
ink     #121012
canvas  #F9F6F5
line    #E5DFDC
```

## 2. Une couleur n'est pas une décoration

Le rouge montre l'identité ImmoLib et l'action principale. Le vert est réservé
aux succès, l'ambre à l'attente et le rouge clair aux erreurs.

Si toutes les cartes possèdent une couleur différente, l'utilisateur ne sait
plus ce qui est important. Les indicateurs du tableau de bord utilisent donc
des icônes neutres et la donnée chiffrée porte la hiérarchie.

## 3. La landing page guide une décision

Une bonne landing page n'énumère pas seulement des fonctionnalités. Elle relie
chaque fonctionnalité à un problème :

- calculs dispersés → échéances reliées au bail ;
- paiement difficile à prouver → reçu et quittance vérifiables ;
- messages perdus → historique partagé ;
- incident annoncé oralement → suivi jusqu'à la clôture.

Les CTA emploient une action concrète : « Ajouter ma première maison ».

## 4. Pourquoi Recharts

`RentCollectionChart` reçoit les mêmes `RentCharge` que le reste du tableau de
bord. Il agrège les six dernières périodes et compare :

```text
expected  = somme des amount_due
collected = somme des amount_paid
```

Les échéances annulées sont exclues. Le composant ne devine aucune donnée et
réutilise `formatMoney` ainsi que `monthLabel`.

Le graphique vit dans un composant client séparé. Le reste de l'application ne
dépend pas directement de Recharts.

## 5. Navigation mobile

La barre bailleur contient trop de modules pour tenir correctement sur un
téléphone. Une liste horizontale aurait obligé l'utilisateur à deviner qu'elle
peut défiler. Le nouveau menu affiche :

- le module courant ;
- un bouton explicite ;
- une grille complète après ouverture.

L'espace locataire applique le même principe.

## 6. Où lire le code

1. `src/app/globals.css` : tokens et primitives.
2. `src/components/brand.tsx` : identité compacte.
3. `src/components/navigation.tsx` : navigation responsive.
4. `src/components/app-shell.tsx` : structure bailleur.
5. `src/components/tenant-portal/tenant-portal-shell.tsx` : structure locataire.
6. `src/components/auth/auth-shell.tsx` : inscription et connexion.
7. `src/app/page.tsx` : landing page.
8. `src/components/dashboard/rent-collection-chart.tsx` : Recharts.

## 7. Règle pour les prochaines pages

Avant d'ajouter un nouveau composant, vérifier si une primitive existe déjà.
Une nouvelle carte, couleur ou modal ne doit être créée que si elle représente
une interaction réellement différente.

