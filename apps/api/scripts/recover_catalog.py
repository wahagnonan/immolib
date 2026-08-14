"""Reconstruit locale/en/LC_MESSAGES/django.po depuis le POT frais.

L'ancien catalogue contient des msgid corrompus (octets latin-1 declarés
UTF-8) : on les re-decode pour tenter de reutiliser les traductions dont le
msgid correspond a une chaine reelle du code. Les chaines sans traduction
recuperable sont listees pour traduction manuelle.
"""
import sys
from pathlib import Path

import polib

BASE = Path(__file__).resolve().parent.parent
POT = BASE / "locale" / "django.pot"
OLD = BASE / "locale" / "en" / "LC_MESSAGES" / "django.po"
NEW = BASE / "locale" / "en" / "LC_MESSAGES" / "django.po"

pot = polib.pofile(str(POT), encoding="utf-8")
old = polib.pofile(str(OLD), encoding="utf-8")

def _repair(msgid: str) -> str:
    return msgid.encode("latin-1", errors="replace").decode("utf-8", errors="replace")

repairs = {}
for entry in old:
    if not entry.msgstr or entry.msgid in repairs:
        continue
    repaired = _repair(entry.msgid)
    if repaired != entry.msgid and repaired:
        repairs[repaired] = entry.msgstr

new = polib.POFile()
new.metadata = {
    "Project-Id-Version": "ImmoLib",
    "Report-Msgid-Bugs-To": "support@immolib.ci",
    "POT-Creation-Date": pot.metadata["POT-Creation-Date"],
    "PO-Revision-Date": "2026-08-14 12:00+0000",
    "Last-Translator": "ImmoLib i18n",
    "Language-Team": "English <en@immolib.ci>",
    "Language": "en",
    "MIME-Version": "1.0",
    "Content-Type": "text/plain; charset=utf-8",
    "Content-Transfer-Encoding": "8bit",
    "Plural-Forms": "nplurals=2; plural=(n != 1);",
}

recovered = 0
missing = []
for entry in pot:
    if not entry.msgid:
        continue
    msgstr = ""
    if entry.msgid in repairs:
        msgstr = repairs[entry.msgid]
    else:
        old_entry = old.find(entry.msgid)
        msgstr = old_entry.msgstr if old_entry else ""
    if msgstr:
        recovered += 1
    else:
        missing.append(entry.msgid)
    new.append(polib.POEntry(msgid=entry.msgid, msgstr=msgstr, occurrences=entry.occurrences))

new.save(str(NEW))
print(f"POT: {len(pot)} msgids | traductions recuperees: {recovered} | manquantes: {len(missing)}")
for m in missing:
    print("MISSING:", m.replace("\n", "\\n")[:120])
