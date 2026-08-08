"""Seed des langues, devises et pays depuis les registres statiques."""

from django.db import migrations

from modules.i18n.currencies import CURRENCIES
from modules.i18n.languages import _LANGUAGES, default_language_code
from modules.i18n.timezones import default_timezone_name

COUNTRIES = [
    # (code, nom, devise, fuseau)
    ("CI", "Côte d'Ivoire", "XOF", "Africa/Abidjan"),
    ("SN", "Sénégal", "XOF", "Africa/Dakar"),
    ("ML", "Mali", "XOF", "Africa/Bamako"),
    ("BF", "Burkina Faso", "XOF", "Africa/Ouagadougou"),
    ("BJ", "Bénin", "XOF", "Africa/Porto-Novo"),
    ("TG", "Togo", "XOF", "Africa/Lome"),
    ("NE", "Niger", "XOF", "Africa/Niamey"),
    ("CM", "Cameroun", "XAF", "Africa/Douala"),
    ("GA", "Gabon", "XAF", "Africa/Libreville"),
    ("CG", "Congo", "XAF", "Africa/Brazzaville"),
    ("CD", "RD Congo", "CDF", "Africa/Kinshasa"),
    ("FR", "France", "EUR", "Europe/Paris"),
    ("BE", "Belgique", "EUR", "Europe/Brussels"),
    ("US", "États-Unis", "USD", "America/New_York"),
    ("GB", "Royaume-Uni", "GBP", "Europe/London"),
    ("MA", "Maroc", "MAD", "Africa/Casablanca"),
    ("NG", "Nigeria", "NGN", "Africa/Lagos"),
    ("KE", "Kenya", "KES", "Africa/Nairobi"),
    ("GH", "Ghana", "GHS", "Africa/Accra"),
    ("ZA", "Afrique du Sud", "ZAR", "Africa/Johannesburg"),
]


def seed_localization(apps, schema_editor):
    Language = apps.get_model("i18n", "Language")
    Currency = apps.get_model("i18n", "Currency")
    Country = apps.get_model("i18n", "Country")

    default_code = default_language_code()
    for index, (code, native_name, active, rtl) in enumerate(_LANGUAGES):
        Language.objects.get_or_create(
            code=code,
            defaults={
                "native_name": native_name,
                "is_active": active,
                "is_default": code == default_code,
                "is_rtl": rtl,
                "order": index,
            },
        )

    for index, (code, info) in enumerate(CURRENCIES.items()):
        Currency.objects.get_or_create(
            code=code,
            defaults={
                "name": info["name"],
                "symbol": info["symbol"],
                "decimals": info["decimals"],
                "symbol_position": info["position"],
                "is_active": True,
                "order": index,
            },
        )

    default_timezone = default_timezone_name()
    for index, (code, name, currency_code, timezone) in enumerate(COUNTRIES):
        currency = Currency.objects.filter(code=currency_code).first()
        if currency is None:
            continue
        Country.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "currency": currency,
                "default_timezone": timezone or default_timezone,
                "is_active": True,
                "order": index,
            },
        )


def unseed_localization(apps, schema_editor):
    apps.get_model("i18n", "Country").objects.all().delete()
    apps.get_model("i18n", "Currency").objects.all().delete()
    apps.get_model("i18n", "Language").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("i18n", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_localization, unseed_localization),
    ]
