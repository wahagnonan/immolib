from django.contrib import admin

from .models import Subscription, SubscriptionPlan, SubscriptionTransaction


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "name",
        "price_monthly",
        "currency",
        "max_houses",
        "is_active",
    )
    list_filter = ("is_active", "currency")
    search_fields = ("name", "slug")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "started_at", "expires_at")
    list_filter = ("status", "plan")
    search_fields = ("user__phone", "user__email")
    autocomplete_fields = ("user",) if False else ()


@admin.register(SubscriptionTransaction)
class SubscriptionTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "amount",
        "currency",
        "status",
        "provider",
        "provider_reference",
        "completed_at",
    )
    list_filter = ("status", "provider", "plan")
    search_fields = ("user__phone", "provider_reference")
