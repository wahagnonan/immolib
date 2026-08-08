from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from ..phones import normalize_e164


User = get_user_model()


class CurrentUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    has_owner_access = serializers.SerializerMethodField()
    has_tenant_access = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "phone",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_verified_at",
            "email_verified_at",
            "has_verified_contact",
            "has_owner_access",
            "has_tenant_access",
            "preferred_language",
            "preferred_timezone",
            "preferred_currency",
            "preferred_date_format",
            "preferred_number_format",
            "created_at",
        )

    def get_full_name(self, obj) -> str:
        return obj.get_full_name()

    def get_has_owner_access(self, obj) -> bool:
        return obj.ownerships.exists()

    def get_has_tenant_access(self, obj) -> bool:
        return obj.tenant_profiles.filter(
            status="ACTIVE",
            leases__status__in=("ACTIVE", "ENDED"),
        ).exists()


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(
        write_only=True, trim_whitespace=False
    )
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    email = serializers.EmailField(allow_blank=True, required=False)
    tenant_invitation_token = serializers.CharField(
        max_length=2048,
        allow_blank=True,
        required=False,
        write_only=True,
    )

    def validate_phone(self, value: str) -> str:
        try:
            phone = normalize_e164(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError(
                _("Un compte utilise déjà ce numéro de téléphone.")
            )
        return phone

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError(
                {"password_confirmation": _("Les mots de passe ne correspondent pas.")}
            )
        candidate = User(
            phone=attrs["phone"],
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
            email=attrs.get("email", ""),
        )
        validate_password(attrs["password"], user=candidate)
        invitation_token = attrs.get("tenant_invitation_token", "")
        if invitation_token:
            from modules.leases.services import (
                validate_tenant_invitation_registration,
            )

            try:
                validate_tenant_invitation_registration(
                    token=invitation_token,
                    phone=attrs["phone"],
                    email=attrs.get("email", ""),
                )
            except DjangoValidationError as exc:
                if hasattr(exc, "message_dict"):
                    raise serializers.ValidationError(exc.message_dict) from exc
                raise serializers.ValidationError(
                    {"tenant_invitation_token": exc.messages}
                ) from exc
        return attrs


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_phone(self, value: str) -> str:
        try:
            return normalize_e164(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class PhoneCodeSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.RegexField(r"^\d{6}$")

    def validate_phone(self, value: str) -> str:
        try:
            return normalize_e164(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class PhoneOnlySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value: str) -> str:
        try:
            return normalize_e164(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class PasswordResetConfirmSerializer(PhoneCodeSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(
        write_only=True, trim_whitespace=False
    )

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError(
                {"password_confirmation": _("Les mots de passe ne correspondent pas.")}
            )
        candidate = User(phone=attrs["phone"])
        validate_password(attrs["password"], user=candidate)
        return attrs
