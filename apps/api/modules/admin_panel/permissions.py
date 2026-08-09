"""Permissions de l'espace d'administration.

Seul le role systeme ADMIN (portee par User.role, jamais modifiable par
l'API publique) ouvre les routes /admin/*. La couche de permissions par
operation (users.read, subscriptions.update, ...) permet d'ajouter plus tard
un role SUPER_ADMIN ou des permissions fines sans refonte.
"""

from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

from modules.accounts.models import User


class Perm:
    """Noms canoniques des permissions d'administration."""

    USERS_READ = "users.read"
    USERS_UPDATE = "users.update"
    USERS_SUSPEND = "users.suspend"
    LANDLORDS_READ = "landlords.read"
    TENANTS_READ = "tenants.read"
    HOUSES_READ = "houses.read"
    SUBSCRIPTIONS_READ = "subscriptions.read"
    SUBSCRIPTIONS_UPDATE = "subscriptions.update"
    PAYMENTS_READ = "payments.read"
    NOTIFICATIONS_READ = "notifications.read"
    AUDIT_LOGS_READ = "audit_logs.read"
    ADMINS_MANAGE = "admins.manage"
    SETTINGS_MANAGE = "settings.manage"


ADMIN_PERMISSIONS = frozenset(
    {
        Perm.USERS_READ,
        Perm.USERS_UPDATE,
        Perm.USERS_SUSPEND,
        Perm.LANDLORDS_READ,
        Perm.TENANTS_READ,
        Perm.HOUSES_READ,
        Perm.SUBSCRIPTIONS_READ,
        Perm.SUBSCRIPTIONS_UPDATE,
        Perm.PAYMENTS_READ,
        Perm.NOTIFICATIONS_READ,
        Perm.AUDIT_LOGS_READ,
    }
)

# Reserves a un futur role SUPER_ADMIN (architecture prevue, non active en MVP).
SUPER_ADMIN_PERMISSIONS = ADMIN_PERMISSIONS | frozenset(
    {Perm.ADMINS_MANAGE, Perm.SETTINGS_MANAGE}
)


def has_permission(user, permission: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.role != User.Role.ADMIN:
        return False
    return permission in ADMIN_PERMISSIONS


class IsAdmin(BasePermission):
    """Autorise uniquement les comptes avec le role systeme ADMIN.

    Non connecte -> 401 (NotAuthenticated) ; connecte sans role ADMIN -> 403.
    """

    message = "Acces reserve a l'administration ImmoLib."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user.is_authenticated:
            raise NotAuthenticated("Authentification requise.")
        return user.role == User.Role.ADMIN


def admin_permission(permission: str):
    """Fabrique une permission DRF combinant IsAdmin et la permission demandee."""

    class _HasAdminPermission(IsAdmin):
        def has_permission(self, request, view) -> bool:
            return super().has_permission(request, view) and has_permission(
                request.user, permission
            )

    _HasAdminPermission.__name__ = "HasAdminPermission" + "_".join(
        permission.split(".")
    )
    return _HasAdminPermission
