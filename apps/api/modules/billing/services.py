import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

from django.core.exceptions import ValidationError
from django.db import transaction

from modules.accounts.models import User
from modules.leases.models import Lease
from modules.leases.selectors import manageable_properties_for

from .models import RentCharge


@dataclass(frozen=True)
class GenerationSummary:
    created: int
    existing: int
    charges: tuple[RentCharge, ...]


@dataclass(frozen=True)
class PreparedObligations:
    created: int
    existing: int
    obligations: tuple[RentCharge, ...]


def month_bounds(period_start: date) -> tuple[date, date]:
    if period_start.day != 1:
        raise ValidationError(_("La periode doit commencer le premier du mois."))
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    return period_start, date(period_start.year, period_start.month, last_day)


def temporal_status(*, due_date: date, today: date) -> str:
    if today < due_date:
        return RentCharge.Status.UPCOMING
    if today == due_date:
        return RentCharge.Status.DUE
    return RentCharge.Status.OVERDUE


def _lease_overlaps_period(*, lease: Lease, period_start: date, period_end: date) -> bool:
    if lease.start_date > period_end:
        return False
    if lease.end_date and lease.end_date < period_start:
        return False
    return True


def default_generation_period(today: date) -> date:
    """A partir du 25, prepare le mois suivant; sinon assure le mois courant."""

    if today.day < 25:
        return today.replace(day=1)
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


def next_month(period_start: date) -> date:
    if period_start.month == 12:
        return date(period_start.year + 1, 1, 1)
    return date(period_start.year, period_start.month + 1, 1)


def _generate_for_leases(*, leases, period_start: date, today: date) -> GenerationSummary:
    period_start, period_end = month_bounds(period_start)
    created_count = 0
    existing_count = 0
    results: list[RentCharge] = []

    for lease in leases:
        if not _lease_overlaps_period(
            lease=lease, period_start=period_start, period_end=period_end
        ):
            continue

        normal_due_date = date(period_start.year, period_start.month, lease.due_day)
        due_date = max(normal_due_date, lease.start_date)
        amount_due = lease.monthly_rent + lease.monthly_charges
        charge, created = RentCharge.objects.get_or_create(
            lease=lease,
            charge_type=RentCharge.Type.RENT,
            period_start=period_start,
            defaults={
                "period_end": period_end,
                "due_date": due_date,
                "rent_amount": lease.monthly_rent,
                "charges_amount": lease.monthly_charges,
                "amount_due": amount_due,
                "currency": lease.currency,
                "status": temporal_status(due_date=due_date, today=today),
            },
        )
        if created:
            created_count += 1
        else:
            existing_count += 1
        results.append(charge)

    return GenerationSummary(
        created=created_count,
        existing=existing_count,
        charges=tuple(results),
    )


def _assert_can_manage_lease(*, actor: User, lease: Lease) -> None:
    if not manageable_properties_for(actor).filter(id=lease.property_id).exists():
        raise ValidationError(_("Tu ne peux pas préparer un paiement pour cette maison."))


def _security_deposit_defaults(*, lease: Lease, today: date) -> dict:
    period_start, period_end = month_bounds(lease.start_date.replace(day=1))
    return {
        "period_start": period_start,
        "period_end": period_end,
        "due_date": lease.start_date,
        "rent_amount": Decimal("0"),
        "charges_amount": Decimal("0"),
        "amount_due": lease.security_deposit,
        "currency": lease.currency,
        "status": temporal_status(due_date=lease.start_date, today=today),
    }


@transaction.atomic
def ensure_security_deposit_obligation(
    *, actor: User, lease: Lease, today: date
) -> tuple[RentCharge | None, bool]:
    """Crée une seule obligation de caution pour le bail, si elle est prévue."""

    _assert_can_manage_lease(actor=actor, lease=lease)
    if lease.security_deposit <= 0:
        return None, False
    obligation, created = RentCharge.objects.get_or_create(
        lease=lease,
        charge_type=RentCharge.Type.SECURITY_DEPOSIT,
        defaults=_security_deposit_defaults(lease=lease, today=today),
    )
    return obligation, created


