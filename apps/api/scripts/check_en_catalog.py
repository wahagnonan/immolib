"""Verifie que le catalogue EN se resout correctement via Django."""
import polib

import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import translation  # noqa: E402

po = polib.pofile("locale/en/LC_MESSAGES/django.po", encoding="utf-8")
ids = [e.msgid for e in po if e.msgstr]
print(f"catalogue: {len(ids)} msgids traduits")

translation.activate("en")
fail = 0
for msgid in ids:
    resolved = translation.gettext(msgid)
    if resolved == msgid:
        fail += 1
        print(f"NO-TRANSLATION: {msgid[:80]}")
print(f"echecs: {fail} / {len(ids)}")

checks = [
    "Si le compte est éligible, un code a été mis en file d’envoi.",
    "Le montant doit être strictement positif.",
    "Quittance de loyer",
]
for c in checks:
    print(f"'{c}' -> '{translation.gettext(c)}'")
