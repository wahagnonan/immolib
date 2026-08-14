#!/bin/sh
# Draine la file de notifications ImmoLib (rappel de loyer, OTP, invitations,
# relances). A executer via cron toutes les heures (voir crontab-prod).
# Usage : /opt/immolib/infrastructure/process-notifications.sh

set -eu

cd /opt/immolib || exit 1
LOCK=/tmp/immolib-notifications.lock

flock -n "$LOCK" sh -c '
  docker compose exec -T api python manage.py process_notifications
'