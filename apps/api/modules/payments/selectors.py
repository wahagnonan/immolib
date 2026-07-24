from django.db.models import QuerySet

from modules.accounts.models import User

from .models import Payment


def visible_payments_for(user: User) -> QuerySet[Payment]:
    return Payment.objects.filter(
        allocations__rent_charge__lease__property__ownerships__user=user
    ).distinct()
