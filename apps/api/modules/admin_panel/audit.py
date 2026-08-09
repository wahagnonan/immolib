"""Enregistrement centralise des actions sensibles dans le journal d'audit."""

from typing import Any

from django.db import transaction

from modules.accounts.models import User

from .models import AuditLog


@transaction.atomic
def log_admin_action(
    *,
    admin: User | None,
    action: str,
    target_type: str = "",
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request=None,
) -> AuditLog:
    """Cree une entree de journal. `request` est optionnel : l'adresse IP
    n'est enregistree que si elle est disponible et appropriee."""
    ip_address = None
    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR")
    return AuditLog.objects.create(
        admin=admin if (admin is not None and admin.is_authenticated) else None,
        action=action,
        target_type=target_type,
        target_id=target_id or "",
        metadata=metadata or {},
        ip_address=ip_address,
    )
