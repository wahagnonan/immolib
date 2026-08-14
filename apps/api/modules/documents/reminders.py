from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import F
from django.utils.translation import gettext_lazy as _

from modules.billing.models import RentCharge
from modules.i18n.utils import resolve_language
from modules.notifications.services import preferred_route_for_tenant
from modules.properties.models import Ownership
from modules.subscriptions.services import has_feature

from .models import NotificationDelivery


@dataclass(frozen=True)
class ReminderQueueSummary:
    eligible_charges: int
    created: int
    existing: int
    skipped_destinations: int


def _destination_for_reminder(charge: RentCharge, channel: str) -> str | None:
    tenant = charge.lease.tenant
    if channel == NotificationDelivery.Channel.EMAIL:
        return tenant.email or None
    if channel in (
        NotificationDelivery.Channel.SMS,
        NotificationDelivery.Channel.WHATSAPP,
    ):
        return tenant.phone
    if channel == NotificationDelivery.Channel.PUSH:
        if not tenant.linked_user_id:
            return None
        route = preferred_route_for_tenant(tenant)
        return route.destination if route and route.channel == channel else None
    raise ImproperlyConfigured(f"Canal de rappel inconnu : {channel}.")


@transaction.atomic
def queue_rent_reminders(
    *,
    today: date,
    offsets: tuple[int, ...] | None = None,
    channels: tuple[str, ...] | None = None,
) -> ReminderQueueSummary:
    """Crée les rappels du jour sans dupliquer un planning déjà exécuté."""

    configured_offsets = tuple(
        dict.fromkeys(
            settings.RENT_REMINDER_OFFSETS_DAYS if offsets is None else offsets
        )
    )
    configured_channels = tuple(
        dict.fromkeys(settings.RENT_REMINDER_CHANNELS if channels is None else channels)
    )
    valid_channels = {*NotificationDelivery.Channel.values, "AUTO"}
    unknown_channels = set(configured_channels) - valid_channels
    if unknown_channels:
        raise ImproperlyConfigured(
            _("Canaux de rappel invalides : ") + ", ".join(sorted(unknown_channels))
        )
    if not configured_offsets or not configured_channels:
        return ReminderQueueSummary(0, 0, 0, 0)

    due_dates = [today - timedelta(days=offset) for offset in configured_offsets]
    charges = list(
        RentCharge.objects.filter(
            due_date__in=due_dates,
            amount_paid__lt=F("amount_due"),
        )
        .exclude(
            status__in=(
                RentCharge.Status.PAID,
                RentCharge.Status.DISPUTED,
                RentCharge.Status.CANCELLED,
            )
        )
        .select_related("lease__tenant", "lease__property")
    )
    property_ids = {charge.lease.property_id for charge in charges}
    primary_owners = Ownership.objects.filter(
        property_id__in=property_ids,
        role=Ownership.Role.PRIMARY,
    ).select_related("user")
    allowed_property_ids = {
        ownership.property_id
        for ownership in primary_owners
        if has_feature(ownership.user, "payment_reminders")
    }
    charges = [
        charge
        for charge in charges
        if charge.lease.property_id in allowed_property_ids
    ]
    created = existing = skipped = 0
    for charge in charges:
        selected_channels = [item for item in configured_channels if item != "AUTO"]
        automatic_route = None
        if "AUTO" in configured_channels:
            automatic_route = preferred_route_for_tenant(charge.lease.tenant)
            if (
                automatic_route
                and automatic_route.channel not in selected_channels
            ):
                selected_channels.insert(0, automatic_route.channel)
        for channel in selected_channels:
            if automatic_route and channel == automatic_route.channel:
                destination = automatic_route.destination
            else:
                destination = _destination_for_reminder(charge, channel)
            if not destination:
                skipped += 1
                continue
            _, was_created = NotificationDelivery.objects.get_or_create(
                rent_charge=charge,
                kind=NotificationDelivery.Kind.RENT_REMINDER,
                channel=channel,
                scheduled_for=today,
                defaults={
                    "destination": destination,
                    "language": resolve_language(
                        user=charge.lease.tenant.linked_user
                    ),
                },
            )
            if was_created:
                created += 1
            else:
                existing += 1

    return ReminderQueueSummary(
        eligible_charges=len(charges),
        created=created,
        existing=existing,
        skipped_destinations=skipped,
    )
