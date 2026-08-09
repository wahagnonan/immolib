from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "admin", "target_type", "target_id", "created_at", "ip_address")
    list_filter = ("action", "created_at")
    readonly_fields = ("admin", "action", "target_type", "target_id", "metadata", "ip_address", "created_at")
    search_fields = ("admin__phone", "admin__email", "target_id")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
