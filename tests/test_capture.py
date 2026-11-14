"""Durable capture must work without validating a single measurement."""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ingest_validate.capture import capture_sensor_packets
from ingest_validate.storage import connect_database


class CaptureTests(unittest.TestCase):
    def setUp(self):
        # Every test owns its database so failed or repeated runs cannot alter
        # the user's local PocketBase database or other tests' measurements.
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "telemetry.sqlite"

    def test_capture_persists_invalid_packets_before_validation(self):
        packets = [{"timestamp": "bad time", "spo2": 140}, "broken packet"]
        ids = capture_sensor_packets(packets, self.db)
        with sqlite3.connect(self.db) as connection:
            rows = connection.execute("SELECT payload, status, captured_at FROM sensor_packets ORDER BY id").fetchall()
            clean_count = connection.execute("SELECT count(*) FROM validated_observations").fetchone()[0]
        self.assertEqual(len(ids), 2)
        self.assertEqual(json.loads(rows[0][0]), packets[0])
        self.assertEqual(rows[0][1:], ("pending", "bad time"))
        self.assertEqual(clean_count, 0)

    def test_retransmissions_are_separate_deliveries(self):
        capture_sensor_packets([{"timestamp": "x"}] * 2, self.db)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM sensor_packets").fetchone()[0], 2)

    def test_receive_time_is_distinct_from_simulation_time(self):
        clock = datetime(2040, 1, 1, tzinfo=timezone.utc)
        capture_sensor_packets([{}], self.db, reference_time=clock)
        with sqlite3.connect(self.db) as connection:
            received, validation_time = connection.execute("SELECT received_at, validation_time FROM sensor_packets").fetchone()
        self.assertNotEqual(received, validation_time)
        self.assertTrue(validation_time.startswith("2040-01-01"))

    def test_existing_database_migrates_without_losing_rows(self):
        with sqlite3.connect(self.db) as connection:
            connection.execute("""CREATE TABLE raw_measurements (
                id INTEGER PRIMARY KEY, received_at TEXT NOT NULL, payload TEXT NOT NULL,
                payload_encoding TEXT NOT NULL, status TEXT NOT NULL, errors_json TEXT NOT NULL)""")
            connection.execute("INSERT INTO raw_measurements VALUES (1, 'old', '{}', 'json', 'quarantined', '[]')")
        connection = connect_database(self.db)
        try:
            self.assertEqual(connection.execute("SELECT payload, sensor_packet_id FROM raw_measurements").fetchone(), ("{}", None))
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            connection.close()

    def test_capture_failure_rolls_back_only_current_batch(self):
        capture_sensor_packets([{}], self.db)
        def interrupted():
            yield {}
            raise RuntimeError("Capture interrupted")
        with self.assertRaises(RuntimeError):
            capture_sensor_packets(interrupted(), self.db)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM sensor_packets").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
