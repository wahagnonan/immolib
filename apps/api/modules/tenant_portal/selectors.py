from django.db.models import Prefetch, QuerySet

from modules.accounts.models import User
from modules.billing.models import RentCharge
from modules.documents.models import RentalDocument
from modules.leases.models import Lease, Tenant
from modules.payments.models import Payment
from modules.properties.models import Ownership


def tenant_profiles_for(user: User) -> QuerySet[Tenant]:
    primary_ownerships = Ownership.objects.filter(
        role=Ownership.Role.PRIMARY
    ).select_related("user")
    return (
        Tenant.objects.filter(
            linked_user=user,
            status=Tenant.Status.ACTIVE,
            leases__status__in=(Lease.Status.ACTIVE, Lease.Status.ENDED),
        )
        .select_related("property")
        .prefetch_related(
            Prefetch(
                "property__ownerships",
                queryset=primary_ownerships,
                to_attr="primary_ownership_entries",
            )
        )
        .distinct()
    )


def tenant_leases_for(user: User) -> QuerySet[Lease]:
    return (
        Lease.objects.filter(
            tenant__linked_user=user,
            tenant__status=Tenant.Status.ACTIVE,
        )
        .exclude(status__in=(Lease.Status.DRAFT, Lease.Status.CANCELLED))
        .select_related("property", "tenant")
        .distinct()
    )


def tenant_rent_charges_for(user: User) -> QuerySet[RentCharge]:
    return (
        RentCharge.objects.filter(
            lease__tenant__linked_user=user,
            lease__tenant__status=Tenant.Status.ACTIVE,
            charge_type=RentCharge.Type.RENT,
        )
        .exclude(lease__status__in=(Lease.Status.DRAFT, Lease.Status.CANCELLED))
        .select_related("lease__property", "lease__tenant")
        .distinct()
    )


def tenant_payments_for(user: User) -> QuerySet[Payment]:
    return (
        Payment.objects.filter(
            allocations__rent_charge__lease__tenant__linked_user=user,
            allocations__rent_charge__lease__tenant__status=Tenant.Status.ACTIVE,
        )
        .exclude(
            allocations__rent_charge__lease__status__in=(
                Lease.Status.DRAFT,
                Lease.Status.CANCELLED,
            )
        )
        .prefetch_related(
            "allocations__rent_charge__lease__property",
            "allocations__rent_charge__lease__tenant",
            "events",
        )
        .distinct()
    )


def tenant_documents_for(user: User) -> QuerySet[RentalDocument]:
    return (
        RentalDocument.objects.filter(
            rent_charge__lease__tenant__linked_user=user,
            rent_charge__lease__tenant__status=Tenant.Status.ACTIVE,
        )
        .exclude(
            rent_charge__lease__status__in=(
                Lease.Status.DRAFT,
                Lease.Status.CANCELLED,
            )
        )
        .select_related(
            "payment",
            "rent_charge__lease__property",
            "rent_charge__lease__tenant",
        )
        .distinct()
    )
