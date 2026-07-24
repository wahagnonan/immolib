from django.contrib import admin

from .models import (
    Payment,
    PaymentAllocation,
    PaymentEvent,
    PaymentProviderEvent,
    SecurityDepositMovement,
)


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    readonly_fields = ("rent_charge", "amount", "created_at")
    can_delete = False


class PaymentEventInline(admin.TabularInline):
    model = PaymentEvent
    extra = 0
    readonly_fields = (
        "event_type",
        "actor_user",
        "actor_tenant",
        "reason",
        "metadata",
        "created_at",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "amount",
        "currency",
        "method",
        "status",
        "is_cash_movement",
        "received_at",
        "recorded_by",
    )
    list_filter = ("method", "status", "is_cash_movement", "currency")
    search_fields = ("external_reference", "recorded_by__phone")
    readonly_fields = (
        "amount",
        "currency",
        "method",
        "status",
        "received_at",
        "external_reference",
        "note",
        "is_cash_movement",
        "idempotency_key",
        "recorded_by",
        "created_at",
        "updated_at",
    )
    inlines = (PaymentAllocationInline, PaymentEventInline)

    def has_add_permission(self, request):
        return False


@admin.register(SecurityDepositMovement)
class SecurityDepositMovementAdmin(admin.ModelAdmin):
    list_display = (
        "deposit_obligation",
        "movement_type",
        "amount",
        "occurred_at",
        "created_by",
    )
    list_filter = ("movement_type", "occurred_at")
    search_fields = (
        "deposit_obligation__lease__property__name",
        "deposit_obligation__lease__tenant__full_name",
        "agreement_reference",
    )
    readonly_fields = [
        field.name for field in SecurityDepositMovement._meta.fields
    ]

    def has_add_permission(self, request):
        return False


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ("payment", "rent_charge", "amount", "created_at")
    readonly_fields = ("payment", "rent_charge", "amount", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("payment", "event_type", "actor_user", "actor_tenant", "created_at")
    readonly_fields = (
        "payment",
        "event_type",
        "actor_user",
        "actor_tenant",
        "reason",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(PaymentProviderEvent)
class PaymentProviderEventAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "external_event_id",
        "event_type",
        "status",
        "transaction_reference",
        "received_at",
    )
    list_filter = ("provider", "status", "event_type")
    search_fields = ("external_event_id", "transaction_reference")
    readonly_fields = (
        "provider",
        "external_event_id",
        "event_type",
        "status",
        "transaction_reference",
        "rent_charge_reference",
        "amount",
        "currency",
        "paid_at",
        "payload_digest",
        "payment",
        "failure_reason",
        "received_at",
        "processed_at",
    )

    def has_add_permission(self, request):
        return False
