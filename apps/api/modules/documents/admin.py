from django.contrib import admin

from .models import (
    DocumentAccessLink,
    NotificationDelivery,
    ManualShareEvent,
    OtpChallenge,
    RentalDocument,
)


@admin.register(RentalDocument)
class RentalDocumentAdmin(admin.ModelAdmin):
    list_display = ("reference", "document_type", "amount", "currency", "status", "issued_at")
    list_filter = ("document_type", "status", "currency")
    search_fields = ("reference", "tenant_name", "tenant_phone", "house_name")
    readonly_fields = [field.name for field in RentalDocument._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(DocumentAccessLink)
class DocumentAccessLinkAdmin(admin.ModelAdmin):
    list_display = ("document", "created_by", "expires_at", "revoked_at", "created_at")
    readonly_fields = [field.name for field in DocumentAccessLink._meta.fields]


@admin.register(OtpChallenge)
class OtpChallengeAdmin(admin.ModelAdmin):
    list_display = ("access_link", "channel", "destination", "attempts", "verified_at", "expires_at")
    readonly_fields = [field.name for field in OtpChallenge._meta.fields]


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "channel",
        "destination",
        "account_challenge",
        "rent_charge",
        "tenant_invitation",
        "scheduled_for",
        "status",
        "attempt_count",
        "next_attempt_at",
        "sent_at",
    )
    list_filter = ("kind", "channel", "status")
    search_fields = (
        "destination",
        "provider_reference",
        "rent_charge__lease__tenant__full_name",
        "rent_charge__lease__property__name",
        "tenant_invitation__tenant__full_name",
    )
    readonly_fields = [field.name for field in NotificationDelivery._meta.fields]


@admin.register(ManualShareEvent)
class ManualShareEventAdmin(admin.ModelAdmin):
    list_display = ("document", "channel", "actor", "created_at")
    list_filter = ("channel", "created_at")
    search_fields = (
        "document__reference",
        "document__tenant_name",
        "actor__phone",
    )
    readonly_fields = [field.name for field in ManualShareEvent._meta.fields]
