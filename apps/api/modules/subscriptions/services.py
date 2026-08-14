"""Service d'abonnement centralisé.

Toute la logique de quota et de feature gating passe par ici :
- get_effective_plan / get_usage / can_create_house / has_feature
- upgrade / cancel / activation après paiement
- expiration (aucune suppression de données)
"""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.accounts.models import User
from modules.properties.selectors import primary_owned_properties_for

from . import paydunya
from .models import Subscription, SubscriptionPlan, SubscriptionTransaction

PLAN_ORDER = ("free", "essential", "pro")

UPGRADE_PLANS = {
    "free": "essential",
    "essential": "pro",
    "pro": None,
}


class HouseLimitReached(Exception):
    """Limite de biens du plan atteinte."""

    def __init__(
        self,
        *,
        limit: int,
        plan_name: str,
        next_plan_slug: str | None = None,
        next_plan_name: str | None = None,
        next_plan_limit: int | None = None,
    ) -> None:
        self.limit = limit
        self.plan_name = plan_name
        self.next_plan_slug = next_plan_slug
        self.next_plan_name = next_plan_name
        self.next_plan_limit = next_plan_limit
        house_word = "bien" if limit == 1 else "biens"
        message = f"Vous avez atteint la limite de {limit} {house_word} de votre forfait {plan_name}."
        if next_plan_name and next_plan_limit:
            message += (
                f" Passez à {next_plan_name} pour gérer jusqu'à {next_plan_limit} biens."
            )
        super().__init__(message)


class FeatureDenied(Exception):
    """Fonctionnalité premium non incluse dans le plan actuel."""

    def __init__(
        self,
        *,
        feature: str,
        required_plan_slug: str,
        required_plan_name: str,
        message: str | None = None,
    ) -> None:
        self.feature = feature
        self.required_plan_slug = required_plan_slug
        self.required_plan_name = required_plan_name
        super().__init__(
            message
            or _(
                "Cette fonctionnalité est disponible avec le plan {plan}."
            ).format(plan=required_plan_name)
        )


@dataclass(frozen=True)
class SubscriptionUsage:
    house_count: int
    max_houses: int
    remaining: int


@dataclass(frozen=True)
class UpgradeResult:
    transaction: SubscriptionTransaction
    redirect_url: str | None
    activated: bool


def _free_plan() -> SubscriptionPlan:
    defaults = settings.SUBSCRIPTION_PLAN_DEFAULTS["free"]
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="free",
        defaults={
            "name": defaults["name"],
            "description": defaults["description"],
            "price_monthly": defaults["price_monthly"],
            "currency": settings.SUBSCRIPTION_CURRENCY,
            "max_houses": defaults["max_houses"],
            "features": defaults["features"],
        },
    )
    return plan


def _plan_from_defaults(slug: str) -> SubscriptionPlan | None:
    defaults = settings.SUBSCRIPTION_PLAN_DEFAULTS.get(slug)
    if defaults is None:
        return None
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug=slug,
        defaults={
            "name": defaults["name"],
            "description": defaults["description"],
            "price_monthly": defaults["price_monthly"],
            "currency": settings.SUBSCRIPTION_CURRENCY,
            "max_houses": defaults["max_houses"],
            "features": defaults["features"],
        },
    )
    return plan


def _expire_lazy(subscription: Subscription) -> None:
    Subscription.objects.filter(id=subscription.id).update(
        status=Subscription.Status.EXPIRED
    )


def _is_active(subscription: Subscription) -> bool:
    if subscription.status != Subscription.Status.ACTIVE:
        return False
    if (
        subscription.expires_at is not None
        and subscription.expires_at <= timezone.now()
    ):
        _expire_lazy(subscription)
        return False
    return True


def get_effective_plan(user: User) -> SubscriptionPlan:
    """Plan réellement applicable (FREE de repli, y compris après expiration)."""
    subscription = Subscription.objects.select_related("plan").filter(user=user).first()
    if subscription is not None and _is_active(subscription):
        return subscription.plan
    return _free_plan()


def ensure_subscription(user: User) -> Subscription:
    """Garantit un abonnement (créé Gratuit si absent)."""
    subscription = Subscription.objects.select_related("plan").filter(user=user).first()
    if subscription is None:
        subscription = Subscription.objects.create(user=user, plan=_free_plan())
    return subscription


