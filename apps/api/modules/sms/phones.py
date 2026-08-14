"""Normalisation des numeros de telephone ivoiriens pour l'envoi de SMS.

Le canal SMS d'ImmoLib cible la Cote d'Ivoire : l'API Orange SMS CI ne livre
que vers les reseaux ivoiriens. Cette normalisation accepte le format local
(``0700000000``) comme le format international (``+2250700000000``) et produit
toujours un E.164 strict commencant par ``+225``.

La validation generale des comptes (modules/accounts/phones.py) reste
inchangee : elle exige deja l'E.164. Cette fonction n'ajoute de la tolerance
que pour le destinataire d'un SMS.
"""

import re

_SEPARATORS = re.compile(r"[\s().-]")


class InvalidPhoneNumber(Exception):
    """Numero qui ne peut pas etre normalise vers un E.164 ivoirien."""


def normalize_ci_phone(value: str) -> str:
    """Retourne ``+225`` suivi du numero national a 10 chiffres.

    Accepte ``+2250700000000``, ``2250700000000`` (sans +), ``0700000000``,
    ``07 00 00 00 00`` et ``002250700000000``. L'echec leve InvalidPhoneNumber.
    """
    candidate = _SEPARATORS.sub("", (value or "").strip())
    if candidate.startswith("+"):
        candidate = candidate[1:]
    if candidate.startswith("00"):
        candidate = candidate[2:]
    if candidate.startswith("225") and len(candidate) == 13:
        candidate = candidate[3:]
    if len(candidate) != 10 or not candidate.isdigit() or not candidate.startswith("0"):
        raise InvalidPhoneNumber(
            "Numero invalide : utilisez le format ivoirien +2250700000000."
        )
    return f"+225{candidate}"
