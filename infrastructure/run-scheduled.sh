#!/bin/sh
# Commandes planifiees ImmoLib. A executer via cron sur l'hote du serveur
# (voir infrastructure/crontab-prod). Le verrou evite les chevauchements
# si une execution depasse l'intervalle prevu.
# Usage : /opt/immolib/infrastructure/run-scheduled.sh

set -eu

cd /opt/immolib || exit 1
LOCK=/tmp/immolib-scheduled.lock

flock -n "$LOCK" sh -c '
  docker compose exec -T api python manage.py run_billing_cycle
  docker compose exec -T api python manage.py process_notifications
  docker compose exec -T api python manage.py check_subscription_expirations
'
