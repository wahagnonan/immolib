"""Services de l'espace admin : metriques du dashboard, suspension,
actions sur les abonnements. Chaque action sensible est tracee dans l'audit.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.leases.models import Tenant
from modules.properties.models import Property
from modules.subscriptions.models import (
    Subscription,
    SubscriptionPlan,
    SubscriptionTransaction,
)

from .audit import log_admin_action
from .models import AuditLog

User = get_user_model()


def _month_start(now=None) -> "timezone.datetime":
    now = now or timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def dashboard_metrics() -> dict:
    """Metriques globales, calculees uniquement depuis les donnees reelles."""
    now = timezone.now()
    month_start = _month_start(now)
    previous_month_start = (
        month_start.replace(day=1) - timedelta(days=1)
    ).replace(day=1)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    users_total = User.objects.count()
    landlords_total = (
        User.objects.filter(ownerships__isnull=False).distinct().count()
    )
    tenants_total = (
        User.objects.filter(tenant_profiles__status="ACTIVE").distinct().count()
    )
    admins_total = User.objects.filter(role=User.Role.ADMIN).count()

    houses_total = Property.objects.count()
    houses_occupied = Property.objects.filter(status=Property.Status.OCCUPIED).count()
    houses_recent = Property.objects.filter(created_at__gte=week_ago).count()

    subscriptions = Subscription.objects.select_related("plan")
    plan_breakdown = {
        row["plan__slug"]: row["count"]
        for row in subscriptions.values("plan__slug").annotate(
            count=Count("id")
        )
    }
    subscriptions_active = subscriptions.filter(
        status=Subscription.Status.ACTIVE
    ).count()
    subscriptions_expired = subscriptions.filter(
        status=Subscription.Status.EXPIRED
    ).count()

    successful = SubscriptionTransaction.objects.filter(
        status=SubscriptionTransaction.Status.SUCCESSFUL,
        currency=settings.SUBSCRIPTION_CURRENCY,
    )
    revenue = {
        "currency": settings.SUBSCRIPTION_CURRENCY,
        "month": (
            successful.filter(completed_at__gte=month_start).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        ),
        "day": (
            successful.filter(completed_at__gte=today_start).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        ),
        "previous_month": (
            successful.filter(
                completed_at__gte=previous_month_start,
                completed_at__lt=month_start,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        ),
    }

    return {
        "users": {
            "total": users_total,
            "new_7d": User.objects.filter(created_at__gte=week_ago).count(),
            "landlords": landlords_total,
            "tenants": tenants_total,
            "admins": admins_total,
        },
        "houses": {
            "total": houses_total,
            "occupied": houses_occupied,
            "recent_7d": houses_recent,
        },
        "subscriptions": {
            "breakdown": plan_breakdown,
            "active": subscriptions_active,
            "expired": subscriptions_expired,
        },
        "revenue": revenue,
    }


def users_evolution(*, period: str) -> list[dict]:
    """Nombre d'utilisateurs ajoutes par jour sur une periode.

    period: 7d, 30d, 3m ou 12m.
    """
    today = timezone.now().date()
    if period == "7d":
        days = 7
    elif period == "30d":
        days = 30
    elif period == "3m":
        days = 90
    else:
        days = 365
    start = today - timedelta(days=days - 1)
    rows = (
        User.objects.filter(date_joined__date__gte=start)
        .annotate(day=TruncDate("date_joined"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    counts = {row["day"]: row["count"] for row in rows}
    series = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        series.append({"date": day.isoformat(), "count": counts.get(day, 0)})
    return series


def revenue_series(*, period: str) -> list[dict]:
    """Revenus d'abonnement reels (transactions reussies) par periode.

    period: weekly, monthly, yearly. Le volume de transactions d'abonnement
    est faible : les buckets sont calcules en Python, sans SQL specifique.
    """
    now = timezone.now()
    if period == "weekly":
        step = timedelta(days=7)
        window = 12
        fmt = "%Y-%m-%d"
    elif period == "yearly":
        step = timedelta(days=365)
        window = 3
        fmt = "%Y"
    else:
        step = timedelta(days=30)
        window = 12
        fmt = "%Y-%m"
    start = now - step * (window - 1)
    buckets = [0] * window
    rows = (
        SubscriptionTransaction.objects.filter(
            status=SubscriptionTransaction.Status.SUCCESSFUL,
            currency=settings.SUBSCRIPTION_CURRENCY,
            completed_at__gte=start,
        ).values_list("completed_at", "amount")
    )
    for completed_at, amount in rows:
        if completed_at is None:
            continue
        index = int((completed_at - start) / step)
        if 0 <= index < window:
            buckets[index] += amount
    return [
        {"date": (start + step * index).strftime(fmt), "total": buckets[index]}
        for index in range(window)
    ]


def houses_evolution(*, period: str) -> list[dict]:
    """Maisons ajoutees par jour sur une periode."""
    today = timezone.now().date()
    days = {"7d": 7, "30d": 30, "3m": 90}.get(period, 365)
    start = today - timedelta(days=days - 1)
    rows = (
        Property.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    counts = {row["day"]: row["count"] for row in rows}
    series = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        series.append({"date": day.isoformat(), "count": counts.get(day, 0)})
    return series


def set_user_active_status(*, user, is_active: bool, admin, request=None) -> None:
    """Suspend ou reactive un compte. La suspension bloque les connexions
    futures et invalide les sessions existantes. Aucune donnee n'est supprimee."""
    if user.id == admin.id:
        raise ValidationError(_("Vous ne pouvez pas suspendre votre propre compte."))
    if user.is_active == is_active:
        raise ValidationError(
            _("Ce compte est deja %s.")
            % (_("actif") if is_active else _("suspendu"))
        )
    with transaction.atomic():
        user.is_active = is_active
        user.save(update_fields=["is_active", "updated_at"])
        if not is_active:
            for session in Session.objects.all():
                try:
                    if session.get_decoded().get("_auth_user_id") == str(user.id):
                        session.delete()
                except Exception:
                    continue
        action = (
            AuditLog.Action.USER_REACTIVATED
            if is_active
            else AuditLog.Action.USER_SUSPENDED
        )
        log_admin_action(
            admin=admin,
            action=action,
            target_type="user",
            target_id=str(user.id),
            metadata={"phone": user.phone, "is_active": is_active},
            request=request,
        )


