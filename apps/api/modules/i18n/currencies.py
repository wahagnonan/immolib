"""Module devises : codes ISO, symboles, decimales, position du symbole.

Les montants sont TOUJOURS stockes en base dans leur valeur exacte ; le
formatage monetaire n'a lieu qu'a la presentation, via
``modules.i18n.format.format_currency``.
"""

from django.utils.translation import gettext_lazy as _

CurrencyEntry = dict

#: (code ISO 4217, nom, symbole, decimales, position du symbole)
_POSITION_PREFIX = "prefix"
_POSITION_SUFFIX = "suffix"

SYMBOL_POSITION_CHOICES = [
    (_POSITION_PREFIX, _("Avant le montant")),
    (_POSITION_SUFFIX, _("Après le montant")),
]

#: Registre statique des devises connues (extensible dans currencies.Currency
#: administrable). ``position`` indique ou placer le symbole, ``decimals`` le
#: nombre de decimales affichees.
CURRENCIES: dict[str, CurrencyEntry] = {
    "XOF": {
        "name": "Franc CFA (UEMOA)",
        "symbol": "FCFA",
        "decimals": 0,
        "position": _POSITION_SUFFIX,
    },
    "XAF": {
        "name": "Franc CFA (CEMAC)",
        "symbol": "FCFA",
        "decimals": 0,
        "position": _POSITION_SUFFIX,
    },
    "USD": {
        "name": "US Dollar",
        "symbol": "$",
        "decimals": 2,
        "position": _POSITION_PREFIX,
    },
    "EUR": {
        "name": "Euro",
        "symbol": "€",
        "decimals": 2,
        "position": _POSITION_SUFFIX,
    },
    "GBP": {
        "name": "British Pound",
        "symbol": "£",
        "decimals": 2,
        "position": _POSITION_PREFIX,
    },
    "MAD": {
        "name": "Moroccan Dirham",
        "symbol": "MAD",
        "decimals": 2,
        "position": _POSITION_SUFFIX,
    },
    "NGN": {
        "name": "Nigerian Naira",
        "symbol": "₦",
        "decimals": 2,
        "position": _POSITION_PREFIX,
    },
    "KES": {
        "name": "Kenyan Shilling",
        "symbol": "KES",
        "decimals": 2,
        "position": _POSITION_PREFIX,
    },
    "GHS": {
        "name": "Ghanaian Cedi",
        "symbol": "GH₵",
        "decimals": 2,
        "position": _POSITION_PREFIX,
    },
    "ZAR": {
        "name": "South African Rand",
        "symbol": "R",
        "decimals": 2,
        "position": _POSITION_PREFIX,
    },
    "CDF": {
        "name": "Congolese Franc",
        "symbol": "FC",
        "decimals": 2,
        "position": _POSITION_SUFFIX,
    },
}

CURRENCY_CODES = tuple(CURRENCIES)

#: Choices pour les champs de modele Django (preferences utilisateur).
CURRENCY_CHOICES = [(code, info["name"]) for code, info in CURRENCIES.items()]

_DEFAULT_CURRENCY_CODE = "XOF"

#: Devise utilisee par defaut lorsqu'aucune preference n'existe.
DEFAULT_CURRENCY_CODE = _DEFAULT_CURRENCY_CODE


def get_currency(code: str) -> CurrencyEntry | None:
    return CURRENCIES.get(code)


def is_supported(code: str) -> bool:
    return code in CURRENCIES


def default_currency_code() -> str:
    return _DEFAULT_CURRENCY_CODE
