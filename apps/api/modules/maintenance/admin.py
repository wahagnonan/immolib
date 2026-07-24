from django.contrib import admin

from .models import MaintenanceEvent, MaintenanceIncident


class MaintenanceEventInline(admin.TabularInline):
    model = MaintenanceEvent
    extra = 0
    can_delete = False
    readonly_fields = (
        "event_type",
        "actor",
        "actor_role",
        "from_status",
        "to_status",
        "message",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MaintenanceIncident)
class MaintenanceIncidentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "property",
        "tenant",
        "category",
        "priority",
        "status",
        "created_at",
    )
    list_filter = ("category", "priority", "status")
    search_fields = ("title", "description", "property__name", "tenant__full_name")
    readonly_fields = (
        "property",
        "lease",
        "tenant",
        "reported_by",
        "resolved_at",
        "closed_at",
        "created_at",
        "updated_at",
    )
    inlines = (MaintenanceEventInline,)


@admin.register(MaintenanceEvent)
class MaintenanceEventAdmin(admin.ModelAdmin):
    list_display = (
        "incident",
        "event_type",
        "actor",
        "actor_role",
        "created_at",
    )
    list_filter = ("event_type", "actor_role")
    readonly_fields = (
        "incident",
        "event_type",
        "actor",
        "actor_role",
        "from_status",
        "to_status",
        "message",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
