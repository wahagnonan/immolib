from django.contrib import admin

from .models import WhatsAppInboundMessage, WhatsAppMessageStatus


@admin.register(WhatsAppInboundMessage)
class WhatsAppInboundMessageAdmin(admin.ModelAdmin):
    list_display = (
        "wa_id",
        "profile_name",
        "message_type",
        "body",
        "sent_at",
        "processed",
    )
    list_filter = ("message_type", "processed", "from_me", "sent_at")
    search_fields = ("wa_id", "profile_name", "body", "message_id")
    readonly_fields = (
        "message_id",
        "wa_id",
        "profile_name",
        "message_type",
        "body",
        "media_id",
        "from_me",
        "sent_at",
        "raw_payload",
        "processed",
        "received_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(WhatsAppMessageStatus)
class WhatsAppMessageStatusAdmin(admin.ModelAdmin):
    list_display = ("message_id", "status", "status_timestamp", "received_at")
    list_filter = ("status", "received_at")
    search_fields = ("message_id",)
    readonly_fields = (
        "message_id",
        "status",
        "status_timestamp",
        "errors",
        "raw_payload",
        "received_at",
    )

    def has_add_permission(self, request):
        return False
