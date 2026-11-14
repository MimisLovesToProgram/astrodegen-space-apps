"""Local settings are data, never executable shell scripts."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingest_validate.config import connection_settings, read_settings


class ConfigTests(unittest.TestCase):
    def test_settings_do_not_execute_shell_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text('POCKETBASE_PASSWORD="$(do-not-execute)"\nPOCKETBASE_URL=http://local\n')
            # Shell-looking text must remain a literal password; only explicit
            # environment settings should override the local file's values.
            self.assertEqual(read_settings(path)["POCKETBASE_PASSWORD"], "$(do-not-execute)")
            with patch.dict(os.environ, {"POCKETBASE_URL": "http://override"}, clear=True):
                self.assertEqual(connection_settings(path)["POCKETBASE_URL"], "http://override")

    def test_invalid_lines_and_missing_explicit_file_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            with self.assertRaises(ValueError):
                connection_settings(path)
            path.write_text("source other-file\n")
            with self.assertRaises(ValueError):
                read_settings(path)
