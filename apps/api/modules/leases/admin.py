from django.contrib import admin

from .models import (
    Lease,
    Tenant,
    TenantInvitation,
    TenantInvitationShareEvent,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "property", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("full_name", "phone", "email", "property__name")


@admin.register(TenantInvitation)
class TenantInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "status",
        "invited_by",
        "claimed_by",
        "accepted_by",
        "expires_at",
    )
    list_filter = ("status", "expires_at")
    search_fields = (
        "tenant__full_name",
        "tenant__phone",
        "tenant__email",
        "tenant__property__name",
    )
    readonly_fields = (
        "claimed_at",
        "accepted_at",
        "revoked_at",
        "created_at",
        "updated_at",
    )


@admin.register(TenantInvitationShareEvent)
class TenantInvitationShareEventAdmin(admin.ModelAdmin):
    list_display = ("invitation", "channel", "actor", "created_at")
    list_filter = ("channel", "created_at")
    search_fields = (
        "invitation__tenant__full_name",
        "invitation__tenant__phone",
        "actor__phone",
    )
    readonly_fields = [field.name for field in TenantInvitationShareEvent._meta.fields]


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = (
        "property",
        "tenant",
        "monthly_rent",
        "due_day",
        "start_date",
        "status",
    )
    list_filter = ("status", "currency", "accepts_mobile_money", "accepts_cash")
    search_fields = ("property__name", "tenant__full_name", "tenant__phone")