def change_plan(*, subscription: Subscription, plan_slug: str, admin, request=None) -> Subscription:
    """Change manuellement le plan d'un abonnement et reinitialise son cycle."""
    plan = SubscriptionPlan.objects.filter(slug=plan_slug, is_active=True).first()
    if plan is None:
        raise ValidationError(_("Ce plan n'existe pas ou n'est plus disponible."))
    previous_slug = subscription.plan.slug
    with transaction.atomic():
        subscription.plan = plan
        subscription.status = Subscription.Status.ACTIVE
        subscription.started_at = timezone.now()
        subscription.expires_at = timezone.now() + timedelta(
            days=settings.SUBSCRIPTION_DURATION_DAYS
        )
        subscription.save()
        log_admin_action(
            admin=admin,
            action=AuditLog.Action.SUBSCRIPTION_CHANGED,
            target_type="subscription",
            target_id=str(subscription.id),
            metadata={
                "user": str(subscription.user.id),
                "plan_from": previous_slug,
                "plan_to": plan_slug,
            },
            request=request,
        )
    return subscription


def extend_subscription(*, subscription: Subscription, days: int, admin, request=None) -> Subscription:
    """Prolonge un abonnement de `days` jours a partir de la date d'expiration."""
    if days <= 0:
        raise ValidationError(_("Le nombre de jours doit etre positif."))
    now = timezone.now()
    base = subscription.expires_at if subscription.expires_at and subscription.expires_at > now else now
    with transaction.atomic():
        subscription.status = Subscription.Status.ACTIVE
        subscription.expires_at = base + timedelta(days=days)
        if subscription.started_at is None:
            subscription.started_at = now
        subscription.save()
        log_admin_action(
            admin=admin,
            action=AuditLog.Action.SUBSCRIPTION_EXTENDED,
            target_type="subscription",
            target_id=str(subscription.id),
            metadata={
                "user": str(subscription.user.id),
                "days": days,
                "expires_at": subscription.expires_at.isoformat(),
            },
            request=request,
        )
    return subscription


def activate_subscription(*, subscription: Subscription, plan_slug: str | None = None, days: int | None = None, admin, request=None) -> Subscription:
    """Active exceptionnellement un abonnement, avec un plan et une duree optionnels."""
    plan = subscription.plan
    if plan_slug:
        plan = SubscriptionPlan.objects.filter(slug=plan_slug, is_active=True).first()
        if plan is None:
            raise ValidationError(_("Ce plan n'existe pas ou n'est plus disponible."))
    duration = days or settings.SUBSCRIPTION_DURATION_DAYS
    if duration <= 0:
        raise ValidationError(_("La duree doit etre positive."))
    with transaction.atomic():
        subscription.plan = plan
        subscription.status = Subscription.Status.ACTIVE
        subscription.started_at = timezone.now()
        subscription.expires_at = timezone.now() + timedelta(days=duration)
        subscription.save()
        log_admin_action(
            admin=admin,
            action=AuditLog.Action.SUBSCRIPTION_ACTIVATED,
            target_type="subscription",
            target_id=str(subscription.id),
            metadata={
                "user": str(subscription.user.id),
                "plan": plan.slug,
                "days": duration,
            },
            request=request,
        )
    return subscription


def cancel_subscription(*, subscription: Subscription, admin, request=None) -> Subscription:
    """Annule un abonnement (le plan Gratuit ne peut pas etre annule)."""
    from modules.subscriptions.services import cancel_subscription as cancel_user_subscription

    with transaction.atomic():
        cancel_user_subscription(subscription.user)
        log_admin_action(
            admin=admin,
            action=AuditLog.Action.SUBSCRIPTION_CANCELLED,
            target_type="subscription",
            target_id=str(subscription.id),
            metadata={"user": str(subscription.user.id)},
            request=request,
        )
    subscription.refresh_from_db()
    return subscription
