from django.db.models import QuerySet

from modules.accounts.models import User

from .models import RentCharge


def visible_rent_charges_for(user: User) -> QuerySet[RentCharge]:
    return RentCharge.objects.filter(
        lease__property__ownerships__user=user,
        charge_type=RentCharge.Type.RENT,
    ).distinct()


def visible_obligations_for(user: User) -> QuerySet[RentCharge]:
    return RentCharge.objects.filter(lease__property__ownerships__user=user).distinct()
