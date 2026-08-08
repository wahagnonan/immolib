"""Registre central des langues supportees par ImmoLib.

C'est la SEULE source de verite pour les codes de langue. Aucune langue
ne doit etre codee en dur ailleurs dans le projet : toute nouvelle langue
s'ajoute ici, puis est activee depuis le panneau d'administration.
"""

LanguageEntry = tuple[str, str, bool, bool]

# (code, nom natif, active, ecriture de droite a gauche)
_LANGUAGES: tuple[LanguageEntry, ...] = (
    ("fr", "Français", True, False),
    ("en", "English", True, False),
    ("es", "Español", True, False),
    ("pt", "Português", True, False),
    ("ar", "العربية", True, True),
    ("sw", "Kiswahili", False, False),
    ("bm", "Bamanankan", False, False),
    ("wo", "Wolof", False, False),
    ("ln", "Lingála", False, False),
    ("yo", "Yorùbá", False, False),
    ("ha", "Hausa", False, False),
    ("am", "አማርኛ", False, False),
)

CODE_INDEX = {code: index for index, (code, *_rest) in enumerate(_LANGUAGES)}

NATIVE_NAMES = {code: name for code, name, _active, _rtl in _LANGUAGES}
RTL_CODES = {code for code, _name, _active, rtl in _LANGUAGES if rtl}
ACTIVE_CODES = tuple(code for code, _name, active, _rtl in _LANGUAGES if active)

#: Couple (code, nom) consomme par ``settings.LANGUAGES`` et le middleware.
LANGUAGES: list[tuple[str, str]] = [
    (code, name) for code, name, _active, _rtl in _LANGUAGES
]

LANGUAGE_CODES = [code for code, _name in LANGUAGES]

#: Choices pour les champs de modele Django (preferences utilisateur).
LANGUAGE_CHOICES = [(code, name) for code, name in LANGUAGES]


def is_supported(code: str) -> bool:
    """Retourne True si le code correspond a une langue enregistree."""
    return code in CODE_INDEX


def is_active(code: str) -> bool:
    """Retourne True si la langue est enregistree ET active."""
    return code in ACTIVE_CODES


def get_native_name(code: str) -> str:
    return NATIVE_NAMES.get(code, code)


def is_rtl(code: str) -> bool:
    return code in RTL_CODES


def default_language_code() -> str:
    """Langue utilisee lorsque aucune preference n'est exprimable."""
    return "fr"
