from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AccountOtpChallenge, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("phone",)
    list_display = ("phone", "first_name", "last_name", "is_active", "is_staff")
    search_fields = ("phone", "first_name", "last_name", "email")
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Identite", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                    "phone_verified_at",
                    "email_verified_at",
                )
            },
        ),
    )


@admin.register(AccountOtpChallenge)
class AccountOtpChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "purpose",
        "channel",
        "destination",
        "attempts",
        "expires_at",
        "verified_at",
        "consumed_at",
    )
    list_filter = ("purpose", "channel")
    search_fields = ("user__phone", "destination")
    readonly_fields = [field.name for field in AccountOtpChallenge._meta.fields]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("phone", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )
