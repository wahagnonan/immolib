from django.contrib import admin

from .models import NotificationPreference, PushSubscription


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "preferred_channel",
        "push_enabled",
        "email_enabled",
        "whatsapp_enabled",
        "sms_enabled",
    )
    list_filter = (
        "preferred_channel",
        "push_enabled",
        "email_enabled",
        "whatsapp_enabled",
        "sms_enabled",
    )
    search_fields = ("user__phone", "user__email")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "device_name", "is_active", "last_seen_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__phone", "user__email", "device_name")
    readonly_fields = ("token", "created_at", "updated_at", "last_seen_at")
