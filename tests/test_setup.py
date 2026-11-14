"""Run setup twice with a real isolated PocketBase backend."""

import os
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from ingest_validate.setup import setup_local


@unittest.skipUnless(os.environ.get("POCKETBASE_TEST_BINARY"), "Set POCKETBASE_TEST_BINARY for setup tests")
class SetupTests(unittest.TestCase):
    def test_setup_is_repeatable_and_removes_its_temporary_admin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            options = dict(binary=os.environ["POCKETBASE_TEST_BINARY"],
                           # Keep account files and server data inside this
                           # test's temporary directory during both setup runs.
                           data_dir=root / "pb_data", env_dir=root, port=port, keep_running=False)
            subprocess.run([options["binary"], "superuser", "create", "owner@example.invalid", "test-owner-password-123",
                            "--dir", str(options["data_dir"]), "--dev=false"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            first = setup_local(**options)
            original = {path: Path(path).read_bytes() for path in first["credential_files"]}
            second = setup_local(**options)
            self.assertFalse(second["server_running"])
            self.assertTrue(second["temporary_admin_removed"])
            for path, content in original.items():
                self.assertEqual(Path(path).read_bytes(), content)
                self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)
            with sqlite3.connect(root / "pb_data/data.db") as connection:
                self.assertEqual(connection.execute("SELECT role FROM telemetry_services ORDER BY role").fetchall(),
                                 [("ingest",), ("reader",), ("worker",)])
                self.assertEqual(connection.execute("SELECT count(*) FROM _superusers").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT count(*) FROM _superusers WHERE email LIKE 'setup-%'").fetchone()[0], 0)

    def test_setup_refuses_an_occupied_port(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with self.assertRaises(ValueError):
                setup_local(binary=os.environ["POCKETBASE_TEST_BINARY"], data_dir=Path(directory) / "pb_data",
                            env_dir=directory, port=listener.getsockname()[1])
            self.assertFalse((Path(directory) / ".env").exists())
