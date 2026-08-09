"""Selecteurs admin : listes paginees avec recherche et filtres.

Les requetes restent cote serveur : le frontend ne recoit jamais l'integralite
des tables, seulement la page demandee.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q, Subquery

from modules.documents.models import NotificationDelivery
from modules.leases.models import Lease, Tenant
from modules.properties.models import Property
from modules.subscriptions.models import Subscription, SubscriptionTransaction

from .models import AuditLog

User = get_user_model()


def _user_search(q: Q, term: str) -> Q:
    return q & (
        Q(phone__icontains=term)
        | Q(email__icontains=term)
        | Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
    )


def admin_users_queryset(*, search: str = "", role: str = "", status: str = "", profile: str = "", plan: str = ""):
    """Users avec compteurs et abonnement. Filtres :
    role ADMIN|USER, status active|suspended, profile landlord|tenant|both,
    plan free|essential|pro."""
    queryset = (
        User.objects.all()
        .select_related("subscription__plan")
        .annotate(
            houses_count=Count("ownerships", distinct=True),
            tenants_count=Count("tenant_profiles", distinct=True),
        )
        .order_by("-date_joined")
    )
    if search:
        q = _user_search(Q(), search)
        queryset = queryset.filter(q)
    if role:
        queryset = queryset.filter(role=role)
    if status == "suspended":
        queryset = queryset.filter(is_active=False)
    elif status == "active":
        queryset = queryset.filter(is_active=True)
    if profile == "landlord":
        queryset = queryset.filter(ownerships__isnull=False).distinct()
    elif profile == "tenant":
        queryset = queryset.filter(tenant_profiles__status="ACTIVE").distinct()
    elif profile == "both":
        queryset = queryset.filter(
            ownerships__isnull=False, tenant_profiles__status="ACTIVE"
        ).distinct()
    if plan:
        queryset = queryset.filter(subscription__plan__slug=plan)
    return queryset


def admin_landlords_queryset(*, search: str = "", status: str = "", plan: str = ""):
    """Bailleurs (comptes detenant au moins une maison), avec maisons et locataires."""
    queryset = (
        User.objects.filter(ownerships__isnull=False)
        .select_related("subscription__plan")
        .annotate(
            houses_count=Count("ownerships", distinct=True),
            tenants_count=Count("ownerships__property__tenants", distinct=True),
        )
        .order_by("-date_joined")
    )
    if search:
        q = _user_search(Q(), search)
        queryset = queryset.filter(q)
    if status == "suspended":
        queryset = queryset.filter(is_active=False)
    elif status == "active":
        queryset = queryset.filter(is_active=True)
    if plan:
        queryset = queryset.filter(subscription__plan__slug=plan)
    return queryset


def admin_tenants_queryset(*, search: str = "", status: str = ""):
    """Fiches locataires (une fiche par maison, comme dans l'espace bailleur)."""
    queryset = Tenant.objects.select_related("property", "linked_user").order_by(
        "-created_at"
    )
    if search:
        queryset = queryset.filter(
            Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(property__name__icontains=search)
        )
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def admin_houses_queryset(*, search: str = "", status: str = "", occupancy: str = ""):
    """Maisons avec bailleur principal, locataire courant (bail actif) et statut."""
    current_lease = (
        Lease.objects.filter(
            property=OuterRef("pk"),
            status="ACTIVE",
        )
        .order_by("-start_date")
        .values("tenant__full_name")[:1]
    )
    queryset = (
        Property.objects.all()
        .annotate(
            current_tenant_name=Subquery(current_lease),
            has_active_lease=Exists(
                Lease.objects.filter(
                    property=OuterRef("pk"), status="ACTIVE"
                )
            ),
            primary_owner_name=Subquery(
                User.objects.filter(
                    ownerships__property=OuterRef("pk"),
                    ownerships__role="PRIMARY",
                ).values("first_name")[:1]
            ),
        )
        .order_by("-created_at")
    )
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(address__icontains=search)
            | Q(city__icontains=search)
            | Q(commune__icontains=search)
        )
    if status:
        queryset = queryset.filter(status=status)
    if occupancy == "with_tenant":
        queryset = queryset.filter(has_active_lease=True)
    elif occupancy == "without_tenant":
        queryset = queryset.filter(has_active_lease=False)
    return queryset


def admin_subscriptions_queryset(*, search: str = "", plan: str = "", status: str = ""):
    """Abonnements avec utilisateur et plan."""
    queryset = Subscription.objects.select_related("user", "plan").order_by(
        "-created_at"
    )
    if search:
        queryset = queryset.filter(
            Q(user__phone__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
        )
    if plan:
        queryset = queryset.filter(plan__slug=plan)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def admin_payments_queryset(*, search: str = "", status: str = "", plan: str = ""):
    """Paiements d'abonnement (SubscriptionTransaction), jamais de details sensibles."""
    queryset = SubscriptionTransaction.objects.select_related(
        "user", "plan"
    ).order_by("-created_at")
    if search:
        queryset = queryset.filter(
            Q(user__phone__icontains=search)
            | Q(user__email__icontains=search)
            | Q(provider_reference__icontains=search)
        )
    if status:
        queryset = queryset.filter(status=status)
    if plan:
        queryset = queryset.filter(plan__slug=plan)
    return queryset


def admin_notifications_queryset(*, search: str = "", channel: str = "", status: str = ""):
    """Envois de messages (NotificationDelivery)."""
    queryset = NotificationDelivery.objects.all().order_by("-created_at")
    if search:
        queryset = queryset.filter(
            Q(destination__icontains=search)
            | Q(kind__icontains=search)
            | Q(failure_reason__icontains=search)
        )
    if channel:
        queryset = queryset.filter(channel=channel)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def admin_audit_logs_queryset(*, search: str = "", action: str = "", from_date: str = "", to_date: str = ""):
    """Journal d'audit."""
    queryset = AuditLog.objects.select_related("admin").order_by("-created_at")
    if search:
        queryset = queryset.filter(
            Q(admin__phone__icontains=search)
            | Q(admin__email__icontains=search)
            | Q(target_id__icontains=search)
        )
    if action:
        queryset = queryset.filter(action=action)
    if from_date:
        queryset = queryset.filter(created_at__date__gte=from_date)
    if to_date:
        queryset = queryset.filter(created_at__date__lte=to_date)
    return queryset
