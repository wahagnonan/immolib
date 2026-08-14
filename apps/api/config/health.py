"""Health check /api/v1/health/ destine au monitoring externe.

Sans authentification : c'est une sonde (UptimeRobot, cron, Sentry, etc.).
Retourne 200 quand tout va bien, 503 sinon :

- base de donnees injoignable ;
- file de notifications bloquee : une NotificationDelivery QUEUED eligible
  (next_attempt_at passe) sans adaptateur configure pour son canal depuis
  au moins HEALTH_QUEUE_STALL_MINUTES minutes ne pourra jamais etre envoyee
  (mauvais IMMOLIB_*_NOTIFICATION_ADAPTER ou worker arrete).

Le endpoint /health/ (plus simple, toujours 200) reste le health check de
lancement de Render : un 503 ici ne doit PAS declencher de redemarrage du
service, c'est une alerte pour un operateur.
"""

from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone


def service_health(request):
    checks = {}
    degraded = False

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        checks["database"] = {
            "status": "error",
            "detail": f"{exc.__class__.__name__}: {exc}",
        }
        degraded = True

    from modules.documents.models import NotificationDelivery

    configured_channels = {
        channel
        for channel, adapter in settings.NOTIFICATION_ADAPTERS.items()
        if adapter
    }
    now = timezone.now()
    cutoff = now - timedelta(minutes=settings.HEALTH_QUEUE_STALL_MINUTES)
    stuck = (
        NotificationDelivery.objects.filter(
            status=NotificationDelivery.Status.QUEUED,
            attempt_count__lt=settings.NOTIFICATION_MAX_ATTEMPTS,
            created_at__lte=cutoff,
        )
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .exclude(channel__in=configured_channels)
        .count()
    )
    checks["notification_queue"] = {
        "status": "ok" if stuck == 0 else "degraded",
        "queued_without_adapter_since_cutoff": stuck,
        "stall_minutes": settings.HEALTH_QUEUE_STALL_MINUTES,
    }
    if stuck:
        degraded = True

    payload = {
        "status": "ok" if not degraded else "degraded",
        "service": "immolib-api",
        "checks": checks,
    }
    return JsonResponse(payload, status=200 if not degraded else 503)
