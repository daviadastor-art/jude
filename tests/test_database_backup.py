import gzip
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telegram_bot import backup


class DatabaseBackupTests(unittest.TestCase):
    def test_progress_bar_is_bounded_and_has_percentage(self):
        self.assertIn("0%", backup.progress_text(-10, "بدء"))
        self.assertIn("100%", backup.progress_text(120, "اكتمل"))
        self.assertIn("جميع الجداول", backup.progress_text(50, "جاري العمل"))

    def test_create_backup_compresses_dump_and_cleans_with_helper(self):
        def fake_run(command, **kwargs):
            sql_file = Path(command[command.index("--file") + 1])
            sql_file.write_text("CREATE TABLE users (id integer);\n", encoding="utf-8")
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return Result()

        with patch.object(backup.shutil, "which", return_value="/usr/bin/pg_dump"), \
                patch.object(backup.subprocess, "run", side_effect=fake_run), \
                patch.object(backup.settings, "DATABASE_URL", "postgresql://example/db"):
            path, size = backup.create_database_backup()
            self.assertGreater(size, 0)
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                self.assertIn("CREATE TABLE users", stream.read())
            backup.cleanup_backup_file(path)
            self.assertFalse(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