@transaction.atomic
def prepare_payment_obligations(
    *,
    actor: User,
    lease: Lease,
    period_start: date | None,
    period_end: date | None,
    include_security_deposit: bool,
    today: date,
) -> PreparedObligations:
    """Prépare caution et/ou loyers futurs avant leur affectation à un paiement."""

    _assert_can_manage_lease(actor=actor, lease=lease)
    if lease.status != Lease.Status.ACTIVE:
        raise ValidationError(_("Seul un bail actif peut recevoir un paiement."))
    if (period_start is None) != (period_end is None):
        raise ValidationError(_("Indique le premier et le dernier mois à payer."))
    if period_start and period_end:
        if period_start.day != 1 or period_end.day != 1:
            raise ValidationError(_("Les périodes doivent commencer le premier du mois."))
        if period_end < period_start:
            raise ValidationError(_("Le dernier mois doit suivre le premier mois."))

        cursor = period_start
        month_count = 0
        while cursor <= period_end:
            month_count += 1
            if month_count > 120:
                raise ValidationError(
                    _("Un paiement peut couvrir au maximum 120 mois par opération.")
                )
            cursor = next_month(cursor)

    created = 0
    existing = 0
    obligations: list[RentCharge] = []

    if include_security_deposit:
        deposit, was_created = ensure_security_deposit_obligation(
            actor=actor, lease=lease, today=today
        )
        if deposit is not None:
            obligations.append(deposit)
            created += int(was_created)
            existing += int(not was_created)

    if period_start and period_end:
        cursor = period_start
        while cursor <= period_end:
            summary = _generate_for_leases(
                leases=(lease,), period_start=cursor, today=today
            )
            obligations.extend(summary.charges)
            created += summary.created
            existing += summary.existing
            cursor = next_month(cursor)

    if not obligations:
        raise ValidationError(_("Sélectionne une caution ou au moins un mois de loyer."))

    return PreparedObligations(
        created=created,
        existing=existing,
        obligations=tuple(obligations),
    )


@transaction.atomic
def generate_monthly_charges(
    *, actor: User, period_start: date, today: date
) -> GenerationSummary:
    """Genere les echeances des maisons modifiables par un bailleur."""

    _, period_end = month_bounds(period_start)
    manageable_property_ids = manageable_properties_for(actor).values_list(
        "id", flat=True
    )
    leases = Lease.objects.filter(
        property_id__in=manageable_property_ids,
        status=Lease.Status.ACTIVE,
        start_date__lte=period_end,
    ).select_related("property")
    return _generate_for_leases(
        leases=leases, period_start=period_start, today=today
    )


@transaction.atomic
def generate_monthly_charges_for_all(
    *, period_start: date, today: date
) -> GenerationSummary:
    """Point d'entree interne destine au planificateur automatique."""

    _, period_end = month_bounds(period_start)
    leases = Lease.objects.filter(
        status=Lease.Status.ACTIVE,
        start_date__lte=period_end,
    ).select_related("property")
    return _generate_for_leases(
        leases=leases, period_start=period_start, today=today
    )


@transaction.atomic
def refresh_temporal_statuses(*, today: date) -> int:
    """Actualise uniquement les statuts qui dependent du calendrier."""

    charges = RentCharge.objects.filter(
        charge_type=RentCharge.Type.RENT,
        status__in=[
            RentCharge.Status.UPCOMING,
            RentCharge.Status.DUE,
            RentCharge.Status.OVERDUE,
        ]
    )
    updated = 0
    for charge in charges:
        next_status = temporal_status(due_date=charge.due_date, today=today)
        if charge.status != next_status:
            charge.status = next_status
            charge.save(update_fields=["status", "updated_at"])
            updated += 1
    return updated
