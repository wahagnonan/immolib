"""Etat courant de la localisation (locale, devise) et accesseurs caches.

Le contexte est stocke dans un ``ContextVar`` rempli par le middleware :
il reste fiable hors requete HTTP (workers asynchrones, commandes) grace
aux valeurs par defaut.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.utils import translation

from .currencies import default_currency_code, is_supported as currency_supported
from .languages import default_language_code, is_active, is_supported

_current_language: ContextVar[str] = ContextVar(
    "immolib_current_language", default=default_language_code()
)
_current_currency: ContextVar[str] = ContextVar(
    "immolib_current_currency", default=default_currency_code()
)
_current_timezone: ContextVar[str] = ContextVar(
    "immolib_current_timezone", default="Africa/Abidjan"
)
_current_date_format: ContextVar[str] = ContextVar("immolib_current_date_format", default="dmy")
_current_number_format: ContextVar[str] = ContextVar("immolib_current_number_format", default="fr")


def set_locale_context(*, language: str | None = None, currency: str | None = None,
                       timezone: str | None = None, date_format: str | None = None,
                       number_format: str | None = None) -> None:
    """Applique le contexte de localisation pour la duree de la requete."""
    if language is not None and is_supported(language):
        _current_language.set(language)
    if currency is not None and currency_supported(currency):
        _current_currency.set(currency)
    if timezone is not None:
        _current_timezone.set(timezone)
    if date_format is not None:
        _current_date_format.set(date_format)
    if number_format is not None:
        _current_number_format.set(number_format)


def get_current_language() -> str:
    return _current_language.get()


def get_current_currency() -> str:
    return _current_currency.get()


def get_current_timezone() -> str:
    return _current_timezone.get()


def get_current_date_format() -> str:
    return _current_date_format.get()


def get_current_number_format() -> str:
    return _current_number_format.get()


def resolve_language(user=None, cookie_language: str | None = None,
                     browser_language: str | None = None) -> str:
    """Ordre de priorite : preference profil -> cookie -> navigateur -> defaut.

    Les langues inconnues ou inactives sont ignorees (jamais acceptees).
    """
    candidates = [
        getattr(user, "preferred_language", "") if user is not None else "",
        cookie_language or "",
        browser_language or "",
    ]
    for candidate in candidates:
        if candidate and is_active(candidate):
            return candidate
    return default_language_code()


def resolve_currency(user=None) -> str:
    preferred = getattr(user, "preferred_currency", "") if user is not None else ""
    if preferred and currency_supported(preferred):
        return preferred
    return default_currency_code()


@contextmanager
def locale_context(language: str | None = None, currency: str | None = None):
    """Bascule temporaire du contexte (workers, threads, tests)."""
    previous = (
        _current_language.get(),
        _current_currency.get(),
        _current_timezone.get(),
        _current_date_format.get(),
        _current_number_format.get(),
    )
    set_locale_context(language=language, currency=currency)
    if language is not None and is_supported(language):
        with translation.override(language):
            yield
        return
    try:
        yield
    finally:
        _current_language.set(previous[0])
        _current_currency.set(previous[1])
        _current_timezone.set(previous[2])
        _current_date_format.set(previous[3])
        _current_number_format.set(previous[4])
