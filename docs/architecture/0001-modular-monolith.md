# ADR 0001 - Monolithe modulaire

## Decision

ImmoLib commence comme un monolithe modulaire Django dans un monorepo.

## Pourquoi

- Le code reste simple a lancer et a comprendre.
- Les transactions financieres restent dans une seule base PostgreSQL.
- Chaque domaine metier possede son propre module Django.
- Un module pourra etre extrait plus tard si la charge le justifie.

## Modules prevus

```text
accounts -> properties -> leases -> billing -> payments -> receipts
```

Le MVP ne contient ni gestionnaire, ni annonces, ni wallet interne.
