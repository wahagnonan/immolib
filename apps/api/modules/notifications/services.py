from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from modules.leases.models import Tenant

from .models import NotificationPreference, PushSubscription


CHANNEL_PRIORITY = ("PUSH", "EMAIL", "WHATSAPP", "SMS")


@dataclass(frozen=True)
class NotificationRoute:
    channel: str
    destination: str


def preference_for(user) -> NotificationPreference:
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    return preference


def available_routes_for_user(user) -> tuple[NotificationRoute, ...]:
    preference = preference_for(user)
    routes: list[NotificationRoute] = []

    if preference.push_enabled:
        subscription = (
            user.push_subscriptions.filter(is_active=True)
            .order_by("-last_seen_at")
            .first()
        )
        if subscription:
            routes.append(NotificationRoute("PUSH", subscription.token))

    if (
        preference.email_enabled
        and user.email
        and user.email_verified_at is not None
    ):
        routes.append(NotificationRoute("EMAIL", user.email))

    if (
        preference.whatsapp_enabled
        and preference.whatsapp_opted_in_at is not None
        and user.phone
    ):
        routes.append(NotificationRoute("WHATSAPP", user.phone))

    if preference.sms_enabled and user.phone:
        routes.append(NotificationRoute("SMS", user.phone))

    if preference.preferred_channel != NotificationPreference.PreferredChannel.AUTO:
        preferred = next(
            (
                route
                for route in routes
                if route.channel == preference.preferred_channel
            ),
            None,
        )
        if preferred:
            routes.remove(preferred)
            routes.insert(0, preferred)
    return tuple(routes)


def preferred_route_for_tenant(tenant: Tenant) -> NotificationRoute | None:
    if tenant.linked_user_id:
        routes = available_routes_for_user(tenant.linked_user)
        if routes:
            return routes[0]

    # Un locataire sans compte ne peut pas recevoir de push et n'a pas encore
    # donné d'opt-in WhatsApp à ImmoLib. L'email fourni par le bailleur reste le
    # seul canal automatique sans coût télécom.
    if tenant.email:
        return NotificationRoute("EMAIL", tenant.email)
    return None


@transaction.atomic
def register_push_subscription(
    *, user, token: str, device_name: str = ""
) -> PushSubscription:
    now = timezone.now()
    subscription, _ = PushSubscription.objects.update_or_create(
        token=token.strip(),
        defaults={
            "user": user,
            "device_name": device_name.strip()[:100],
            "is_active": True,
            "last_seen_at": now,
        },
    )
    preference = preference_for(user)
    if not preference.push_enabled:
        preference.push_enabled = True
        preference.save(update_fields=["push_enabled", "updated_at"])
    return subscription


def deactivate_push_subscription(*, user, token: str) -> int:
    return PushSubscription.objects.filter(
        user=user, token=token.strip(), is_active=True
    ).update(is_active=False, updated_at=timezone.now())
