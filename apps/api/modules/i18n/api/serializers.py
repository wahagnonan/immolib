from zoneinfo import available_timezones

from rest_framework import serializers

from modules.i18n.currencies import CURRENCIES, CURRENCY_CHOICES
from modules.i18n.format import DATE_FORMAT_CHOICES, NUMBER_FORMAT_CHOICES
from modules.i18n.languages import LANGUAGE_CHOICES, is_active
from modules.i18n.timezones import timezone_choices

TIMEZONES = set(available_timezones())

#: Seules les langues actives sont acceptees par l'API.
ACTIVE_LANGUAGE_CHOICES = [
    (code, name) for code, name in LANGUAGE_CHOICES if is_active(code)
]


class AccountPreferencesSerializer(serializers.Serializer):
    """Preferences de localisation d'un compte (langue, devise, formats)."""

    preferred_language = serializers.ChoiceField(
        choices=ACTIVE_LANGUAGE_CHOICES, required=False, allow_blank=True
    )
    preferred_timezone = serializers.CharField(
        required=False, allow_blank=True, max_length=64
    )
    preferred_currency = serializers.ChoiceField(
        choices=CURRENCY_CHOICES, required=False, allow_blank=True
    )
    preferred_date_format = serializers.ChoiceField(
        choices=DATE_FORMAT_CHOICES, required=False, allow_blank=True
    )
    preferred_number_format = serializers.ChoiceField(
        choices=NUMBER_FORMAT_CHOICES, required=False, allow_blank=True
    )

    def validate_preferred_timezone(self, value: str) -> str:
        if value and value not in TIMEZONES:
            raise serializers.ValidationError(
                "Fuseau horaire inconnu, utilisez un code IANA."
            )
        return value

    def update(self, instance, validated_data):
        for field in (
            "preferred_language",
            "preferred_timezone",
            "preferred_currency",
            "preferred_date_format",
            "preferred_number_format",
        ):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save(update_fields=list(validated_data) + ["updated_at"])
        return instance


class LocalizationOptionsSerializer(serializers.Serializer):
    """Catalogues proposables a l'utilisateur pour construire ses preferences."""

    languages = serializers.SerializerMethodField()
    currencies = serializers.SerializerMethodField()
    timezones = serializers.SerializerMethodField()

    def get_languages(self, obj) -> list[dict]:
        return [
            {"code": code, "native_name": name}
            for code, name in ACTIVE_LANGUAGE_CHOICES
        ]

    def get_currencies(self, obj) -> list[dict]:
        return [
            {
                "code": code,
                "symbol": info["symbol"],
                "name": info["name"],
                "decimals": info["decimals"],
                "position": info["position"],
            }
            for code, info in CURRENCIES.items()
        ]

    def get_timezones(self, obj) -> list[str]:
        return timezone_choices()
