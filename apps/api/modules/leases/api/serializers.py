from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from modules.accounts.phones import normalize_e164

from ..models import (
    Lease,
    Tenant,
    TenantInvitation,
    TenantInvitationShareEvent,
)
from ..services import tenant_invitation_url


class TenantSerializer(serializers.ModelSerializer):
    house_id = serializers.UUIDField(source="property_id", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    has_account = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = (
            "id",
            "house_id",
            "full_name",
            "phone",
            "email",
            "status",
            "status_label",
            "has_account",
            "created_at",
            "updated_at",
        )

    def get_has_account(self, obj: Tenant) -> bool:
        return obj.linked_user_id is not None


class CreateTenantSerializer(serializers.Serializer):
    house_id = serializers.UUIDField()
    full_name = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(allow_blank=True, required=False)

    def validate_phone(self, value: str) -> str:
        try:
            return normalize_e164(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                "Utilisez le format international, par exemple +2250700000000."
            ) from exc


class TenantInvitationSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(read_only=True)
    tenant_name = serializers.CharField(source="tenant.full_name", read_only=True)
    house_id = serializers.UUIDField(source="tenant.property_id", read_only=True)
    house_name = serializers.CharField(source="tenant.property.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    secure_url = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)
    claimed_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    accepted_by_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = TenantInvitation
        fields = (
            "id",
            "tenant_id",
            "tenant_name",
            "house_id",
            "house_name",
            "status",
            "status_label",
            "secure_url",
            "is_expired",
            "claimed_by_id",
            "accepted_by_id",
            "expires_at",
            "claimed_at",
            "accepted_at",
            "revoked_at",
            "created_at",
            "updated_at",
        )

    def get_secure_url(self, obj) -> str:
        return tenant_invitation_url(obj)


class CreateTenantInvitationSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()


class ShareTenantInvitationSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(
        choices=(
            ("EMAIL_AUTOMATIC", "Email automatique Amazon SES"),
            *TenantInvitationShareEvent.Channel.choices,
        )
    )


class InvitationTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=2048)


class PublicTenantInvitationSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.full_name", read_only=True)
    phone = serializers.CharField(source="tenant.phone", read_only=True)
    email = serializers.EmailField(source="tenant.email", read_only=True)
    house_name = serializers.CharField(source="tenant.property.name", read_only=True)
    house_address = serializers.CharField(
        source="tenant.property.address", read_only=True
    )
    owner_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = TenantInvitation
        fields = (
            "tenant_name",
            "phone",
            "email",
            "house_name",
            "house_address",
            "owner_name",
            "status",
            "status_label",
            "is_expired",
            "expires_at",
        )

    def get_owner_name(self, obj) -> str:
        return obj.invited_by.get_full_name() or obj.invited_by.phone


class LeaseSerializer(serializers.ModelSerializer):
    house_id = serializers.UUIDField(source="property_id", read_only=True)
    tenant = TenantSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Lease
        fields = (
            "id",
            "house_id",
            "tenant",
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
            "created_at",
            "updated_at",
        )


class CreateLeaseSerializer(serializers.Serializer):
    house_id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    monthly_rent = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    monthly_charges = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False
    )
    due_day = serializers.IntegerField(min_value=1, max_value=28)
    security_deposit = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False
    )
    rent_advance = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False
    )
    accepts_mobile_money = serializers.BooleanField(required=False)
    accepts_cash = serializers.BooleanField(required=False)

    def validate(self, attrs):
        end_date = attrs.get("end_date")
        if end_date and end_date < attrs["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "La date de fin doit suivre la date de debut."}
            )
        if not attrs.get("accepts_mobile_money", True) and not attrs.get(
            "accepts_cash", True
        ):
            raise serializers.ValidationError(
                "Au moins un moyen de paiement doit etre accepte."
            )
        return attrs
