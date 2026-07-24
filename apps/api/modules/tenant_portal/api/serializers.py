from rest_framework import serializers

from modules.leases.models import Lease, Tenant


class TenantPortalProfileSerializer(serializers.ModelSerializer):
    house = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = (
            "id",
            "full_name",
            "phone",
            "email",
            "status",
            "house",
            "owner",
        )

    def get_house(self, obj: Tenant) -> dict:
        return {
            "id": str(obj.property_id),
            "name": obj.property.name,
            "address": obj.property.address,
            "commune": obj.property.commune,
            "city": obj.property.city,
        }

    def get_owner(self, obj: Tenant) -> dict | None:
        ownerships = getattr(
            obj.property,
            "primary_ownership_entries",
            (),
        )
        ownership = next(iter(ownerships), None)
        if ownership is None:
            return None
        owner = ownership.user
        return {
            "id": str(owner.id),
            "full_name": owner.get_full_name() or owner.phone,
            "phone": owner.phone,
        }


class TenantPortalLeaseSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(read_only=True)
    tenant_name = serializers.CharField(source="tenant.full_name", read_only=True)
    house = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Lease
        fields = (
            "id",
            "tenant_id",
            "tenant_name",
            "house",
            "status",
            "status_label",
            "start_date",
            "end_date",
            "monthly_rent",
            "monthly_charges",
            "due_day",
            "security_deposit",
            "rent_advance",
            "currency",
            "accepts_mobile_money",
            "accepts_cash",
            "activated_at",
            "ended_at",
        )

    def get_house(self, obj: Lease) -> dict:
        return {
            "id": str(obj.property_id),
            "name": obj.property.name,
            "address": obj.property.address,
            "commune": obj.property.commune,
            "city": obj.property.city,
        }


class TenantPaymentDisputeSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=2000)
