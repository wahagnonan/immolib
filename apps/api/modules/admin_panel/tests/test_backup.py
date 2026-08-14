import gzip
import os
from pathlib import Path
from unittest.mock import patch

import boto3
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

COMMAND_SHUTIL = "modules.admin_panel.management.commands.backup_database.shutil"


class BackupDatabaseCommandTests(TestCase):
    def setUp(self):
        self.tmp = Path(self._testMethodName)
        self.tmp.mkdir(exist_ok=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def test_dumpdata_fallback_writes_local_archive(self):
        get_user_model().objects.create_user(
            phone="+2250707070707", password="motdepasse-test"
        )
        with patch(COMMAND_SHUTIL + ".which", return_value=None):
            call_command("backup_database", output_dir=str(self.tmp), verbosity=0)
        files = list(self.tmp.glob("immolib_*"))
        self.assertEqual(len(files), 1)
        self.assertGreater(files[0].stat().st_size, 0)
        with gzip.open(files[0], "rb") as raw:
            self.assertIn(b"+2250707070707", raw.read())

    def test_rotation_removes_old_local_backups(self):
        old = self.tmp / "immolib_2000-01-01_000000.dump.enc"
        old.write_bytes(b"x")
        with patch(COMMAND_SHUTIL + ".which", return_value=None):
            call_command(
                "backup_database",
                output_dir=str(self.tmp),
                keep_days=1,
                verbosity=0,
            )
        self.assertFalse(old.exists())

    def test_upload_s3_when_bucket_configured(self):
        with patch(COMMAND_SHUTIL + ".which", return_value=None), patch.dict(
            os.environ, {"BACKUP_S3_BUCKET": "immolib-backups"}
        ), patch.object(boto3, "client") as client_mock:
            call_command("backup_database", output_dir=str(self.tmp), verbosity=0)
        client_mock.assert_called_once_with("s3")
        put = client_mock.return_value.put_object
        put.assert_called_once()
        self.assertEqual(put.call_args.kwargs["ServerSideEncryption"], "AES256")
        self.assertTrue(put.call_args.kwargs["Key"].startswith("backups/immolib_"))
