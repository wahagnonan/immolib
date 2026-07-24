from django.db.models import Q, QuerySet

from modules.accounts.models import User

from .models import NotificationDelivery, RentalDocument


def visible_documents_for(user: User) -> QuerySet[RentalDocument]:
    return RentalDocument.objects.filter(
        rent_charge__lease__property__ownerships__user=user
    ).distinct()


def visible_notification_deliveries_for(
    user: User,
) -> QuerySet[NotificationDelivery]:
    return NotificationDelivery.objects.filter(
        Q(access_link__document__in=visible_documents_for(user))
        | Q(rent_charge__lease__property__ownerships__user=user)
        | Q(tenant_invitation__tenant__property__ownerships__user=user)
    ).distinct()
