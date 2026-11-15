"""Recovery and concurrent consumption of the SQLite inbox."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from biosensors import Crew, reading_from
from ingest_validate.capture import capture_sensor_packets
from ingest_validate.worker import validate_pending_packets


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "telemetry.sqlite"
        self.ids = capture_sensor_packets(
            [reading_from(crew, arc[0], 1) for crew, arc in Crew.items()], self.db,
            assume_utc=True, reference_time=datetime(2026, 11, 22, tzinfo=timezone.utc),
        )

    def test_restart_drains_only_pending_batches(self):
        self.assertEqual(validate_pending_packets(self.db, limit=1)["packet_ids"], self.ids[:1])
        self.assertEqual(validate_pending_packets(self.db)["packet_ids"], self.ids[1:])
        self.assertEqual(validate_pending_packets(self.db)["packet_ids"], [])
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM validated_observations").fetchone()[0], 36)
            self.assertEqual(connection.execute("SELECT count(DISTINCT sensor_packet_id) FROM raw_measurements").fetchone()[0], 3)
            self.assertNotIn('"sensor_packet":', connection.execute("SELECT payload FROM raw_measurements LIMIT 1").fetchone()[0])

    def test_failure_leaves_captured_packets_pending(self):
        # Abort in the middle of writing a packet to prove that both metric
        # records and completion markers roll back together.
        with sqlite3.connect(self.db) as connection:
            connection.execute("""CREATE TRIGGER fail_worker BEFORE INSERT ON validated_observations
                WHEN NEW.metric='spo2' BEGIN SELECT RAISE(ABORT, 'test storage failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            validate_pending_packets(self.db)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM sensor_packets WHERE status='pending'").fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_measurements").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM validated_observations").fetchone()[0], 0)
            connection.execute("DROP TRIGGER fail_worker")
        self.assertEqual(len(validate_pending_packets(self.db)["ingestion"]["accepted"]), 36)

    def test_workers_do_not_process_the_same_packet(self):
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: validate_pending_packets(self.db, limit=1), range(3)))
        self.assertEqual(sorted(item for result in results for item in result["packet_ids"]), self.ids)
        self.assertEqual(sum(len(result["ingestion"]["accepted"]) for result in results), 36)


if __name__ == "__main__":
    unittest.main()
