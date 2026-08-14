"""Serializers de l'espace admin. Aucun mot de passe, token ou donnee
sensible de paiement n'est expose."""

from rest_framework import serializers

from modules.accounts.models import User
from modules.documents.models import NotificationDelivery
from modules.leases.models import Tenant
from modules.properties.models import Property
from modules.subscriptions.models import Subscription, SubscriptionTransaction

from ..models import AuditLog


class AdminUserListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    houses_count = serializers.IntegerField(read_only=True)
    tenants_count = serializers.IntegerField(read_only=True)
    plan_slug = serializers.CharField(
        source="subscription.plan.slug", read_only=True, default=None
    )
    plan_name = serializers.CharField(
        source="subscription.plan.name", read_only=True, default=None
    )
    subscription_status = serializers.CharField(
        source="subscription.status", read_only=True, default=None
    )

    class Meta:
        model = User
        fields = (
            "id",
            "role",
            "full_name",
            "phone",
            "email",
            "is_active",
            "date_joined",
            "last_login",
            "created_at",
            "houses_count",
            "tenants_count",
            "plan_slug",
            "plan_name",
            "subscription_status",
        )


class AdminUserDetailSerializer(AdminUserListSerializer):
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    phone_verified_at = serializers.DateTimeField(read_only=True)
    email_verified_at = serializers.DateTimeField(read_only=True)

    class Meta(AdminUserListSerializer.Meta):
        fields = AdminUserListSerializer.Meta.fields + (
            "first_name",
            "last_name",
            "phone_verified_at",
            "email_verified_at",
        )


class UserStatusUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class AdminTenantSerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(
        source="property.name", read_only=True
    )
    property_id = serializers.UUIDField(source="property.id", read_only=True)
    linked_user_id = serializers.UUIDField(
        source="linked_user.id", read_only=True, default=None
    )
    linked_user_phone = serializers.CharField(
        source="linked_user.phone", read_only=True, default=None
    )

    class Meta:
        model = Tenant
        fields = (
            "id",
            "full_name",
            "phone",
            "email",
            "status",
            "property_id",
            "property_name",
            "linked_user_id",
            "linked_user_phone",
            "created_at",
        )


class AdminHouseSerializer(serializers.ModelSerializer):
    primary_owner_name = serializers.CharField(read_only=True)
    current_tenant_name = serializers.CharField(read_only=True)
    has_active_lease = serializers.BooleanField(read_only=True)
    property_type = serializers.CharField(read_only=True)

    class Meta:
        model = Property
        fields = (
            "id",
            "name",
            "address",
            "commune",
            "city",
            "status",
            "property_type",
            "primary_owner_name",
            "current_tenant_name",
            "has_active_lease",
            "created_at",
        )


class AdminSubscriptionSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_full_name = serializers.CharField(
        source="user.get_full_name", read_only=True
    )
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    plan_slug = serializers.CharField(source="plan.slug", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    price_monthly = serializers.IntegerField(
        source="plan.price_monthly", read_only=True
    )
    currency = serializers.CharField(source="plan.currency", read_only=True)
    max_houses = serializers.IntegerField(source="plan.max_houses", read_only=True)
    houses_count = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = (
            "id",
            "user_id",
            "user_full_name",
            "user_phone",
            "user_email",
            "plan_slug",
            "plan_name",
            "price_monthly",
            "currency",
            "status",
            "started_at",
            "expires_at",
            "houses_count",
            "max_houses",
            "created_at",
        )

    def get_houses_count(self, obj) -> int:
        return obj.user.ownerships.count()


class AdminSubscriptionActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=("change_plan", "extend", "activate", "cancel")
    )
    plan_slug = serializers.CharField(required=False, allow_blank=True)
    days = serializers.IntegerField(required=False, min_value=1)


class AdminPaymentSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_full_name = serializers.CharField(
        source="user.get_full_name", read_only=True
    )
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    plan_slug = serializers.CharField(source="plan.slug", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = SubscriptionTransaction
        fields = (
            "id",
            "user_id",
            "user_full_name",
            "user_phone",
            "plan_slug",
            "plan_name",
            "amount",
            "currency",
            "status",
            "provider",
            "completed_at",
            "created_at",
        )


class AdminNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = (
            "id",
            "kind",
            "channel",
            "destination",
            "status",
            "delivery_status",
            "delivered_at",
            "segments_count",
            "attempt_count",
            "last_attempt_at",
            "failure_reason",
            "scheduled_for",
            "sent_at",
            "created_at",
        )


class AdminAuditLogSerializer(serializers.ModelSerializer):
    admin_id = serializers.UUIDField(source="admin.id", read_only=True, default=None)
    admin_phone = serializers.CharField(
        source="admin.phone", read_only=True, default=None
    )
    admin_name = serializers.CharField(
        source="admin.get_full_name", read_only=True, default=None
    )
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "admin_id",
            "admin_phone",
            "admin_name",
            "action",
            "action_label",
            "target_type",
            "target_id",
            "metadata",
            "ip_address",
            "created_at",
        )
