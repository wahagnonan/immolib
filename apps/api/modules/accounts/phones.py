import re

from django.core.exceptions import ValidationError


E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
E164_ERROR = (
    "Utilisez le format international E.164, par exemple +2250700000000."
)


def normalize_e164(value: str) -> str:
    """Retourne un numéro international canonique, sans séparateur."""

    candidate = (value or "").strip()
    if candidate.startswith("00"):
        candidate = f"+{candidate[2:]}"
    candidate = re.sub(r"[\s().-]", "", candidate)
    if not E164_PATTERN.fullmatch(candidate):
        raise ValidationError(E164_ERROR)
    return candidate


def validate_e164(value: str) -> None:
    normalize_e164(value)
