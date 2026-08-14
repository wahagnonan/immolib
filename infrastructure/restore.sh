#!/bin/sh
# Restauration d'une sauvegarde chiffree ImmoLib.
# Usage : infrastructure/restore.sh /opt/immolib/backups/immolib_2026-08-10_020000.dump.enc
# Attention : ecrase la base courante. Arreter l'API avant :
#   docker compose stop api

set -eu

cd /opt/immolib || exit 1
if [ $# -ne 1 ]; then
  echo "Usage: $0 FICHIER.dump.enc" >&2
  exit 1
fi
ENC="$1"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/opt/immolib/backup-passphrase}"
DB_NAME="${POSTGRES_DB:-immolib}"
DB_USER="${POSTGRES_USER:-immolib}"

openssl enc -d -aes-256-cbc -pbkdf2 -in "$ENC" -out /tmp/immolib_restore.dump \
  -pass file:"$PASSPHRASE_FILE"
docker compose exec -T db pg_restore --clean --if-exists -U "$DB_USER" -d "$DB_NAME" \
  < /tmp/immolib_restore.dump
rm -f /tmp/immolib_restore.dump

echo "Restauration terminee. Relancer : docker compose start api"
