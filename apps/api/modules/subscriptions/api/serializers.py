"""API d'abonnement."""

from rest_framework import serializers

from ..models import Subscription, SubscriptionPlan, SubscriptionTransaction


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = (
            "id",
            "slug",
            "name",
            "description",
            "price_monthly",
            "currency",
            "max_houses",
            "features",
            "is_active",
        )


class SubscriptionTransactionSerializer(serializers.ModelSerializer):
    plan_slug = serializers.CharField(source="plan.slug", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SubscriptionTransaction
        fields = (
            "id",
            "plan_slug",
            "plan_name",
            "amount",
            "currency",
            "status",
            "status_label",
            "provider",
            "provider_reference",
            "completed_at",
            "created_at",
        )


class SubscriptionDetailSerializer(serializers.Serializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    status = serializers.CharField()
    status_label = serializers.CharField()
    started_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)
    house_count = serializers.IntegerField()
    max_houses = serializers.IntegerField()
    remaining_houses = serializers.IntegerField()
    features = serializers.ListField(child=serializers.CharField())
    pending_transaction = SubscriptionTransactionSerializer(allow_null=True)


class UpgradeSubscriptionSerializer(serializers.Serializer):
    plan_slug = serializers.SlugField(max_length=40)

    def validate_plan_slug(self, value: str) -> str:
        if value == "free":
            raise serializers.ValidationError(
                "Le plan Gratuit ne nécessite pas de souscription."
            )
        return value
