from django.db.models import QuerySet

from modules.accounts.models import User
from modules.leases.selectors import manageable_properties_for

from .models import Payment, PaymentMethodAccount, PaymentRequest


def visible_payments_for(user: User) -> QuerySet[Payment]:
    return Payment.objects.filter(
        allocations__rent_charge__lease__property__ownerships__user=user
    ).distinct()


def payment_method_accounts_for(user: User) -> QuerySet[PaymentMethodAccount]:
    return PaymentMethodAccount.objects.filter(owner=user)


def payment_requests_for_owner(user: User) -> QuerySet[PaymentRequest]:
    manageable_ids = manageable_properties_for(user).values_list("id", flat=True)
    return PaymentRequest.objects.filter(
        rent_charge__lease__property_id__in=manageable_ids
    ).distinct()


def payment_requests_for_tenant(user: User) -> QuerySet[PaymentRequest]:
    return PaymentRequest.objects.filter(requested_by=user)