def get_usage(user: User) -> SubscriptionUsage:
    plan = get_effective_plan(user)
    house_count = primary_owned_properties_for(user).count()
    return SubscriptionUsage(
        house_count=house_count,
        max_houses=plan.max_houses,
        remaining=max(0, plan.max_houses - house_count),
    )


def can_create_house(user: User) -> bool:
    usage = get_usage(user)
    return usage.house_count < usage.max_houses


def assert_can_create_house(user: User) -> None:
    plan = get_effective_plan(user)
    house_count = primary_owned_properties_for(user).count()
    if house_count < plan.max_houses:
        return
    next_plan = UPGRADE_PLANS.get(plan.slug)
    next_plan_object = _plan_from_defaults(next_plan) if next_plan else None
    raise HouseLimitReached(
        limit=plan.max_houses,
        plan_name=plan.name,
        next_plan_slug=next_plan,
        next_plan_name=next_plan_object.name if next_plan_object else None,
        next_plan_limit=next_plan_object.max_houses if next_plan_object else None,
    )


def _plan_that_has(feature: str) -> SubscriptionPlan | None:
    for slug in PLAN_ORDER:
        plan = SubscriptionPlan.objects.filter(slug=slug, is_active=True).first()
        if plan is not None and feature in plan.features:
            return plan
        fallback = _plan_from_defaults(slug)
        if fallback is not None and feature in fallback.features:
            return fallback
    return None


def has_feature(user: User, feature: str) -> bool:
    return feature in get_effective_plan(user).features


def assert_has_feature(
    user: User, feature: str, *, message: str | None = None
) -> None:
    if has_feature(user, feature):
        return
    required = _plan_that_has(feature)
    raise FeatureDenied(
        feature=feature,
        required_plan_slug=required.slug if required else "pro",
        required_plan_name=required.name if required else "Pro",
        message=message,
    )


@transaction.atomic
def _activate_subscription(user: User, plan: SubscriptionPlan) -> Subscription:
    subscription = ensure_subscription(user)
    subscription.plan = plan
    subscription.status = Subscription.Status.ACTIVE
    subscription.started_at = timezone.now()
    subscription.expires_at = timezone.now() + timedelta(
        days=settings.SUBSCRIPTION_DURATION_DAYS
    )
    subscription.save()
    return subscription


@transaction.atomic
def upgrade(user: User, plan_slug: str) -> UpgradeResult:
    """Passe au plan demandé. Retourne l'URL PayDunya si configuré,
    sinon active immédiatement (mode pilote) avec transaction tracée."""
    plan = _plan_from_defaults(plan_slug)
    if plan is None or not plan.is_active:
        raise ValidationError(_("Ce plan n'existe pas ou n'est plus disponible."))
    if get_effective_plan(user).slug == plan.slug:
        raise ValidationError(_("Vous êtes déjà abonné à ce plan."))

    ensure_subscription(user)
    if paydunya.is_configured():
        transaction_record = SubscriptionTransaction.objects.create(
            user=user,
            plan=plan,
            amount=plan.price_monthly,
            currency=plan.currency,
            status=SubscriptionTransaction.Status.PENDING,
            provider=SubscriptionTransaction.Provider.PAYDUNYA,
        )
        callback_url = settings.PAYDUNYA_CALLBACK_URL
        return_url = f"{settings.PUBLIC_APP_URL}/abonnement?transaction={transaction_record.id}"
        cancel_url = f"{settings.PUBLIC_APP_URL}/abonnement?cancelled=1"
        token, redirect_url = paydunya.create_checkout_invoice(
            total_amount=plan.price_monthly,
            description=f"Abonnement ImmoLib {plan.name}",
            items=[(f"Abonnement {plan.name} (1 mois)", plan.price_monthly)],
            custom_data={
                "transaction_id": str(transaction_record.id),
                "plan_slug": plan.slug,
            },
            return_url=return_url,
            cancel_url=cancel_url,
            callback_url=callback_url,
        )
        SubscriptionTransaction.objects.filter(id=transaction_record.id).update(
            provider_reference=token
        )
        transaction_record.refresh_from_db()
        return UpgradeResult(
            transaction=transaction_record, redirect_url=redirect_url, activated=False
        )

    if settings.IS_PRODUCTION and not settings.SUBSCRIPTIONS_PILOT_MODE:
        raise ValidationError(
            _("Le paiement en ligne n’est pas configuré pour ce compte.")
        )

    transaction_record = SubscriptionTransaction.objects.create(
        user=user,
        plan=plan,
        amount=plan.price_monthly,
        currency=plan.currency,
        status=SubscriptionTransaction.Status.SUCCESSFUL,
        provider=SubscriptionTransaction.Provider.MANUAL,
        completed_at=timezone.now(),
    )
    _activate_subscription(user, plan)
    return UpgradeResult(
        transaction=transaction_record, redirect_url=None, activated=True
    )


@transaction.atomic
def cancel_subscription(user: User) -> Subscription:
    subscription = ensure_subscription(user)
    if subscription.plan.slug == "free":
        raise ValidationError(_("Le plan Gratuit ne peut pas être annulé."))
    if subscription.status == Subscription.Status.CANCELLED:
        raise ValidationError(_("Votre abonnement est déjà annulé."))
    subscription.status = Subscription.Status.CANCELLED
    subscription.expires_at = timezone.now()
    subscription.save()
    return subscription


def confirm_transaction(
    transaction_record: SubscriptionTransaction, *, confirmed_status: str
) -> SubscriptionTransaction:
    """Applique le résultat PayDunya à une transaction en attente."""
    if transaction_record.status != SubscriptionTransaction.Status.PENDING:
        return transaction_record
    status_map = {
        "COMPLETED": SubscriptionTransaction.Status.SUCCESSFUL,
        "CANCELLED": SubscriptionTransaction.Status.CANCELLED,
        "FAILED": SubscriptionTransaction.Status.FAILED,
        "PENDING": SubscriptionTransaction.Status.PENDING,
    }
    new_status = status_map.get(confirmed_status)
    if new_status is None or new_status == SubscriptionTransaction.Status.PENDING:
        return transaction_record
    if new_status == SubscriptionTransaction.Status.SUCCESSFUL:
        _activate_subscription(transaction_record.user, transaction_record.plan)
    SubscriptionTransaction.objects.filter(id=transaction_record.id).update(
        status=new_status,
        completed_at=(
            timezone.now()
            if new_status == SubscriptionTransaction.Status.SUCCESSFUL
            else None
        ),
    )
    transaction_record.refresh_from_db()
    return transaction_record


def refresh_transaction(transaction_record: SubscriptionTransaction) -> SubscriptionTransaction:
    """Re-confirme une transaction PayDunya auprès du fournisseur."""
    if transaction_record.status != SubscriptionTransaction.Status.PENDING:
        return transaction_record
    if transaction_record.provider != SubscriptionTransaction.Provider.PAYDUNYA:
        return transaction_record
    confirmed = paydunya.confirm_invoice(transaction_record.provider_reference)
    return confirm_transaction(transaction_record, confirmed_status=confirmed)


def handle_paydunya_ipn(*, token: str) -> SubscriptionTransaction | None:
    """Traitement d'un IPN PayDunya. La confiance repose sur la confirmation
    authentifiée du token auprès de PayDunya, jamais sur le corps seul."""
    transaction_record = (
        SubscriptionTransaction.objects.select_related("plan", "user")
        .filter(
            provider_reference=token,
            provider=SubscriptionTransaction.Provider.PAYDUNYA,
        )
        .first()
    )
    if transaction_record is None:
        return None
    if transaction_record.status == SubscriptionTransaction.Status.SUCCESSFUL:
        return transaction_record
    confirmed = paydunya.confirm_invoice(token)
    return confirm_transaction(transaction_record, confirmed_status=confirmed)


def check_subscription_expirations() -> int:
    """Expire les abonnements arrivés à terme. Aucune donnée n'est supprimée."""
    updated = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE,
        expires_at__lte=timezone.now(),
    ).update(status=Subscription.Status.EXPIRED)
    return updated


def get_subscription_summary(user: User) -> dict | None:
    """Résumé pour /auth/me/ (lecture seule, sans effet de bord)."""
    subscription = Subscription.objects.select_related("plan").filter(user=user).first()
    if subscription is None:
        return None
    plan = (
        subscription.plan
        if _is_active(subscription)
        else _free_plan()
    )
    usage = get_usage(user)
    return {
        "plan_slug": plan.slug,
        "plan_name": plan.name,
        "price_monthly": plan.price_monthly,
        "currency": plan.currency,
        "status": (
            subscription.status
            if _is_active(subscription)
            else Subscription.Status.EXPIRED
        ),
        "expires_at": subscription.expires_at,
        "house_count": usage.house_count,
        "max_houses": usage.max_houses,
        "features": plan.features,
    }
