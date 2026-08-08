"""Formatage localise des dates, montants et nombres (backend).

Le formatage n'est jamais stocke : il est applique uniquement a la
presentation, selon la locale active et les preferences de l'utilisateur.
"""

from datetime import date, datetime

from babel.dates import format_date as babel_format_date
from babel.numbers import format_decimal

from .currencies import get_currency
from .utils import get_current_language


def _babel_locale(locale: str | None) -> str | None:
    """Babel attend ``fr_FR`` ; on accepte aussi ``fr-FR`` et ``fr``."""
    if locale is None:
        return None
    return locale.replace("-", "_")

#: (code, exemple) - formats de date proposes aux utilisateurs.
DATE_FORMAT_CHOICES = [
    ("dmy", "JJ/MM/AAAA"),
    ("mdy", "MM/JJ/AAAA"),
    ("ymd", "AAAA-MM-JJ"),
]

DATE_FORMAT_SEPARATORS = {
    "dmy": "/",
    "mdy": "/",
    "ymd": "-",
}

DEFAULT_DATE_FORMAT = "dmy"

#: (code, exemple) - conventions de nombre (separateurs).
NUMBER_FORMAT_CHOICES = [
    ("fr", "1 234 567,89"),
    ("en", "1,234,567.89"),
]

NUMBER_FORMAT_LOCALES = {
    "fr": "fr-FR",
    "en": "en-US",
}

DEFAULT_NUMBER_FORMAT = "fr"


def _resolve_locale(locale: str | None) -> str:
    return locale or get_current_language()


def format_date(value: date | datetime | str, format_code: str = DEFAULT_DATE_FORMAT,
                locale: str | None = None) -> str:
    """Formate une date selon un code nomme (dmy, mdy, ymd)."""
    if format_code not in DATE_FORMAT_SEPARATORS:
        format_code = DEFAULT_DATE_FORMAT
    separator = DATE_FORMAT_SEPARATORS[format_code]
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    elif isinstance(value, datetime):
        value = value.date()
    if format_code == "ymd":
        return value.isoformat()
    if format_code == "mdy":
        return value.strftime(f"%m{separator}%d{separator}%Y")
    return value.strftime(f"%d{separator}%m{separator}%Y")


def format_long_date(value: date | datetime | str, locale: str | None = None) -> str:
    """Date longue localisee, ex. ``5 août 2026`` en francais."""
    locale = _resolve_locale(locale)
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    elif isinstance(value, datetime):
        value = value.date()
    return babel_format_date(value, format="long", locale=_babel_locale(locale))


def format_month_name(period: str, locale: str | None = None) -> str:
    """Nom du mois localise a partir d'une periode ``AAAA-MM``."""
    locale = _resolve_locale(locale)
    year, month = (int(part) for part in period.split("-")[:2])
    return babel_format_date(
        date(year, month, 1), format="MMMM yyyy", locale=_babel_locale(locale)
    )


def format_number(value: int | float | str, number_format: str = DEFAULT_NUMBER_FORMAT,
                  locale: str | None = None) -> str:
    """Nombre avec les separateurs de la convention choisie (fr/en)."""
    locale = _resolve_locale(locale)
    if number_format not in NUMBER_FORMAT_LOCALES:
        number_format = DEFAULT_NUMBER_FORMAT
    formatted = format_decimal(value, locale=_babel_locale(locale))
    # Babel utilise l'espace fine insécable (U+202F) en francais ;
    # ImmoLib affiche un espace simple, plus lisible et attendu.
    return formatted.replace("\u202f", " ").replace("\u00a0", " ")


def format_money(value: int | float | str, currency_code: str | None = None,
                 decimals: int | None = None, number_format: str = DEFAULT_NUMBER_FORMAT,
                 locale: str | None = None) -> str:
    """Montant avec symbole, decimales et position definis par la devise.

    La devise est resolue depuis les preferences utilisateur si non fournie.
    """
    from .utils import get_current_currency

    code = currency_code or get_current_currency()
    info = get_currency(code) or {}
    decimals = decimals if decimals is not None else info.get("decimals", 2)
    position = info.get("position", "suffix")
    symbol = info.get("symbol", code)

    number = format_number(value, number_format=number_format, locale=locale)
    if position == "prefix":
        return f"{symbol} {number}".strip()
    return f"{number} {symbol}".strip()
