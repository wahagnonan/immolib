"""Registre des fuseaux horaires autorises.

Le fuseau est stocke sous forme de code IANA (ex. ``Africa/Abidjan``) et
valide contre ``zoneinfo.available_timezones()``.
"""

from zoneinfo import available_timezones

#: Fuseaux les plus courants du marche africain et international.
COMMON_TIMEZONES: tuple[str, ...] = (
    "Africa/Abidjan",
    "Africa/Algiers",
    "Africa/Cairo",
    "Africa/Casablanca",
    "Africa/Dakar",
    "Africa/Douala",
    "Africa/El_Aaiun",
    "Africa/Johannesburg",
    "Africa/Kinshasa",
    "Africa/Lagos",
    "Africa/Lome",
    "Africa/Luanda",
    "Africa/Lusaka",
    "Africa/Nairobi",
    "Africa/Ouagadougou",
    "Africa/Porto-Novo",
    "Africa/Tunis",
    "Europe/London",
    "Europe/Paris",
    "America/New_York",
    "America/Sao_Paulo",
)

_DEFAULT_TIMEZONE = "Africa/Abidjan"

_TIMEZONES = sorted(available_timezones())


def is_supported(name: str) -> bool:
    return name in _TIMEZONES


def timezone_choices() -> list[str]:
    """Toutes les zones IANA, fuseaux courants en premier."""
    return [zone for zone in COMMON_TIMEZONES if zone in _TIMEZONES] + [
        zone for zone in _TIMEZONES if zone not in COMMON_TIMEZONES
    ]


def default_timezone_name() -> str:
    return _DEFAULT_TIMEZONE
