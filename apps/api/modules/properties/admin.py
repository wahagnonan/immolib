from django.contrib import admin

from .models import CoOwnerInvitation, Ownership, Property


class OwnershipInline(admin.TabularInline):
    model = Ownership
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "commune", "status", "created_at")
    list_filter = ("status", "city", "commune")
    search_fields = ("name", "address", "landmark")
    inlines = (OwnershipInline,)


@admin.register(Ownership)
class OwnershipAdmin(admin.ModelAdmin):
    list_display = (
        "property",
        "user",
        "role",
        "access_level",
        "ownership_percentage",
    )
    list_filter = ("role", "access_level")
    search_fields = ("property__name", "user__phone")


@admin.register(CoOwnerInvitation)
class CoOwnerInvitationAdmin(admin.ModelAdmin):
    list_display = ("phone", "property", "status", "access_level", "expires_at")
    list_filter = ("status", "access_level")
    search_fields = ("phone", "email", "property__name")
