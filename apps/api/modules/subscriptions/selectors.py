from django.db.models import QuerySet

from modules.accounts.models import User

from .models import Subscription, SubscriptionPlan, SubscriptionTransaction


def subscription_for(user: User) -> QuerySet[Subscription]:
    return Subscription.objects.filter(user=user).select_related("plan")


def active_subscription_for(user: User) -> Subscription | None:
    return subscription_for(user).filter(status=Subscription.Status.ACTIVE).first()


def transactions_for(user: User) -> QuerySet[SubscriptionTransaction]:
    return (
        SubscriptionTransaction.objects.filter(user=user)
        .select_related("plan", "subscription")
    )


def active_plans() -> QuerySet[SubscriptionPlan]:
    return SubscriptionPlan.objects.filter(is_active=True)
