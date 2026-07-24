from django.utils import timezone
from rest_framework import serializers

from ..models import NotificationPreference, PushSubscription
from ..services import available_routes_for_user, preference_for


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    whatsapp_opt_in = serializers.BooleanField(write_only=True, required=False)
    available_channels = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    email_verified = serializers.SerializerMethodField()
    active_push_devices = serializers.SerializerMethodField()

    class Meta:
        model = NotificationPreference
        fields = (
            "preferred_channel",
            "push_enabled",
            "email_enabled",
            "whatsapp_enabled",
            "sms_enabled",
            "whatsapp_opt_in",
            "whatsapp_opted_in_at",
            "available_channels",
            "email",
            "email_verified",
            "active_push_devices",
            "updated_at",
        )
        read_only_fields = (
            "whatsapp_opted_in_at",
            "available_channels",
            "email",
            "email_verified",
            "active_push_devices",
            "updated_at",
        )

    def get_available_channels(self, obj) -> list[str]:
        return [route.channel for route in available_routes_for_user(obj.user)]

    def get_email_verified(self, obj) -> bool:
        return obj.user.email_verified_at is not None

    def get_active_push_devices(self, obj) -> int:
        return obj.user.push_subscriptions.filter(is_active=True).count()

    def validate(self, attrs):
        whatsapp_enabled = attrs.get(
            "whatsapp_enabled", self.instance.whatsapp_enabled
        )
        opted_in = attrs.get(
            "whatsapp_opt_in", self.instance.whatsapp_opted_in_at is not None
        )
        if whatsapp_enabled and not opted_in:
            raise serializers.ValidationError(
                {
                    "whatsapp_opt_in": (
                        "Le consentement WhatsApp est obligatoire pour activer ce canal."
                    )
                }
            )
        return attrs

    def update(self, instance, validated_data):
        opted_in = validated_data.pop("whatsapp_opt_in", None)
        if opted_in is True and instance.whatsapp_opted_in_at is None:
            instance.whatsapp_opted_in_at = timezone.now()
        elif opted_in is False:
            instance.whatsapp_opted_in_at = None
            validated_data["whatsapp_enabled"] = False
        return super().update(instance, validated_data)


class PushSubscriptionInputSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096, trim_whitespace=True)
    device_name = serializers.CharField(
        max_length=100, allow_blank=True, required=False
    )


class PushSubscriptionSerializer(serializers.ModelSerializer):
    token_suffix = serializers.SerializerMethodField()

    class Meta:
        model = PushSubscription
        fields = (
            "id",
            "platform",
            "device_name",
            "token_suffix",
            "is_active",
            "last_seen_at",
            "created_at",
        )

    def get_token_suffix(self, obj) -> str:
        return obj.token[-6:]
