from rest_framework import serializers

from ..models import Plan, Subscription, SubscriptionPayment


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
            "currency",
            "interval",
            "max_houses",
            "features",
            "is_highlighted",
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    max_houses = serializers.IntegerField(source="plan.max_houses", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "status",
            "max_houses",
            "current_period_start",
            "current_period_end",
            "created_at",
        ]


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPayment
        fields = [
            "id",
            "amount",
            "currency",
            "status",
            "payment_url",
            "paid_at",
            "created_at",
        ]


class CreatePaymentSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
