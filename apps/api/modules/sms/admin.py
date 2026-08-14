from django.contrib import admin

from .models import SmsDeliveryReceipt, SmsSendRecord


@admin.register(SmsSendRecord)
class SmsSendRecordAdmin(admin.ModelAdmin):
    list_display = (
        "provider_message_id",
        "recipient",
        "segments_count",
        "estimated_cost_xof",
        "sent_at",
    )
    list_filter = ("sent_at", "segments_count")
    search_fields = ("provider_message_id", "recipient")
    readonly_fields = (
        "delivery",
        "provider_message_id",
        "recipient",
        "segments_count",
        "estimated_cost_xof",
        "sent_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(SmsDeliveryReceipt)
class SmsDeliveryReceiptAdmin(admin.ModelAdmin):
    list_display = ("provider_message_id", "delivery_status", "address", "received_at")
    list_filter = ("delivery_status", "received_at")
    search_fields = ("provider_message_id", "address")
    readonly_fields = (
        "provider_message_id",
        "delivery_status",
        "address",
        "raw_payload",
        "received_at",
    )

    def has_add_permission(self, request):
        return False
