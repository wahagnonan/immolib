from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.leases.models import Lease
from modules.leases.services import (
    CreateLeaseData,
    CreateTenantData,
    activate_lease,
    create_lease,
    create_tenant,
)
from modules.properties.services import CreateHouseData, create_house

from ..models import RentCharge
from ..services import (
    default_generation_period,
    generate_monthly_charges,
    generate_monthly_charges_for_all,
    month_bounds,
    refresh_temporal_statuses,
)


class RentChargeServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+2250700000300", password="password"
        )
        self.house = create_house(
            owner=self.owner,
            data=CreateHouseData(
                name="Maison Abobo",
                address="Abobo Baoule",
                city="Abidjan",
                commune="Abobo",
            ),
        )
        tenant = create_tenant(
            actor=self.owner,
            property=self.house,
            data=CreateTenantData(
                full_name="Awa Kone", phone="+2250500000300"
            ),
        )
        self.lease = create_lease(
            actor=self.owner,
            property=self.house,
            tenant=tenant,
            data=CreateLeaseData(
                start_date=date(2026, 7, 1),
                monthly_rent=Decimal("100000"),
                monthly_charges=Decimal("10000"),
                due_day=5,
            ),
        )
        activate_lease(actor=self.owner, lease=self.lease)

    def test_month_bounds_requires_first_day(self):
        with self.assertRaises(ValidationError):
            month_bounds(date(2026, 8, 2))

    def test_default_period_switches_to_next_month_on_the_25th(self):
        self.assertEqual(
            default_generation_period(date(2026, 7, 24)), date(2026, 7, 1)
        )
        self.assertEqual(
            default_generation_period(date(2026, 7, 25)), date(2026, 8, 1)
        )
        self.assertEqual(
            default_generation_period(date(2026, 12, 25)), date(2027, 1, 1)
        )

    def test_generation_snapshots_rent_and_charges(self):
        summary = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        )

        charge = summary.charges[0]
        self.assertEqual(summary.created, 1)
        self.assertEqual(charge.rent_amount, Decimal("100000"))
        self.assertEqual(charge.charges_amount, Decimal("10000"))
        self.assertEqual(charge.amount_due, Decimal("110000"))
        self.assertEqual(charge.due_date, date(2026, 8, 5))
        self.assertEqual(charge.status, RentCharge.Status.UPCOMING)

    def test_generation_is_idempotent(self):
        first = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        )
        second = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        )

        self.assertEqual(first.created, 1)
        self.assertEqual(second.created, 0)
        self.assertEqual(second.existing, 1)
        self.assertEqual(RentCharge.objects.count(), 1)

    def test_first_month_due_date_cannot_precede_lease_start(self):
        self.lease.start_date = date(2026, 7, 20)
        self.lease.save(update_fields=["start_date"])

        summary = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 7, 1),
            today=date(2026, 7, 10),
        )

        self.assertEqual(summary.charges[0].due_date, date(2026, 7, 20))

    def test_existing_charge_is_not_changed_when_lease_changes(self):
        first = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        )
        self.lease.monthly_rent = Decimal("120000")
        self.lease.save(update_fields=["monthly_rent"])

        second = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 26),
        )

        self.assertEqual(first.charges[0].amount_due, Decimal("110000"))
        self.assertEqual(second.charges[0].amount_due, Decimal("110000"))

    def test_refresh_changes_due_charge_to_overdue(self):
        charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 8, 5),
        ).charges[0]
        self.assertEqual(charge.status, RentCharge.Status.DUE)

        updated = refresh_temporal_statuses(today=date(2026, 8, 6))

        charge.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertEqual(charge.status, RentCharge.Status.OVERDUE)

    def test_partial_or_paid_status_is_not_overwritten_by_calendar(self):
        charge = generate_monthly_charges(
            actor=self.owner,
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        ).charges[0]
        charge.status = RentCharge.Status.PARTIALLY_PAID
        charge.save(update_fields=["status"])

        refresh_temporal_statuses(today=date(2026, 8, 10))

        charge.refresh_from_db()
        self.assertEqual(charge.status, RentCharge.Status.PARTIALLY_PAID)

    def test_internal_generation_entry_point_creates_all_active_leases(self):
        summary = generate_monthly_charges_for_all(
            period_start=date(2026, 8, 1),
            today=date(2026, 7, 25),
        )

        self.assertEqual(summary.created, 1)
        self.assertEqual(RentCharge.objects.count(), 1)
