from rest_framework import serializers

from ..models import MaintenanceEvent, MaintenanceIncident


class MaintenanceEventSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="get_event_type_display", read_only=True)
    actor_role_label = serializers.CharField(
        source="get_actor_role_display",
        read_only=True,
    )
    actor_name = serializers.SerializerMethodField()
    from_status_label = serializers.SerializerMethodField()
    to_status_label = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceEvent
        fields = (
            "id",
            "event_type",
            "event_label",
            "actor_role",
            "actor_role_label",
            "actor_name",
            "from_status",
            "from_status_label",
            "to_status",
            "to_status_label",
            "message",
            "created_at",
        )

    def get_actor_name(self, obj: MaintenanceEvent) -> str:
        return obj.actor.get_full_name() or obj.actor.phone

    def get_from_status_label(self, obj: MaintenanceEvent) -> str:
        return (
            MaintenanceIncident.Status(obj.from_status).label
            if obj.from_status
            else ""
        )

    def get_to_status_label(self, obj: MaintenanceEvent) -> str:
        return (
            MaintenanceIncident.Status(obj.to_status).label
            if obj.to_status
            else ""
        )


class MaintenanceIncidentSerializer(serializers.ModelSerializer):
    house_id = serializers.UUIDField(source="property_id", read_only=True)
    house_name = serializers.CharField(source="property.name", read_only=True)
    house_address = serializers.CharField(source="property.address", read_only=True)
    lease_id = serializers.UUIDField(read_only=True)
    tenant_id = serializers.UUIDField(read_only=True)
    tenant_name = serializers.CharField(source="tenant.full_name", read_only=True)
    category_label = serializers.CharField(
        source="get_category_display",
        read_only=True,
    )
    priority_label = serializers.CharField(
        source="get_priority_display",
        read_only=True,
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    events = MaintenanceEventSerializer(many=True, read_only=True)

    class Meta:
        model = MaintenanceIncident
        fields = (
            "id",
            "house_id",
            "house_name",
            "house_address",
            "lease_id",
            "tenant_id",
            "tenant_name",
            "title",
            "description",
            "category",
            "category_label",
            "priority",
            "priority_label",
            "status",
            "status_label",
            "occurred_at",
            "resolved_at",
            "closed_at",
            "events",
            "created_at",
            "updated_at",
        )


class CreateMaintenanceIncidentSerializer(serializers.Serializer):
    lease_id = serializers.UUIDField()
    title = serializers.CharField(max_length=160)
    description = serializers.CharField(max_length=5000)
    category = serializers.ChoiceField(choices=MaintenanceIncident.Category.choices)
    priority = serializers.ChoiceField(
        choices=MaintenanceIncident.Priority.choices,
        required=False,
    )
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)


class ChangeMaintenanceStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MaintenanceIncident.Status.choices)
    message = serializers.CharField(
        max_length=2000,
        allow_blank=True,
        required=False,
    )


class MaintenanceCommentSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=2000)


class TenantMaintenanceResponseSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("CLOSE", "REOPEN"))
    message = serializers.CharField(
        max_length=2000,
        allow_blank=True,
        required=False,
    )

    def validate(self, attrs):
        if attrs["action"] == "REOPEN" and not attrs.get("message", "").strip():
            raise serializers.ValidationError(
                {"message": "Expliquez pourquoi le problème persiste."}
            )
        return attrs
