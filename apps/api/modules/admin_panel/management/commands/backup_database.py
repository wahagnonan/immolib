"""Sauvegarde de la base de donnees ImmoLib.

Utilise pg_dump (format custom) quand la base est PostgreSQL et que le
binaire est present, sinon export JSON ``dumpdata`` compresse (repli).

Destinations, dans l'ordre :
1. Amazon S3 si ``BACKUP_S3_BUCKET`` est defini (cle ``backups/<fichier>``,
   chiffrement cote serveur SSE-S3) ;
2. dossier local ``BACKUP_DIR`` (defaut ``./backups``) avec rotation
   ``BACKUP_RETENTION_DAYS`` (defaut 14).

Chiffrement optionnel : si ``BACKUP_PASSPHRASE`` (ou ``BACKUP_PASSPHRASE_FILE``)
et ``openssl`` sont disponibles, l'archive est chiffree AES-256-CBC avant
toute destination.

Usage (Render cron / hote) :
    python manage.py backup_database
    python manage.py backup_database --output-dir /var/backups --keep-days 30
"""

import gzip
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


class Command(BaseCommand):
    help = (
        "Sauvegarde la base vers S3 (BACKUP_S3_BUCKET) et/ou le disque local "
        "(pg_dump si disponible, sinon dumpdata)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Dossier local de sauvegarde (defaut: BACKUP_DIR ou ./backups).",
        )
        parser.add_argument(
            "--keep-days",
            type=int,
            default=None,
            help="Retention locale en jours (defaut: BACKUP_RETENTION_DAYS ou 14).",
        )

    def handle(self, *args, **options):
        engine = settings.DATABASES["default"]["ENGINE"]
        if "postgresql" in engine and shutil.which("pg_dump"):
            self.stdout.write("PostgreSQL : sauvegarde via pg_dump (format custom).")
            data, suffix = self._pg_dump(), ".dump"
        else:
            self.stdout.write(
                "pg_dump indisponible (ou base non PostgreSQL) : export dumpdata."
            )
            data, suffix = self._dumpdata_dump()

        data, suffix = self._maybe_encrypt(data, suffix)
        filename = f"immolib_{_now_stamp()}{suffix}"

        uploaded = self._upload_s3(filename, data)
        written = self._write_local(
            filename, data, output_dir=options["output_dir"]
        )
        if not uploaded and not written:
            raise CommandError(
                "Aucune destination de sauvegarde disponible : renseigner "
                "BACKUP_S3_BUCKET ou un dossier local accessible."
            )
        if written:
            self._rotate_local(
                output_dir=options["output_dir"], keep_days=options["keep_days"]
            )
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde {filename} terminee."))

    # --- Extraction --------------------------------------------------------

    def _pg_dump(self) -> bytes:
        db = settings.DATABASES["default"]
        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = db["PASSWORD"]
        command = [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "-h", db.get("HOST", ""),
            "-p", str(db.get("PORT", "5432")),
            "-U", db.get("USER", ""),
            db.get("NAME", ""),
        ]
        proc = subprocess.run(command, capture_output=True, check=False, env=env)
        if proc.returncode != 0:
            raise CommandError(
                "pg_dump a echoue: "
                + proc.stderr.decode("utf-8", errors="replace")[:500]
            )
        return proc.stdout

    def _dumpdata_dump(self) -> tuple[bytes, str]:
        from io import StringIO

        from django.core.management import call_command

        output = StringIO()
        call_command("dumpdata", "--all", stdout=output, verbosity=0)
        return gzip.compress(output.getvalue().encode("utf-8")), ".json.gz"

    # --- Chiffrement -------------------------------------------------------

    def _passphrase(self) -> str:
        passphrase = os.getenv("BACKUP_PASSPHRASE", "").strip()
        if passphrase:
            return passphrase
        passphrase_file = os.getenv("BACKUP_PASSPHRASE_FILE", "").strip()
        if passphrase_file:
            try:
                return Path(passphrase_file).read_text(encoding="utf-8").strip()
            except OSError:
                return ""
        return ""

    def _maybe_encrypt(self, data: bytes, suffix: str) -> tuple[bytes, str]:
        passphrase = self._passphrase()
        openssl = shutil.which("openssl")
        if not passphrase or not openssl:
            if passphrase:
                self.stdout.write(
                    self.style.WARNING(
                        "BACKUP_PASSPHRASE present mais openssl indisponible : "
                        "sauvegarde non chiffree (SSE S3 si upload)."
                    )
                )
            return data, suffix
        proc = subprocess.run(
            [
                openssl,
                "enc",
                "-aes-256-cbc",
                "-pbkdf2",
                "-salt",
                "-pass",
                "env:IMMOLIB_BACKUP_PASSPHRASE",
            ],
            input=data,
            capture_output=True,
            check=False,
            env={**os.environ, "IMMOLIB_BACKUP_PASSPHRASE": passphrase},
        )
        if proc.returncode != 0:
            raise CommandError(
                "Chiffrement openssl echoue: "
                + proc.stderr.decode("utf-8", errors="replace")[:300]
            )
        return proc.stdout, suffix + ".enc"

    # --- Destinations ------------------------------------------------------

    def _upload_s3(self, filename: str, data: bytes) -> bool:
        bucket = os.getenv("BACKUP_S3_BUCKET", "").strip()
        if not bucket:
            return False
        try:
            import boto3

            boto3.client("s3").put_object(
                Bucket=bucket,
                Key=f"backups/{filename}",
                Body=data,
                ServerSideEncryption="AES256",
            )
            self.stdout.write(f"S3 : s3://{bucket}/backups/{filename}")
            return True
        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Echec upload S3 ({exc.__class__.__name__}: {exc}) ; "
                    "la copie locale est conservee."
                )
            )
            return False

    def _write_local(self, filename: str, data: bytes, *, output_dir) -> bool:
        base = Path(
            output_dir or os.getenv("BACKUP_DIR", "backups")
        )
        try:
            base.mkdir(parents=True, exist_ok=True)
            (base / filename).write_bytes(data)
            self.stdout.write(f"Local : {base / filename}")
            return True
        except OSError as exc:
            self.stdout.write(
                self.style.WARNING(f"Dossier local {base} inaccessible : {exc}")
            )
            return False

    def _rotate_local(self, *, output_dir, keep_days) -> None:
        keep_days = keep_days or int(os.getenv("BACKUP_RETENTION_DAYS", "14"))
        base = Path(output_dir or os.getenv("BACKUP_DIR", "backups"))
        if not base.exists():
            return
        cutoff = datetime.now() - timedelta(days=keep_days)
        removed = 0
        for path in base.glob("immolib_*"):
            try:
                stamp = path.name[len("immolib_") :].split(".")[0]
                created = datetime.strptime(stamp, "%Y-%m-%d_%H%M%S")
            except ValueError:
                continue
            if created < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        if removed:
            self.stdout.write(
                f"Rotation locale : {removed} ancienne(s) sauvegarde(s) supprimee(s)."
            )
