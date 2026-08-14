#!/bin/sh
# Sauvegarde chiffree de la base PostgreSQL ImmoLib.
# Installation (hote) :
#   sudo apt install openssl
#   echo -n 'une-phrase-secrete-longue-et-aleatoire' > /opt/immolib/backup-passphrase
#   chmod 600 /opt/immolib/backup-passphrase
#   sudo cp infrastructure/backup.sh /opt/immolib/backup.sh && sudo chmod +x /opt/immolib/backup.sh
# Planification : ajouter a /etc/cron.d/immolib :
#   45 2 * * * root /opt/immolib/backup.sh
#
# Option hors site : remplacer BACKUP_OFFSITE_CMD (ex: rclone copy "$DUMP" remote:)

set -eu

cd /opt/immolib || exit 1
BACKUP_DIR="${BACKUP_DIR:-/opt/immolib/backups}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/opt/immolib/backup-passphrase}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DB_NAME="${POSTGRES_DB:-immolib}"
DB_USER="${POSTGRES_USER:-immolib}"

mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y-%m-%d_%H%M%S)
DUMP="$BACKUP_DIR/immolib_$DATE.dump"
ENC="$DUMP.enc"

docker compose exec -T db pg_dump -Fc -U "$DB_USER" "$DB_NAME" > "$DUMP"
openssl enc -aes-256-cbc -pbkdf2 -salt -in "$DUMP" -out "$ENC" \
  -pass file:"$PASSPHRASE_FILE"
rm -f "$DUMP"

echo "OK $ENC ($(du -h "$ENC" | cut -f1))"

# Rotation : ne garder que RETENTION_DAYS jours de sauvegardes locales.
find "$BACKUP_DIR" -name 'immolib_*.dump.enc' -mtime +"$RETENTION_DAYS" -delete

# Copie hors site (a configurer).
if [ -n "${BACKUP_OFFSITE_CMD:-}" ]; then
  eval "$BACKUP_OFFSITE_CMD"
fi
