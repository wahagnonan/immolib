from datetime import date
from decimal import Decimal

from django.db.models import Case, DecimalField, IntegerField, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.payments.api.serializers import PaymentSerializer
from modules.payments.selectors import visible_payments_for
from modules.properties.models import Property

from ..models import RentCharge
from ..selectors import visible_rent_charges_for
from .serializers import RentChargeSerializer


MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def _shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _money(value) -> str:
    return str(value or Decimal("0"))


class DashboardOverviewView(APIView):
    """Synthèse agrégée, sans charger tout l'historique dans le navigateur."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        period = timezone.localdate().replace(day=1)
        houses = Property.objects.filter(ownerships__user=request.user).distinct()
        current_charges = visible_rent_charges_for(request.user).filter(
            period_start=period,
        ).exclude(status=RentCharge.Status.CANCELLED)
        totals = current_charges.aggregate(
            expected=Coalesce(Sum("amount_due"), Value(Decimal("0")), output_field=MONEY_FIELD),
            collected=Coalesce(Sum("amount_paid"), Value(Decimal("0")), output_field=MONEY_FIELD),
        )
        expected = totals["expected"]
        collected = totals["collected"]
        remaining = expected - collected
        attention_statuses = (
            RentCharge.Status.PARTIALLY_PAID,
            RentCharge.Status.DUE,
            RentCharge.Status.OVERDUE,
            RentCharge.Status.DISPUTED,
        )

        priority = Case(
            When(status=RentCharge.Status.OVERDUE, then=Value(0)),
            When(status=RentCharge.Status.DISPUTED, then=Value(1)),
            When(status=RentCharge.Status.PARTIALLY_PAID, then=Value(2)),
            When(status=RentCharge.Status.DUE, then=Value(3)),
            When(status=RentCharge.Status.UPCOMING, then=Value(4)),
            default=Value(5),
            output_field=IntegerField(),
        )
        priority_charges = list(
            current_charges.select_related("lease__property", "lease__tenant")
            .annotate(priority=priority)
            .order_by("priority", "due_date")[:5]
        )
        recent_payments = list(
            visible_payments_for(request.user)
            .prefetch_related(
                "allocations__rent_charge__lease__property",
                "allocations__rent_charge__lease__tenant",
                "events",
            )
            .order_by("-received_at")[:5]
        )

        range_start = _shift_month(period, -5)
        monthly_rows = {
            row["period_start"]: row
            for row in visible_rent_charges_for(request.user)
            .filter(period_start__gte=range_start, period_start__lte=period)
            .exclude(status=RentCharge.Status.CANCELLED)
            .values("period_start")
            .annotate(
                expected=Coalesce(
                    Sum("amount_due"),
                    Value(Decimal("0")),
                    output_field=MONEY_FIELD,
                ),
                collected=Coalesce(
                    Sum("amount_paid"),
                    Value(Decimal("0")),
                    output_field=MONEY_FIELD,
                ),
            )
        }
        monthly_collection = []
        for offset in range(-5, 1):
            month = _shift_month(period, offset)
            row = monthly_rows.get(month, {})
            monthly_collection.append(
                {
                    "period": month.strftime("%Y-%m"),
                    "expected": _money(row.get("expected")),
                    "collected": _money(row.get("collected")),
                }
            )

        return Response(
            {
                "period": period.strftime("%Y-%m"),
                "currency": "XOF",
                "houses": {
                    "total": houses.count(),
                    "occupied": houses.filter(
                        status=Property.Status.OCCUPIED
                    ).count(),
                    "vacant": houses.filter(status=Property.Status.VACANT).count(),
                },
                "collection": {
                    "expected": _money(expected),
                    "collected": _money(collected),
                    "remaining": _money(remaining),
                    "rate": (
                        min(100, round(float(collected / expected) * 100))
                        if expected
                        else 0
                    ),
                    "attention_count": current_charges.filter(
                        status__in=attention_statuses
                    ).count(),
                },
                "priority_charges": RentChargeSerializer(
                    priority_charges,
                    many=True,
                ).data,
                "recent_payments": PaymentSerializer(
                    recent_payments,
                    many=True,
                ).data,
                "monthly_collection": monthly_collection,
            }
        )
