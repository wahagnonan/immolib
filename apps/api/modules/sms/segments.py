"""Comptage des segments SMS (GSM-7 et UCS-2) pour mesurer le cout reel.

Un SMS simple tient dans un segment GSM-7 de 160 caracteres (ou 70 en
UCS-2). Au-dela, le message est decoupe en segments concatenes de 153
caracteres GSM-7 (ou 67 en UCS-2).

Des qu'un caractere hors GSM-7 de base est present (accentue etendu, ``€``,
emoji...), le message est compte en UCS-2 : la plupart des agrgregateurs
ivoiriens basculent alors l'encodage. Un message melangeant GSM-7 et UCS-2
est toujours compte en segments concatenes de 67 caracteres : la encore, le
choix est volontairement prudent (jamais sous-evalue).
"""

_GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ "
    '"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿'
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)

_GSM7_SINGLE_LIMIT = 160
_GSM7_CONCATENATED_LIMIT = 153
_UCS2_SINGLE_LIMIT = 70
_UCS2_CONCATENATED_LIMIT = 67


def is_gsm7(text: str) -> bool:
    """True si le texte tient entierement dans le jeu GSM-7 de base."""
    return all(character in _GSM7_BASIC for character in text)


def count_segments(text: str) -> int:
    """Nombre de segments factures pour un texte SMS."""
    if not text:
        return 1
    if is_gsm7(text):
        if len(text) <= _GSM7_SINGLE_LIMIT:
            return 1
        return -(-len(text) // _GSM7_CONCATENATED_LIMIT)
    if any(character in _GSM7_BASIC for character in text):
        return max(1, -(-len(text) // _UCS2_CONCATENATED_LIMIT))
    if len(text) <= _UCS2_SINGLE_LIMIT:
        return 1
    return -(-len(text) // _UCS2_CONCATENATED_LIMIT)
