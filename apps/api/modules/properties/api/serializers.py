from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from modules.accounts.models import User
from modules.accounts.phones import normalize_e164

from ..models import CoOwnerInvitation, Ownership, Property


class OwnerSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "phone", "full_name")

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()


class OwnershipSerializer(serializers.ModelSerializer):
    user = OwnerSummarySerializer(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    access_level_label = serializers.CharField(
        source="get_access_level_display", read_only=True
    )

    class Meta:
        model = Ownership
        fields = (
            "id",
            "user",
            "role",
            "role_label",
            "access_level",
            "access_level_label",
            "ownership_percentage",
        )


class HouseSerializer(serializers.ModelSerializer):
    ownerships = OwnershipSerializer(many=True, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Property
        fields = (
            "id",
            "name",
            "address",
            "commune",
            "city",
            "landmark",
            "status",
            "status_label",
            "ownerships",
            "created_at",
            "updated_at",
        )


class CreateHouseSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    address = serializers.CharField(max_length=255)
    commune = serializers.CharField(max_length=120, allow_blank=True, required=False)
    city = serializers.CharField(max_length=120)
    landmark = serializers.CharField(max_length=255, allow_blank=True, required=False)


class CoOwnerSerializer(serializers.ModelSerializer):
    house_id = serializers.UUIDField(source="property_id", read_only=True)
    house_name = serializers.CharField(source="property.name", read_only=True)
    user = OwnerSummarySerializer(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    access_level_label = serializers.CharField(
        source="get_access_level_display", read_only=True
    )

    class Meta:
        model = Ownership
        fields = (
            "id",
            "house_id",
            "house_name",
            "user",
            "role",
            "role_label",
            "access_level",
            "access_level_label",
            "ownership_percentage",
            "created_at",
        )


class UpdateCoOwnerSerializer(serializers.Serializer):
    access_level = serializers.ChoiceField(
        choices=Ownership.AccessLevel.choices, required=False
    )
    ownership_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("99.99"),
        allow_null=True,
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Indique au moins une modification.")
        return attrs


class CoOwnerInvitationSerializer(serializers.ModelSerializer):
    house_id = serializers.UUIDField(source="property_id", read_only=True)
    house_name = serializers.CharField(source="property.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    access_level_label = serializers.CharField(
        source="get_access_level_display", read_only=True
    )
    is_expired = serializers.BooleanField(read_only=True)
    invited_by = OwnerSummarySerializer(read_only=True)
    accepted_by = OwnerSummarySerializer(read_only=True)

    class Meta:
        model = CoOwnerInvitation
        fields = (
            "id",
            "house_id",
            "house_name",
            "phone",
            "email",
            "ownership_percentage",
            "access_level",
            "access_level_label",
            "status",
            "status_label",
            "is_expired",
            "invited_by",
            "accepted_by",
            "expires_at",
            "accepted_at",
            "revoked_at",
            "created_at",
            "updated_at",
        )


class CreateCoOwnerInvitationSerializer(serializers.Serializer):
    house_id = serializers.UUIDField()
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(allow_blank=True, required=False)
    ownership_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("99.99"),
        allow_null=True,
        required=False,
    )
    access_level = serializers.ChoiceField(
        choices=Ownership.AccessLevel.choices,
        required=False,
        default=Ownership.AccessLevel.OBSERVER,
    )

    def validate_phone(self, value: str) -> str:
        try:
            return normalize_e164(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                "Utilisez le format international, par exemple +2250700000000."
            ) from exc
